import argparse
import json
import sys
from pathlib import Path

from .core import extract
from .export import export


def main():
    parser = argparse.ArgumentParser(
        description="Extract auditable document tables and coordinates"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    parse = sub.add_parser("extract")
    parse.add_argument("input", type=Path)
    parse.add_argument("--out", type=Path, required=True)
    parse.add_argument("--force-ocr", action="store_true")
    parse.add_argument("--max-pages", type=int, default=30)
    features = sub.add_parser("features")
    features.add_argument("document", type=Path)
    features.add_argument("--checkpoint", required=True)
    features.add_argument("--out", type=Path, required=True)
    upload = sub.add_parser("upload")
    upload.add_argument("document", type=Path)
    upload.add_argument("--bucket", required=True)
    upload.add_argument("--key", required=True)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            result = extract(
                args.input, max_pages=args.max_pages, force_ocr=args.force_ocr
            )
            export(result, args.out)
            print(f"Extracted {len(result['pages'])} pages into {args.out}")
        elif args.command == "features":
            from .adapters import layoutlm_features

            result = json.loads(args.document.read_text(encoding="utf-8"))
            args.out.write_text(
                json.dumps(
                    [layoutlm_features(p, args.checkpoint) for p in result["pages"]]
                ),
                encoding="utf-8",
            )
        else:
            from .adapters import upload_json

            print(upload_json(args.document, args.bucket, args.key))
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports adapter failures
        print(f"LayoutLens: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
