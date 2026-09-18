#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
"${WEBCAM_PYTHON:-$PWD/.webcam-venv/bin/python}" capture_webcam.py --index "${WEBCAM_INDEX:-0}" --output webcam-test.jpg
echo "Check $PWD/webcam-test.jpg before the demonstration. No photo was sent."
