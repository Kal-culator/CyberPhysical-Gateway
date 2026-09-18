#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -m venv .webcam-venv
.webcam-venv/bin/python -m pip install -r webcam-requirements.txt
echo 'Webcam installed. Run: bash test_webcam.sh'
