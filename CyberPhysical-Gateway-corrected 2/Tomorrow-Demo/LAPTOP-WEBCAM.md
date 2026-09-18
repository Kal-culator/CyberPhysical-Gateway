# Laptop webcam + real Pi fingerprint and deadbolt

Use this Tomorrow-Demo directory, either at the repository root or inside
`CyberPhysical-Gateway-corrected 2`. Both copies include this update.
Do not run the old Java-Backend server or extract the old Tomorrow-Demo.zip over these files.

Only the ESP32-CAM is replaced. Keep the R307, LCD and relays connected to the Pi.
Relay 1/buzzer stays BCM27 (physical 13); relay 2/deadbolt stays BCM22 (physical 15).
Registered fingerprints still open locally. Unknown fingerprints request a fresh laptop
webcam photo, sent to the configured Telegram chat with YES/NO buttons. YES requests
OPEN; NO, timeout, or Telegram failure requests BUZZER. Existing MySQL logging remains.

## Update both machines

From your existing CyberPhysical-Gateway Git checkout, run `git pull` on BOTH laptop
and Pi. Preserve your own `demo_config.json` laptop address and other local settings.
If Git reports local changes, do not discard that file; resolve/preserve them before updating.
Stop the old Java server and Pi demo with Ctrl+C before restarting.

## Laptop (macOS or Linux)

From the repository root, use the folder you have been working in:

```bash
cd "CyberPhysical-Gateway-corrected 2/Tomorrow-Demo/Java-Server"
bash setup_webcam.sh
bash test_webcam.sh
```

The setup needs Python 3 with venv/pip, internet for OpenCV, and your existing Java 11+
and Maven. On Linux, install the distro's python3-venv package if venv is missing.
The test takes a real photo but does not send it. Open `webcam-test.jpg` and check the
visitor is visible. On macOS allow camera access for your terminal; if needed enable
it in System Settings > Privacy & Security > Camera and reopen the terminal.
Close Zoom/FaceTime/other apps using the webcam. To use another camera:

```bash
export WEBCAM_INDEX=1
bash test_webcam.sh
```

Default index is 0. Then start the existing server as usual:

```bash
bash run_server.sh
```

Enter the existing MySQL password, Telegram token and chat ID when prompted.
Keep this terminal open and aim the laptop webcam at the visitor. No ESP32 upload,
ESP32 power connection or camera port 8081 is required.

## Raspberry Pi

From the repository root:

```bash
cd "CyberPhysical-Gateway-corrected 2/Tomorrow-Demo"
source .venv/bin/activate
python demo.py telegram-test
python demo.py run
```

If your configured virtual environment lives elsewhere, activate that existing one.
`telegram-test` requests a webcam photo and Telegram approval without moving the lock;
then use `run` to test the actual fingerprint and deadbolt. Keep the existing laptop IP
in `demo_config.json`, with port 8080. The Pi and Java approval timeout settings must
match (default 30 seconds). The updated Pi allows another 40 seconds for capture,
upload and network cleanup; the Telegram decision window itself remains 30 seconds.

## Failure behavior

Capture is limited to eight seconds and uses a fresh temporary file, deleted afterward.
If the camera cannot capture, the existing text approval appears with a clear
“Photo unavailable” notice. A failed Telegram upload denies the attempt; there is no
automatic unlock. Photos sent successfully remain in the configured Telegram chat.
`webcam-test.jpg` stays locally until you delete it and is ignored by Git.
An accepted YES is not reversed merely because Telegram cannot update its caption.

## Offline validation

```bash
cd Java-Server
python3 test_webcam_flow.py
```

These tests use fake camera output and a local Telegram stub: no physical camera,
real Telegram messages, database changes, or lock movement. A live hardware test
is still required at the demonstration setup.
