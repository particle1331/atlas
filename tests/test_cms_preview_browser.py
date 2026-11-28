"""Opt-in real Quarto/Chromium regression for preview renderer restarts."""

import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from test_cms import store, workspace  # noqa: F401 -- shared CMS fixtures

from atlas import cms_notebooks as nb
from atlas.cms_store import decode, encode

pytestmark = pytest.mark.skipif(
    os.environ.get("ATLAS_BROWSER_TESTS") != "1",
    reason="Set ATLAS_BROWSER_TESTS=1 to run real preview/browser checks.",
)


def test_preview_tabs_recover_after_repeated_offline_refreshes(store):
    playwright = pytest.importorskip("playwright.sync_api")
    quarto = shutil.which(os.environ.get("QUARTO", "quarto"))
    if not quarto:
        pytest.skip("Quarto is required for the browser check.")
    repository = Path(__file__).resolve().parents[1]
    shutil.copyfile(
        repository / "frontend/_quarto-preview.yml",
        store.path("frontend/_quarto-preview.yml"),
    )
    shutil.copyfile(
        repository / "frontend/_cms/preview-reload.html",
        store.path("frontend/_cms/preview-reload.html"),
    )
    # Guarantee a visible offline interval, rather than merely hoping the
    # browser catches the small gap between two fast Quarto processes.
    wrapper = store.root / "slow-quarto"
    wrapper.write_text(
        '#!/bin/sh\ncase "$*" in *--to*typst*) sleep 2 ;; esac\n'
        f'exec {shlex.quote(quarto)} "$@"\n'
    )
    wrapper.chmod(0o755)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    log = store.root / "preview.log"
    socket_events = []
    with log.open("w") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from atlas.cli import main; main()",
                "cms",
                "--root",
                str(store.root),
                "preview",
                "--port",
                str(port),
            ],
            env={**os.environ, "QUARTO": str(wrapper)},
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                assert process.poll() is None, log.read_text()
                try:
                    with urllib.request.urlopen(
                        origin + "/posts/example.html", timeout=5
                    ) as response:
                        if "Original body" in response.read().decode():
                            break
                except OSError:
                    time.sleep(0.25)
            else:
                pytest.fail("Preview did not start:\n" + log.read_text())

            with playwright.sync_playwright() as runtime:
                browser = runtime.chromium.launch(
                    executable_path=os.environ.get("ATLAS_CHROMIUM"),
                    args=["--no-sandbox"],
                )
                context = browser.new_context()
                first_marker = True

                def transient_marker_failure(route):
                    nonlocal first_marker
                    if first_marker:
                        first_marker = False
                        route.abort("failed")
                    else:
                        route.continue_()

                context.route(
                    "**/atlas-preview-generation.json", transient_marker_failure
                )
                context.add_init_script("""
                    window.__testSockets = [];
                    const Socket = window.WebSocket;
                    window.WebSocket = class RecordingWebSocket extends Socket {
                      constructor(...args) {
                        super(...args);
                        window.__testSockets.push(this);
                      }
                    };
                    """)
                pages = [context.new_page(), context.new_page()]
                failures = []
                errors = []

                def track_socket(socket):
                    socket.on(
                        "framereceived",
                        lambda value: socket_events.append(
                            ("message", socket.url, value)
                        ),
                    )
                    socket.on(
                        "close", lambda: socket_events.append(("close", socket.url))
                    )

                for page in pages:
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("websocket", track_socket)
                    page.on(
                        "requestfailed",
                        lambda request: failures.append((request.url, request.failure)),
                    )
                urls = [
                    f"{origin}/posts/example.html?atlas-test=reload#preview-fragment",
                    f"{origin}/resume.html",
                ]
                for page, url in zip(pages, urls):
                    page.goto(url)
                    page.wait_for_function(
                        "window.__testSockets.some(s => s.readyState === 1)"
                    )
                    page.wait_for_function(
                        """sessionStorage.getItem("atlas-preview-generation:" +
                           location.pathname + location.search) !== null"""
                    )
                    assert page.evaluate("WebSocket.name") == "RecordingWebSocket"

                previous_pdf = store.path("frontend/assets/resume.pdf").read_bytes()
                for revision in range(3):
                    marker = f"Same-tab saved revision {revision}"
                    profile = decode(store.path("content/resume.yaml").read_bytes())
                    profile["summary"] = marker
                    store.path("content/resume.yaml").write_bytes(encode(profile))
                    store.path("content/posts/example.ipynb").write_bytes(
                        nb.dump(nb.notebook(marker))
                    )
                    # Do not navigate or reload from the test: the existing,
                    # nested post tab and résumé tab must recover themselves.
                    for page in pages:
                        try:
                            page.get_by_text(marker).wait_for(timeout=60000)
                        except Exception:
                            print("Browser state:", page.url, page.inner_text("body"))
                            raise
                        page.wait_for_function(
                            "window.__testSockets.some(s => s.readyState === 1)"
                        )
                    pdf = store.path("frontend/assets/resume.pdf").read_bytes()
                    assert pdf.startswith(b"%PDF-") and pdf != previous_pdf
                    previous_pdf = pdf

                # An old document can finish initializing against the new
                # server, so its socket never observes the old server closing.
                post, resume = pages
                post.add_init_script("""
                    if (!sessionStorage.getItem("atlas-test-delayed-init")) {
                      sessionStorage.setItem("atlas-test-delayed-init", "1");
                      const add = document.addEventListener;
                      const pending = [];
                      document.addEventListener = function (...args) {
                        if (args[0] === "DOMContentLoaded") pending.push(args);
                        else return Reflect.apply(add, this, args);
                      };
                      window.__releasePreview = () => {
                        document.addEventListener = add;
                        for (const args of pending) {
                          Reflect.apply(add, document, args);
                        }
                        document.dispatchEvent(
                          new Event("DOMContentLoaded", { bubbles: true })
                        );
                      };
                    }
                    """)
                post.goto(post.url)
                assert post.get_by_text(marker).is_visible()
                marker = "Save while an old document is still initializing"
                profile["summary"] = marker
                store.path("content/resume.yaml").write_bytes(encode(profile))
                store.path("content/posts/example.ipynb").write_bytes(
                    nb.dump(nb.notebook(marker))
                )
                resume.get_by_text(marker).wait_for(timeout=60000)
                post.evaluate("window.__releasePreview()")
                post.get_by_text(marker).wait_for(timeout=60000)
                post.wait_for_function(
                    "window.__testSockets.some(s => s.readyState === 1)"
                )

                # Simulate a cached page being hidden and restored while the
                # port is down; it must wait, not navigate to an error page.
                failed_before = len(failures)
                marker = "Save across a cached-page restoration"
                profile["summary"] = marker
                store.path("content/resume.yaml").write_bytes(encode(profile))
                store.path("content/posts/example.ipynb").write_bytes(
                    nb.dump(nb.notebook(marker))
                )
                deadline = time.monotonic() + 20
                while len(failures) == failed_before and time.monotonic() < deadline:
                    post.wait_for_timeout(50)
                assert len(failures) > failed_before
                post.evaluate("""
                    window.dispatchEvent(
                      new PageTransitionEvent("pagehide", { persisted: true })
                    );
                    window.dispatchEvent(
                      new PageTransitionEvent("pageshow", { persisted: true })
                    );
                    """)
                post.get_by_text(marker).wait_for(timeout=60000)
                assert [page.url for page in pages] == urls
                assert not errors
                assert any(
                    "atlas-preview-generation.json" in url
                    and failure == "net::ERR_CONNECTION_REFUSED"
                    for url, failure in failures
                )
                browser.close()
        except Exception:
            print("Preview socket events:", socket_events)
            print(log.read_text())
            raise
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()

    public = subprocess.run(
        [
            sys.executable,
            "-c",
            "from atlas.cli import main; main()",
            "cms",
            "--root",
            str(store.root),
            "build",
        ],
        env={**os.environ, "QUARTO": str(wrapper)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert public.returncode == 0, public.stderr
    html = store.path("frontend/_site/posts/example.html").read_text()
    assert "atlas-preview-generation" not in html
    assert not store.path("frontend/_site/atlas-preview-generation.json").exists()
