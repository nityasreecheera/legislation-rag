#!/usr/bin/env bash
# One-command setup: environment, dependencies, OCR engine, and index.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> virtualenv"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

if ! command -v tesseract >/dev/null 2>&1; then
  echo "==> installing tesseract (needed for the image-only CEA report)"
  if command -v brew >/dev/null 2>&1; then brew install tesseract
  else echo "    Install Tesseract manually: https://tesseract-ocr.github.io/"; exit 1; fi
fi

echo "==> extracting text (OCR on 27 pages, ~2 min)"
.venv/bin/python src/ingest.py
echo "==> chunking"
.venv/bin/python src/chunk.py
echo "==> embedding + indexing (~2 min)"
.venv/bin/python src/index.py

echo
echo "Done. Add an API key to .env (see .env.example), then:"
echo "  .venv/bin/python src/chat.py"
