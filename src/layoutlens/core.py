from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber
from PIL import Image


@dataclass
class Word:
    text: str
    box: list[float]
    confidence: float | None = None


def normalized_box(box, width, height):
    if width <= 0 or height <= 0:
        raise ValueError("Page dimensions must be positive")
    return [
        max(0, min(1000, round(v / (width if i % 2 == 0 else height) * 1000)))
        for i, v in enumerate(box)
    ]


def clean_number(value):
    """Conservative US-style financial normalization; preserve other strings."""
    s = value.strip()
    if not re.fullmatch(r"\(?-?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?", s):
        return value
    if s.startswith("(") != s.endswith(")"):
        return value
    try:
        return str(
            Decimal(s.replace("$", "").replace(",", "").strip("()"))
            * (-1 if s.startswith("(") else 1)
        )
    except InvalidOperation:
        return value


def ocr(image: Image.Image, timeout=60):
    executable = shutil.which("tesseract")
    if not executable:
        raise RuntimeError(
            "Tesseract is required for images/scanned pages. Install it and add it to PATH."
        )
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    result = subprocess.run(
        [executable, "stdin", "stdout", "--psm", "6", "tsv"],
        input=buf.getvalue(),
        capture_output=True,
        timeout=timeout,
        check=True,
    )
    words = []
    for row in csv.DictReader(
        io.StringIO(result.stdout.decode("utf-8")), delimiter="\t"
    ):
        if row["text"].strip() and float(row["conf"]) >= 0:
            x, y, w, h = [int(row[k]) for k in ("left", "top", "width", "height")]
            words.append(
                Word(row["text"], [x, y, x + w, y + h], float(row["conf"]) / 100)
            )
    return words


def spatial_tables(words, row_tolerance=8, gap=24):
    """Heuristic for aligned, borderless rows; no semantic model claims."""
    rows = []
    for word in sorted(words, key=lambda w: (w.box[1], w.box[0])):
        if not rows or abs(word.box[1] - rows[-1][0].box[1]) > row_tolerance:
            rows.append([word])
        else:
            rows[-1].append(word)
    candidates = []
    for row in rows:
        cells = []
        for word in sorted(row, key=lambda w: w.box[0]):
            if cells and word.box[0] - cells[-1]["box"][2] <= gap:
                cells[-1]["text"] += " " + word.text
                cells[-1]["box"][2] = word.box[2]
                cells[-1]["box"][3] = max(cells[-1]["box"][3], word.box[3])
            else:
                cells.append({"text": word.text, "box": word.box.copy()})
        candidates.append(cells)
    groups, active = [], []
    for cells in candidates:
        matches = (
            active
            and len(cells) == len(active[-1])
            and all(
                abs(a["box"][0] - b["box"][0]) <= 18
                for a, b in zip(cells, active[-1], strict=True)
            )
            and cells[0]["box"][1] - active[-1][0]["box"][3] < 50
        )
        if not matches:
            if len(active) >= 2:
                groups.append(active)
            active = []
        if len(cells) >= 2:
            active.append(cells)
    if len(active) >= 2:
        groups.append(active)
    return [{"method": "spatial-row-baseline", "rows": g} for g in groups]


def extract(path: Path, max_pages=30, max_bytes=25_000_000, force_ocr=False):
    path = Path(path)
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if path.stat().st_size > max_bytes:
        raise ValueError("Document exceeds the input byte limit")
    pages = []
    if path.suffix.lower() == ".pdf":
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise ValueError("Document exceeds the page limit")
            for page in pdf.pages:
                native = page.extract_words()
                tables = []
                if native and not force_ocr:
                    words = [
                        Word(w["text"], [w["x0"], w["top"], w["x1"], w["bottom"]])
                        for w in native
                    ]
                    width, height, source = page.width, page.height, "pdf-text"
                    for table in page.find_tables():
                        rows = []
                        texts = table.extract()
                        for ri, row in enumerate(table.rows):
                            rows.append(
                                [
                                    {
                                        "text": texts[ri][ci] or "",
                                        "box": list(box) if box else None,
                                    }
                                    for ci, box in enumerate(row.cells)
                                ]
                            )
                        tables.append({"method": "pdf-vector-grid", "rows": rows})
                else:
                    if page.width * page.height * (150 / 72) ** 2 > 30_000_000:
                        raise ValueError("Rendered page exceeds 30 megapixels")
                    image = page.to_image(resolution=150).original
                    width, height = image.size
                    words, source = ocr(image), "tesseract"
                pages.append(pack_page(words, tables, width, height, source))
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) > 1:
                raise ValueError(
                    "Multi-frame images are unsupported; split frames before extraction"
                )
            width, height = image.size
            if width * height > 30_000_000:
                raise ValueError("Image exceeds 30 megapixels")
            pages.append(pack_page(ocr(image), [], width, height, "tesseract"))
    else:
        raise ValueError("Supported inputs: PDF, PNG, JPEG, single-frame TIFF")
    return {
        "schema_version": "1.0",
        "document": path.name,
        "pages": pages,
        "warnings": [
            "Baseline output requires review; merged cells and complex reading order may be incomplete."
        ],
    }


def pack_page(words, tables, width, height, source):
    return {
        "width": width,
        "height": height,
        "coordinate_system": "top-left pixels"
        if source == "tesseract"
        else "top-left PDF points",
        "source": source,
        "words": [asdict(w) for w in words],
        "tables": tables or spatial_tables(words),
    }
