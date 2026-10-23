#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Run this script on the Raspberry Pi, not the laptop.' >&2; exit 1
fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-gpiozero python3-lgpio i2c-tools
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -f config.json ]]; then cp config.example.json config.json; fi
printf '%s\n' 'Setup complete. Enable I2C and serial hardware in raspi-config; disable serial login.' 'Configure config.json before network tests. Existing settings were preserved.'
