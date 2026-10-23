# CyberPhysical Gateway — clean rebuild

This project is a separate replacement for the earlier Tomorrow-Demo / Final-Release code. Do not mix files between them. The old repository and database are not modified.

**Start with [START-HERE.md](START-HERE.md).** It gives numbered steps for Mac, Raspberry Pi and camera. [WIRING.md](docs/WIRING.md) records the assigned physical pins and breadboard rows.

## What it does

- R307 fingerprint enrollment, listing and explicit deletion, using the existing UART wiring.
- 20×4 LCD messages, optional console-only operation while LCD wiring is corrected.
- Relay 1 buzzer (BCM27 / physical 13); relay 2 deadbolt (BCM22 / physical 15), through two BC547 drivers.
- Dedicated `relay-test` and `lock-test` commands independent of LCD/fingerprint.
- Java 17+ HTTP server and a new MySQL database, `cyberphysical_v2`.
- Database authorization for registered IDs; an unknown, revoked or low-confidence fingerprint requires owner approval.
- Telegram approval/denial, authenticated against BOTH configured chat and owner. A request expires after 30 seconds from creation, including network delay. A late reply cannot unlock.
- Camera JPEG uploads over Wi-Fi, latest fresh photo attached separately to a Telegram request.
- MPU movement and missing-MPU alerts when enabled; camera darkness/offline alerts when enabled.
- A built-in read-only dashboard at the server address. It records **decisions**, not physical bolt-position confirmation.
- No fingerprint image/template is sent to the server. SQL stores only the sensor ID and access metadata.

## Behavior on failures

The full demo requires the server. Server/auth/database errors deny access; there is no silent offline unlock. A poor-quality finger scan asks for a retry instead of reporting it as an intruder. Output pulses are bounded and use cleanup on normal exceptions/interruption. Power loss or OS/process failure is not a software-guaranteed emergency shutoff: keep the hardware pull-down resistors and correct relay polarity.

Tamper alerts deny pending approvals, briefly inhibit new openings and pulse the buzzer. Motion and camera monitoring default OFF until calibrated. Darkness can also mean a dark room; MPU motion can mean an ordinary door movement. Those are demonstration heuristics, not proof of an attack. Fingerprint communications failure stops the running demo with outputs off. An LCD write failure also stops the demo; LCD removal is not independently monitored continuously.

## Layout

| Folder | Runs on / purpose |
|---|---|
| `pi/` | Raspberry Pi Python client and independent hardware tests |
| `server/` | Mac Java server; prebuilt JAR also supplied in the ZIP |
| `camera/CameraNode/` | AI Thinker ESP32-CAM Arduino sketch |
| `database/` | New database bootstrap and user administration examples |
| `tools/` | Private configuration helper, Telegram ID helper, integration tests |
| `docs/` | Wiring, protocol, test results, troubleshooting |

## Secrets and network

`tools/configure.py` generates a shared random API key and local settings. Real configuration files and their backups are Git-ignored. Copy `pi/config.json` privately to the Pi; a normal Git clone does not include it. Never commit your bot token, Wi-Fi password, DB password or `Secrets.h`.

Use only on your trusted demo LAN; this build uses HTTP between your own devices, not Internet-facing TLS. Do not forward port 8080 from a router. Telegram itself uses HTTPS. Treat any holder of the shared API key as a trusted device. This is a student demonstration, not a production access-control installation.

## Development verification

```
cd server
mvn test
mvn package
cd ..
python3 -m unittest discover -s pi/tests -v
python3 tools/smoke_test.py
```

The smoke test starts a local Java server with a disposable H2 SQL database in simulation mode. It sends no Telegram messages and touches no hardware. Simulation decisions cannot be consumed by a real Pi client. Real deployment uses MySQL. See [validation results](docs/VALIDATION.md) for what was and was not physically verified.
