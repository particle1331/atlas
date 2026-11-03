import pytest
from typer.testing import CliRunner

from atlas.cli import app

runner = CliRunner()


def _pdf_bytes(
    pages: list[str],
    outline: list[tuple[str, int]] | None = None,
    info: dict[str, str] | None = None,
) -> bytes:
    """Build a minimal valid PDF: one text line per page, bookmarks and info."""
    outline = outline or []
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add(num: int, body: bytes) -> None:
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

    n_pages = len(pages)
    page_nums = [3 + 2 * i for i in range(n_pages)]
    font_num = 3 + 2 * n_pages
    outline_start = font_num + 1

    kids = " ".join(f"{num} 0 R" for num in page_nums)
    add(2, f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    add(font_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    if outline:
        outlines_body = (
            f"<< /Type /Outlines /First {outline_start + 1} 0 R "
            f"/Last {outline_start + len(outline)} 0 R /Count {len(outline)} >>"
        )
    else:
        outlines_body = "<< /Type /Outlines /Count 0 >>"
    add(outline_start, outlines_body.encode())
    for j, (title, page_index) in enumerate(outline):
        num = outline_start + 1 + j
        parts = [
            f"/Title ({title})",
            f"/Parent {outline_start} 0 R",
            f"/Dest [{page_nums[page_index]} 0 R /XYZ null null null]",
        ]
        if j > 0:
            parts.append(f"/Prev {num - 1} 0 R")
        if j < len(outline) - 1:
            parts.append(f"/Next {num + 1} 0 R")
        add(num, ("<< " + " ".join(parts) + " >>").encode())

    info_num = None
    if info:
        info_num = outline_start + len(outline) + 1
        body = " ".join(f"/{key.lstrip('/')} ({value})" for key, value in info.items())
        add(info_num, ("<< " + body + " >>").encode())

    for i, text in enumerate(pages):
        page_num, content_num = 3 + 2 * i, 4 + 2 * i
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        add(
            content_num,
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
        )
        add(
            page_num,
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_num} 0 R "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> >>".encode(),
        )

    add(
        1,
        f"<< /Type /Catalog /Pages 2 0 R /Outlines {outline_start} 0 R >>".encode(),
    )

    xref_pos = len(out)
    max_obj = max(offsets)
    out.extend(f"xref\n0 {max_obj + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for num in range(1, max_obj + 1):
        out.extend(f"{offsets[num]:010d} 00000 n \n".encode())
    trailer_dict = f"<< /Size {max_obj + 1} /Root 1 0 R"
    if info_num is not None:
        trailer_dict += f" /Info {info_num} 0 R"
    out.extend(f"trailer\n{trailer_dict} >>\nstartxref\n{xref_pos}\n%%EOF\n".encode())
    return bytes(out)


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(
        _pdf_bytes(
            [
                "Alpha intro on page one.",
                "Beta notes about handoff on page two.",
                "Gamma summary on page three.",
            ],
            outline=[("Part One", 0), ("Chapter 1", 1)],
            info={"/Title": "Test Book", "/Author": "Test Author"},
        )
    )
    return path


def invoke(*args, code=0):
    result = runner.invoke(app, ["pdf", *args])
    assert result.exit_code == code, (result.output, result.exception)
    return result


def test_info(sample_pdf):
    result = invoke("info", str(sample_pdf))
    assert "Pages: 3" in result.output
    assert "Title: Test Book" in result.output
    assert "Author: Test Author" in result.output
    assert "Bookmarks: 2" in result.output


def test_info_without_metadata(tmp_path):
    path = tmp_path / "plain.pdf"
    path.write_bytes(_pdf_bytes(["Only page text."]))
    result = invoke("info", str(path))
    assert "Pages: 1" in result.output
    assert "Title: unknown" in result.output
    assert "Bookmarks: 0" in result.output


def test_info_missing_file(tmp_path):
    invoke("info", str(tmp_path / "absent.pdf"), code=2)


def test_invalid_pdf(tmp_path, capsys):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is not a pdf")
    result = invoke("info", str(path), code=2)
    assert "Could not read PDF" in result.stderr


def test_outline(sample_pdf):
    result = invoke("outline", str(sample_pdf))
    assert "Part One (p.1)" in result.output
    assert "Chapter 1 (p.2)" in result.output


def test_outline_without_bookmarks(tmp_path):
    path = tmp_path / "plain.pdf"
    path.write_bytes(_pdf_bytes(["Only page text."]))
    result = invoke("outline", str(path))
    assert "No bookmarks." in result.output


def test_read_range(sample_pdf):
    result = invoke("read", str(sample_pdf), "--pages", "2-3")
    assert "--- p.2 ---" in result.output
    assert "Beta notes about handoff" in result.output
    assert "--- p.3 ---" in result.output
    assert "Alpha intro" not in result.output


def test_read_single_page(sample_pdf):
    result = invoke("read", str(sample_pdf), "--pages", "2")
    assert "Beta notes about handoff" in result.output
    assert "Alpha intro" not in result.output
    assert "Gamma summary" not in result.output


def test_read_open_range(sample_pdf):
    result = invoke("read", str(sample_pdf), "--pages", "2-")
    assert "Beta notes about handoff" in result.output
    assert "Gamma summary" in result.output
    assert "Alpha intro" not in result.output


def test_read_from_start(sample_pdf):
    result = invoke("read", str(sample_pdf), "--pages", "-2")
    assert "Alpha intro" in result.output
    assert "Gamma summary" not in result.output


def test_read_blank_page(tmp_path):
    path = tmp_path / "blank.pdf"
    path.write_bytes(_pdf_bytes(["Alpha text.", "", "Gamma text."]))
    result = invoke("read", str(path), "--pages", "2-3")
    assert "--- p.2 ---" in result.output
    assert "[no extractable text]" in result.output
    assert "Gamma text." in result.output


@pytest.mark.parametrize("spec", ["abc", "", "-", "0", "4", "5-", "3-1", "2-b"])
def test_read_invalid_page_spec(sample_pdf, spec):
    result = invoke("read", str(sample_pdf), "--pages", spec, code=2)
    assert "Error:" in result.stderr


def test_find_match(sample_pdf):
    result = invoke("find", str(sample_pdf), "handoff")
    assert "p.2: Beta notes about handoff on page two." in result.output


def test_find_is_case_insensitive(sample_pdf):
    result = invoke("find", str(sample_pdf), "HANDOFF")
    assert "p.2:" in result.output


def test_find_no_match(sample_pdf):
    result = invoke("find", str(sample_pdf), "missing word")
    assert "No matches." in result.output


def test_find_page_range(sample_pdf):
    result = invoke("find", str(sample_pdf), "handoff", "--pages", "3")
    assert "No matches." in result.output
    result = invoke("find", str(sample_pdf), "handoff", "--pages", "2-3")
    assert "p.2:" in result.output


def test_find_invalid_page_range(sample_pdf):
    invoke("find", str(sample_pdf), "handoff", "--pages", "9-10", code=2)


def test_read_expands_home(sample_pdf, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = invoke("read", "~/sample.pdf", "--pages", "1")
    assert "Alpha intro" in result.output
