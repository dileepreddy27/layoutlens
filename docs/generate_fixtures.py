import json

# Create original synthetic fixtures without external data.
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "fixtures"
ROOT.mkdir(exist_ok=True)
rows = [
    ["Account", "2025", "2026"],
    ["Revenue", "1,250", "1,480"],
    ["Expenses", "(820)", "(910)"],
    ["Net income", "430", "570"],
]
commands = ["BT /F1 20 Tf 45 750 Td (NORTHSTAR | Synthetic financial statement) Tj ET"]
for y in [690, 650, 610, 570, 530]:
    commands.append(f"45 {y} m 555 {y} l S")
for x in [45, 255, 405, 555]:
    commands.append(f"{x} 530 m {x} 690 l S")
for ri, row in enumerate(rows):
    for x, text in zip([55, 265, 415], row, strict=True):
        escaped = text.replace("(", r"\(").replace(")", r"\)")
        commands.append(f"BT /F1 12 Tf {x} {665 - ri * 40} Td ({escaped}) Tj ET")
commands.append(
    "BT /F1 11 Tf 45 490 Td (Original synthetic fixture. Not an actual company's financial data.) Tj ET"
)
stream = "\n".join(commands).encode()
objects = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length "
    + str(len(stream)).encode()
    + b" >>\nstream\n"
    + stream
    + b"\nendstream",
]
data = b"%PDF-1.4\n"
offsets = [0]
for i, obj in enumerate(objects, 1):
    offsets.append(len(data))
    data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
xref = len(data)
data += b"xref\n0 6\n0000000000 65535 f \n"
data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
(ROOT / "statement.pdf").write_bytes(data)
image = Image.new("RGB", (1200, 700), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.load_default(size=32)
for i, row in enumerate(
    [
        ["Item", "Amount"],
        ["Services", "120.00"],
        ["Supplies", "35.00"],
        ["Total", "155.00"],
    ]
):
    for x, text in zip([80, 700], row, strict=True):
        draw.text((x, 100 + i * 90), text, font=font, fill="black")
image.save(ROOT / "receipt.png")

(ROOT / "expected.json").write_text(
    json.dumps(
        {
            "statement": rows,
            "receipt": [
                ["Item", "Amount"],
                ["Services", "120.00"],
                ["Supplies", "35.00"],
                ["Total", "155.00"],
            ],
        },
        indent=2,
    )
)

