#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

if [[ -z "${DB_PASSWORD:-}" ]]; then
  read -r -s -p 'MySQL password for root: ' DB_PASSWORD
  echo
  export DB_PASSWORD
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  read -r -s -p 'Telegram bot token: ' TELEGRAM_BOT_TOKEN
  echo
  export TELEGRAM_BOT_TOKEN
fi

if [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  read -r -p 'Telegram private chat ID: ' TELEGRAM_CHAT_ID
  export TELEGRAM_CHAT_ID
fi

export DB_USER="${DB_USER:-root}"
export DB_URL="${DB_URL:-jdbc:mysql://localhost:3306/smart_door_demo?serverTimezone=UTC}"
export APPROVAL_TIMEOUT_SECONDS="${APPROVAL_TIMEOUT_SECONDS:-30}"
export WEBCAM_PYTHON="${WEBCAM_PYTHON:-$PWD/.webcam-venv/bin/python}"
export WEBCAM_SCRIPT="${WEBCAM_SCRIPT:-$PWD/capture_webcam.py}"
if [[ ! -x "$WEBCAM_PYTHON" ]]; then
  echo 'Run bash setup_webcam.sh and bash test_webcam.sh first.' >&2
  exit 1
fi
mvn -q compile exec:java
