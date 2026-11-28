import json
import signal

import pytest
from test_cms import invoke, store, workspace  # noqa: F401 -- shared CMS fixtures

from atlas import cms
from atlas import cms_notebooks as nb
from atlas.cms_site import generate
from atlas.cms_store import Store, decode, document, encode


@pytest.mark.parametrize("page", ["posts", "collections"])
@pytest.mark.parametrize("listing", [None, "posts/*.ipynb", []])
def test_invalid_listing_is_rejected_before_stopping_preview(store, page, listing):
    generate(store, preview=True)
    projected = store.path(f"frontend/{page}.qmd")
    previous = projected.read_bytes()
    store.path(f"frontend/_cms/{page}.qmd").write_bytes(
        document({"title": page, "listing": listing}, "Listing.")
    )
    stopped = []

    with pytest.raises(ValueError, match="listing mapping"):
        generate(store, preview=True, before_install=lambda: stopped.append(True))

    assert stopped == []
    assert projected.read_bytes() == previous


@pytest.mark.parametrize("cleanup_races_write", [False, True])
def test_preview_restores_generation_removed_by_startup_cleanup(
    store, monkeypatch, cleanup_races_write
):
    marker = cms.preview_generation_marker(store)
    generation = cms.write_preview_generation(marker)
    tick = 0
    attempts = 0
    write = cms.write_preview_generation

    class Process:
        def poll(self):
            return 0 if tick >= 3 else None

    def sleep(duration):
        nonlocal tick
        assert duration == 0.25
        tick += 1
        if tick == 1:
            marker.unlink()

    def restore(path, token):
        nonlocal attempts
        attempts += 1
        if cleanup_races_write and attempts == 1:
            raise FileNotFoundError("Quarto removed the temporary marker")
        return write(path, token)

    monkeypatch.setattr(cms.time, "sleep", sleep)
    monkeypatch.setattr(cms, "write_preview_generation", restore)
    assert (
        cms.watch_preview(store, "/bin/quarto", Process(), generation=generation)
        is None
    )
    assert json.loads(marker.read_text())["generation"] == generation
    assert attempts == (2 if cleanup_races_write else 1)


@pytest.mark.parametrize("command", [("sync",), ("sync", "--preview"), ("build",)])
def test_explicit_projection_writes_are_rejected_during_live_preview(store, command):
    generate(store, preview=True)
    previous = store.path("frontend/posts/example.ipynb").read_bytes()
    with cms.site_lock(store, "live-preview"):
        result = invoke(store, *command, code=2)
    assert "live preview" in result.stderr.lower()
    assert store.path("frontend/posts/example.ipynb").read_bytes() == previous


def fake_preview(monkeypatch, watch):
    processes = []

    class Process:
        pid = 1234

        def __init__(self):
            self.returncode = None if not processes else 0

        def poll(self):
            return self.returncode

    def start(*args, **kwargs):
        process = Process()
        processes.append(process)
        return process

    def stop(process):
        if process.poll() is None:
            process.returncode = -signal.SIGTERM

    monkeypatch.setattr(cms, "quarto_executable", lambda: "/bin/quarto")
    monkeypatch.setattr(cms, "render_resume_pdf", lambda *_: None)
    monkeypatch.setattr(cms.subprocess, "Popen", start)
    monkeypatch.setattr(cms, "watch_preview", watch)
    monkeypatch.setattr(cms, "stop_preview", stop)
    return processes


@pytest.mark.parametrize("recovery_fails", [False, True])
def test_preview_recovers_partial_install_before_restarting(
    store, monkeypatch, recovery_fails
):
    generate(store, preview=True)
    post = store.path("frontend/posts/example.ipynb")
    resume = store.path("frontend/resume.qmd")
    pending = store.path(".atlas/cms/pending.json")
    updates = {post: b"New projected post", resume: b"New projected resume"}
    install = Store._install
    enabled = False
    faulted = False

    def interrupted_install(actual_store, path, raw):
        nonlocal faulted
        if enabled and path == resume and (not faulted or recovery_fails):
            faulted = True
            raise OSError("Interrupted projection install")
        install(actual_store, path, raw)

    def watch(actual_store, executable, process, previous, **kwargs):
        nonlocal enabled
        if len(processes) == 1:
            cms.stop_preview(process)
            enabled = True
            with pytest.raises(OSError), actual_store.lock():
                actual_store.commit(updates)
            assert pending.exists()
            return previous
        assert not pending.exists()
        assert all(path.read_bytes() == raw for path, raw in updates.items())
        return None

    monkeypatch.setattr(Store, "_install", interrupted_install)
    processes = fake_preview(monkeypatch, watch)
    invoke(store, "preview", code=2 if recovery_fails else 0)
    assert len(processes) == (1 if recovery_fails else 2)
    assert pending.exists() is recovery_fails
    assert processes[0].returncode == -signal.SIGTERM
    assert not cms.preview_generation_marker(store).exists()


