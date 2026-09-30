import html
import json
from pathlib import Path

import pandas as pd

from .core import clean_number


def export(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "document.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    sections = []
    for pi, page in enumerate(result["pages"], 1):
        boxes = []
        for word in page["words"]:
            x0, y0, x1, y1 = word["box"]
            boxes.append(
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}"/><text x="{x0}" y="{y1}" font-size="{max(6, (y1 - y0) * 0.8)}">{html.escape(word["text"])}</text>'
            )
        sections.append(
            f'<h2>Page {pi} · {html.escape(page["source"])}</h2><svg viewBox="0 0 {page["width"]} {page["height"]}">{"".join(boxes)}</svg>'
        )
        for ti, table in enumerate(page["tables"], 1):
            rows = [[cell["text"] for cell in row] for row in table["rows"]]
            # Quote formula-like values for spreadsheet consumers; JSON retains raw text.
            safe = [
                [
                    "'" + v if v.startswith(("=", "+", "-", "@", "\t", "\r")) else v
                    for v in row
                ]
                for row in rows
            ]
            pd.DataFrame(safe).to_csv(
                directory / f"page-{pi}-table-{ti}.csv", index=False, header=False
            )
            normalized = [[clean_number(v) for v in row] for row in rows]
            sections.append(
                f"<h3>Table {ti} · {html.escape(table['method'])}</h3>"
                + pd.DataFrame(rows).to_html(index=False, header=False, escape=True)
            )
            (directory / f"page-{pi}-table-{ti}.normalized.json").write_text(
                json.dumps(normalized, indent=2), encoding="utf-8"
            )
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>LayoutLens extraction report</title>
<style>body{background:#101c2c;color:#e2ebf7;font:16px system-ui;max-width:1050px;margin:40px auto;padding:24px}h1{font-size:48px;margin-bottom:8px}p{color:#afc4da}svg{background:white;width:100%;max-height:650px;border-radius:12px}rect{fill:#ddf7f3;stroke:#319c8b;stroke-width:.5}text{fill:#142438}table{border-collapse:collapse;width:100%;background:#1b3047}td{padding:12px;border:1px solid #49617c}h2{margin-top:40px}</style>
<h1>LayoutLens</h1><p>Document structure, made inspectable. Coordinate-preserving baseline extraction.</p>"""
    page += (
        "<p>"
        + html.escape(result["document"])
        + " · Review required</p>"
        + "".join(sections)
        + "</html>"
    )
    (directory / "report.html").write_text(page, encoding="utf-8")
