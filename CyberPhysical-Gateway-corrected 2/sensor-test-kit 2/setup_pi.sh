#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Run this installer on your Raspberry Pi, not on a Mac/PC.' >&2
  exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
  echo 'Run: bash setup_pi.sh  (without sudo; it asks for sudo when needed).' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-gpiozero python3-lgpio i2c-tools
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
echo 'Installed. Next: sudo raspi-config'
echo 'Interface Options: enable I2C; Serial Port: login shell NO, serial hardware YES.'
echo 'Reboot if you changed interfaces. Read START-HERE.md and match config.json to your wiring.'
