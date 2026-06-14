import zipfile

import pytest

# reader_tab imports PySide6 at module load; skip where the GUI stack is absent.
pytest.importorskip("PySide6")

from pathlib import Path

from src.tabs.reader_tab import ReaderTab, _html_to_text


def _make_epub(path: Path, opf_path: str, files: dict, spine: list) -> Path:
    """Build a minimal valid EPUB. `files` maps archive name -> bytes/str."""
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            f'<rootfiles><rootfile full-path="{opf_path}" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        for name, data in files.items():
            z.writestr(name, data)
    return path


def _extract(path: Path) -> str:
    # _extract_epub does not use instance state; call it without running __init__.
    obj = ReaderTab.__new__(ReaderTab)
    return ReaderTab._extract_epub(obj, path)


def test_html_to_text_strips_tags_and_collapses_whitespace():
    html = (
        "<html><head><title>nope</title><style>p{}</style></head>"
        "<body><h1>Title</h1><p>Hello   world.</p>"
        "<p>Second&nbsp;line with <em>emphasis</em>.</p>"
        "<script>var x=1;</script></body></html>"
    )
    text = _html_to_text(html)
    assert "nope" not in text and "var x" not in text
    assert "Hello world." in text
    assert "Second line with emphasis." in text


def test_extract_epub_reading_order_and_subdir(tmp_path):
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
        '<item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        '</manifest>'
        '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'
    )
    epub = _make_epub(
        tmp_path / "book.epub",
        "OEBPS/content.opf",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/ch1.xhtml": "<html><body><h1>Chapter One</h1>"
                               "<p>First.</p></body></html>",
            "OEBPS/ch2.xhtml": "<html><body><h1>Chapter Two</h1>"
                               "<p>Second.</p></body></html>",
        },
        ["c1", "c2"],
    )
    text = _extract(epub)
    assert "Chapter One" in text and "Chapter Two" in text
    # Manifest lists c2 first, but the spine dictates c1 then c2.
    assert text.index("Chapter One") < text.index("Chapter Two")


def test_extract_epub_root_opf_and_missing_spine_item(tmp_path):
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0"><manifest>'
        '<item id="a" href="a.html" media-type="application/xhtml+xml"/>'
        '</manifest>'
        '<spine><itemref idref="a"/><itemref idref="ghost"/></spine></package>'
    )
    epub = _make_epub(
        tmp_path / "book2.epub",
        "book.opf",
        {
            "book.opf": opf,
            "a.html": "<html><body><p>Root level chapter.</p></body></html>",
        },
        ["a", "ghost"],
    )
    text = _extract(epub)
    # A ghost spine entry with no manifest href must be skipped, not raise.
    assert text.strip() == "Root level chapter."
