import json
import shutil
from pathlib import Path

import pytest
from pdfplumber.utils.exceptions import PdfminerException
from PIL import Image

from layoutlens.core import (
    Word,
    clean_number,
    extract,
    normalized_box,
    ocr,
    spatial_tables,
)
from layoutlens.export import export

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_statement_cells_and_coordinates(tmp_path):
    result = extract(FIX / "statement.pdf")
    page = result["pages"][0]
    expected = json.loads((FIX / "expected.json").read_text())["statement"]
    assert [[c["text"] for c in r] for r in page["tables"][0]["rows"]] == expected
    assert all(
        c["box"] and c["box"][2] > c["box"][0]
        for r in page["tables"][0]["rows"]
        for c in r
    )
    assert page["source"] == "pdf-text"
    export(result, tmp_path)
    assert len(list(tmp_path.glob("*.csv"))) == 1
    assert (
        json.loads((tmp_path / "page-1-table-1.normalized.json").read_text())[2][1]
        == "-820"
    )
    assert "<svg" in (tmp_path / "report.html").read_text()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$1,250.00", "1250.00"),
        ("(820)", "-820"),
        ("1,2", "1,2"),
        ("Revenue", "Revenue"),
        ("12%", "12%"),
        ("(12", "(12"),
    ],
)
def test_numbers(raw, expected):
    assert clean_number(raw) == expected


def test_spatial_multitoken_cells():
    words = [
        Word("Net", [0, 0, 15, 10]),
        Word("income", [19, 0, 48, 10]),
        Word("100", [100, 0, 120, 10]),
        Word("Total", [0, 20, 35, 30]),
        Word("100", [100, 20, 120, 30]),
    ]
    table = spatial_tables(words)[0]
    assert table["rows"][0][0]["text"] == "Net income"


def test_no_false_single_row_table():
    assert (
        spatial_tables([Word("A", [0, 0, 10, 10]), Word("B", [100, 0, 110, 10])]) == []
    )


def test_limits_and_formats(tmp_path):
    with pytest.raises(ValueError, match="byte limit"):
        extract(FIX / "statement.pdf", max_bytes=1)
    with pytest.raises(ValueError, match="positive"):
        extract(FIX / "statement.pdf", max_pages=0)
    f = tmp_path / "bad.txt"
    f.write_text("test")
    with pytest.raises(ValueError, match="Supported"):
        extract(f)
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"not a pdf")
    with pytest.raises(PdfminerException):
        extract(f)


def test_missing_tesseract(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Tesseract"):
        ocr(Image.new("RGB", (10, 10)))


def test_normalized_coordinates():
    assert normalized_box([-1, 20, 200, 100], 200, 100) == [0, 200, 1000, 1000]
    with pytest.raises(ValueError):
        normalized_box([0, 0, 0, 0], 0, 1)


def test_html_and_csv_injection(tmp_path):
    result = {
        "document": "<script>bad</script>",
        "pages": [
            {
                "width": 100,
                "height": 100,
                "source": "test",
                "words": [],
                "tables": [
                    {
                        "method": "test",
                        "rows": [
                            [
                                {"text": "=1+1", "box": None},
                                {"text": "<script>", "box": None},
                            ]
                        ],
                    }
                ],
            }
        ],
    }
    export(result, tmp_path)
    assert "<script>" not in (tmp_path / "report.html").read_text()
    assert "'=1+1" in (tmp_path / "page-1-table-1.csv").read_text()


@pytest.mark.skipif(
    not shutil.which("tesseract"), reason="Tesseract executable unavailable"
)
def test_real_ocr_receipt():
    page = extract(FIX / "receipt.png")["pages"][0]
    expected = json.loads((FIX / "expected.json").read_text())["receipt"]
    assert page["source"] == "tesseract"
    assert [[c["text"] for c in r] for r in page["tables"][0]["rows"]] == expected
    assert all(w["confidence"] is not None for w in page["words"])