@pytest.mark.parametrize("termination", [signal.SIGTERM, signal.SIGHUP])
def test_preview_termination_signals_cleanup_child_and_restore_handlers(
    store, monkeypatch, termination
):
    original = signal.getsignal(termination)

    def watch(actual_store, executable, process, previous, **kwargs):
        handler = signal.getsignal(termination)
        assert callable(handler)
        handler(termination, None)

    processes = fake_preview(monkeypatch, watch)
    invoke(store, "preview", code=128 + termination)
    assert processes[0].returncode == -signal.SIGTERM
    assert signal.getsignal(termination) == original
    assert not cms.preview_generation_marker(store).exists()


def refresh_clock(monkeypatch):
    tick = 0

    def sleep(duration):
        nonlocal tick
        assert duration == 0.25
        tick += 1
        assert tick < 12, "Refresh failed to stop or restart"

    monkeypatch.setattr(cms.time, "sleep", sleep)
    monkeypatch.setattr(cms.time, "monotonic", lambda: tick * 0.25)


@pytest.mark.parametrize("termination", [signal.SIGTERM, signal.SIGHUP])
@pytest.mark.parametrize("phase", ["stage", "pdf"])
def test_termination_during_actual_refresh_is_not_caught_as_invalid_save(
    store, monkeypatch, termination, phase
):
    original_handler = signal.getsignal(termination)
    actual_watch = cms.watch_preview
    generate = cms.generate

    def terminate():
        signal.getsignal(termination)(termination, None)

    def stage(*args, **kwargs):
        if processes and phase == "stage":
            terminate()
        return generate(*args, **kwargs)

    def pdf(*_):
        if processes and phase == "pdf":
            terminate()

    def watch(actual_store, executable, process, previous, **kwargs):
        path = actual_store.path("content/resume.yaml")
        path.write_bytes(encode(decode(path.read_bytes()) | {"summary": "Edited"}))
        return actual_watch(actual_store, executable, process, previous, **kwargs)

    processes = fake_preview(monkeypatch, watch)
    monkeypatch.setattr(cms, "generate", stage)
    monkeypatch.setattr(cms, "render_resume_pdf", pdf)
    refresh_clock(monkeypatch)
    result = invoke(store, "preview", code=128 + termination)
    assert "Preview sync failed" not in result.stderr
    assert len(processes) == 1
    assert processes[0].returncode == -signal.SIGTERM
    assert signal.getsignal(termination) == original_handler
    assert not cms.preview_generation_marker(store).exists()


@pytest.mark.parametrize("recovery_fails", [False, True])
def test_partial_refresh_finishes_pruning_and_pdf_before_restart(
    store, monkeypatch, recovery_fails
):
    actual_watch = cms.watch_preview
    install = Store._install
    faulted = False
    stale = store.path("frontend/_site-preview/posts/removed.html")
    pdf = store.path("frontend/assets/resume.pdf")

    def interrupted_install(actual_store, path, raw):
        nonlocal faulted
        if (
            processes
            and path == store.path("frontend/resume.qmd")
            and (not faulted or recovery_fails)
        ):
            faulted = True
            raise OSError("Interrupted projection")
        install(actual_store, path, raw)

    def render(actual_store, _executable):
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(
            b"%PDF-1.7\n" + actual_store.path(".atlas/cms/resume.qmd").read_bytes()
        )

    def watch(actual_store, executable, process, previous, **kwargs):
        if len(processes) > 1:
            assert not stale.exists()
            assert b"After recovery" in pdf.read_bytes()
            assert not actual_store.path(".atlas/cms/pending.json").exists()
            return None
        path = actual_store.path("content/resume.yaml")
        path.write_bytes(
            encode(decode(path.read_bytes()) | {"summary": "After recovery"})
        )
        actual_store.path("content/posts/example.ipynb").write_bytes(
            nb.dump(nb.notebook("After recovery"))
        )
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("Stale rendered page")
        return actual_watch(actual_store, executable, process, previous, **kwargs)

    processes = fake_preview(monkeypatch, watch)
    monkeypatch.setattr(Store, "_install", interrupted_install)
    monkeypatch.setattr(cms, "render_resume_pdf", render)
    refresh_clock(monkeypatch)
    result = invoke(store, "preview", code=2 if recovery_fails else 0)
    assert "Preview sync failed" in result.stderr
    assert faulted
    assert len(processes) == (1 if recovery_fails else 2)
    assert store.path(".atlas/cms/pending.json").exists() is recovery_fails
    assert not cms.preview_generation_marker(store).exists()
