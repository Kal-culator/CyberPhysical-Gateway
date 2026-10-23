#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -f config.properties ]]; then echo 'Run: python3 ../tools/configure.py' >&2; exit 1; fi
if ! command -v java >/dev/null; then echo 'Install JDK 17 or newer.' >&2; exit 1; fi
if [[ ! -f target/gateway-server-1.0.0.jar ]]; then
  if ! command -v mvn >/dev/null; then echo 'Install Maven, then run this again.' >&2; exit 1; fi
  mvn -q package
fi
exec java -jar target/gateway-server-1.0.0.jar config.properties
