# Validation — 23 October 2026

## Completed locally

- Java server compiled with JDK 25 using `--release 17`; runnable shaded JAR includes its dependencies.
- **14 Java unit tests passed**: known/unknown and low-confidence access, immediate owner reply, denial, timeout/late reply, tamper cancellation, restart replay rejection, database revocation/failure, same-door concurrency, deleted sample-user preservation, notification deduplication, callback owner/chat verification, camera darkness persistence/freshness/invalid JPEG.
- **10 Python tests passed**: configuration parsing and pulse bounds, motion persistence, cleanup after interruption, tamper denial, action validation, simulation isolation, generated shared settings, secret-file permissions and Java-property escaping.
- HTTP integration test passed using the real Java HTTP server and Python API client, with disposable H2 SQL in MySQL compatibility mode. Verified missing-key rejection, registered access, approve/deny, duplicate replies, expiry, tamper cancellation, event persistence, and refusal of simulation responses by the physical client.
- ESP32-CAM sketch compiled with ESP32 Arduino **3.3.8**, board `esp32:esp32:esp32cam`. Flash use: **1,042,453 bytes / 3,145,728 (33%)**. Global RAM: **59,840 / 327,680 (18%)**. Build used placeholder Wi-Fi/API values; no hardware was flashed.
- Arduino's installed Intel-only ctags could not run on this Apple Silicon execution environment. For compilation verification, an ARM-native copy of Arduino ctags was built in the temporary work area, with a macro compatibility fix. The installed Arduino application/toolchain was not altered. If your IDE reports `bad CPU type in executable` for ctags, that is a host-toolchain issue, not a sketch error; use a compatible tool or supported Intel translation before compiling.
- Shell scripts passed syntax checks. Python source passed compile checks. Pinned Pi package versions were confirmed downloadable.

## Not claimed / still required on your devices

- No live Raspberry Pi, GPIO, LCD, R307, MPU, relay, solenoid or camera measurements.
- No real Telegram message sent; sender/chat checks and decision timing were tested with fixtures/simulation. Your bot configuration and network must be checked using telegram-test.
- No live MySQL credentials used or existing database modified. SQL behavior was tested against H2 compatibility mode, not a running MySQL instance. Bootstrap the dedicated MySQL database, start the server and confirm a real event before the demo.
- No proof of 5V LCD I²C protection, relay wiring correctness, power adequacy, deadbolt duty rating or physical motion. Resolve the wiring conditions in START-HERE before load tests.
- Motion/brightness thresholds need calibration. Darkness/offline/motion are possible tamper indicators, not reliable attribution of malicious behavior.
- Not a production security audit. Use the build on a trusted local demo network only.

## Reproduce

```bash
cd server
mvn package
cd ..
python3 -m unittest discover -s pi/tests -v
python3 tools/smoke_test.py
```

Camera compilation requires Arduino ESP32 core 3.x and a local Secrets.h. Do not publish a binary containing real Wi-Fi/API secrets.
