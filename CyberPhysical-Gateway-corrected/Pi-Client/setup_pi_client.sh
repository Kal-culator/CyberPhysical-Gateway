#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Run this on the Raspberry Pi.' >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-rpi.gpio
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install 'pyserial>=3.5,<4' 'adafruit-circuitpython-fingerprint==2.2.25'

echo 'Pi packages installed.'
echo 'Next run: sudo raspi-config'
echo 'Interface Options -> Serial: login shell NO, serial hardware YES; then reboot.'
