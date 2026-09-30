# Verification evidence

Local Windows / Python 3.11 verification:

- 13 tests passed, 1 skipped (Tesseract is not installed locally).
- Native PDF statement: exact match for all 12 expected cells; cell bounding boxes validated.
- Parenthesized expenses normalized to `-820`; original values preserved in extraction JSON.
- Local extraction generated JSON, CSV, normalized JSON and an HTML coordinate report.
- Ruff static checks passed.

The CI workflow installs Tesseract on Ubuntu, runs the real image OCR comparison (8 expected cells), runs both command-line demos and uploads reports. Its actual result is available in the linked GitHub Actions workflow; a configured workflow alone is not evidence of success.

Not run locally: Tesseract OCR; LayoutLM model inference; S3 upload. No checkpoint weights or cloud credentials are required or bundled. No training or real-document generalization study was performed. Synthetic exact matches are regression checks, not accuracy estimates.
