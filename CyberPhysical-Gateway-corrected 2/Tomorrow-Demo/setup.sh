#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Run this setup script on the Raspberry Pi.' >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-gpiozero python3-lgpio i2c-tools
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt

echo 'Setup complete.'
echo 'Use raspi-config to enable I2C and the serial hardware, with serial login disabled.'
