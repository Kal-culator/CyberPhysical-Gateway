# CyberPhysical Gateway

## Current demonstration: Gateway-Rebuild

The fresh, standalone project is in **[Gateway-Rebuild](Gateway-Rebuild/README.md)**. Older files remain available for reference; do not mix old and new client/server/firmware versions.

- **[Download the complete ZIP](https://github.com/Kal-culator/CyberPhysical-Gateway/raw/refs/heads/main/Gateway-Rebuild.zip)** — includes the prebuilt Java server and all source files.
- **[Start here: numbered Mac, Pi and camera instructions](Gateway-Rebuild/START-HERE.md)**
- **[Physical pins and breadboard wiring](Gateway-Rebuild/docs/WIRING.md)**
- **[Validation and remaining hardware checks](Gateway-Rebuild/docs/VALIDATION.md)**

If you already cloned this repository on the Pi:

```bash
cd ~/CyberPhysical-Gateway
git pull --ff-only
cd Gateway-Rebuild/pi
bash setup.sh
```

Complete the Mac configuration step in the guide, then copy the generated `pi/config.json` into this Pi folder before network tests. Secrets are deliberately excluded from Git. If following the guide directly from this repository rather than extracting the ZIP to your home folder, replace `~/Gateway-Rebuild` with `~/CyberPhysical-Gateway/Gateway-Rebuild` in its commands.

For a source checkout, build the Java server with Maven (`cd Gateway-Rebuild/server && mvn package`), then run `bash start.sh`. Alternatively, extract the complete ZIP into your home folder; it already includes the runnable server JAR. All devices use the new server on HTTP port 8080.

The new MySQL database is `cyberphysical_v2`; the old `smart_door_demo` database is not modified. Verify physical wiring, power and relay behavior before live lock operation. Automated software checks passed; live hardware/MySQL/Telegram commissioning remains required.
