# Start here — Mac + Raspberry Pi + ESP32-CAM

Use **Gateway-Rebuild** throughout. Do not run the previous GatewayServer or demo.py at the same time. This guide assumes the ZIP is extracted to `~/Gateway-Rebuild` on each computer (the home folder). The Pi does not need its OS reflashed.

## 0. Electrical conditions before software

- Relay VCC is 5V, not 3.3V. On your photographed board the missing **RY-VCC ↔ VCC jumper** must remain installed; do not bridge GND.
- Two BC547 drivers: Pi BCM27/physical13 → relay IN1 (buzzer); BCM22/physical15 → relay IN2 (deadbolt). The configured `relay_active_high: true` assumes these NPN drivers and active-low relay inputs.
- Keep the **12V adapter unplugged** until the relay tests pass and the exposed screw-terminal conductors are secured.
- A 5V LCD backpack must not expose the Pi SDA/SCL pins to 5V. Use a proper I²C shifter or verified 3.3V-safe interface. To proceed without the LCD, disconnect its four wires with all power off and set `lcd_enabled` to `false`. The client then prints messages in the terminal. Supplying a compatible backpack at 3.3V is only a provisional alternative; some LCDs won't work.
- Measure the LM2596 output at **5.0V before connecting the camera**. Never parallel its 5V output with Pi power or camera USB power.
- The code cannot correct a swapped relay channel or confirm that a physical bolt moved.

## 1. MAC — unpack and check Java/MySQL

Extract the ZIP and move `Gateway-Rebuild` into your home folder. In Mac Terminal:

```bash
cd ~/Gateway-Rebuild
java -version
mysql --version
```

Java must be **17 or newer**. Use your existing working MySQL installation. If either command is missing, install that prerequisite first. The downloadable ZIP includes a prebuilt server, so Maven is only needed when compiling from source. Optional Homebrew installation for a Mac that has none of these: `brew install openjdk@17 maven mysql` (follow Homebrew's PATH instructions; do not install a second MySQL instance over an existing one).

Find your Mac Wi-Fi IPv4 address:

```bash
ipconfig getifaddr en0
```

If blank, use System Settings → Wi-Fi → Details → TCP/IP. Mac, Pi and ESP32-CAM must share a network; the ESP32-CAM needs 2.4GHz. Guest-network client isolation can block them.

## 2. MAC — make the new database (keeps the old one)

With MySQL running:

```bash
cd ~/Gateway-Rebuild
mysql -u root -p < database/bootstrap.sql
```

Type your MySQL password (not necessarily the Mac password). This creates only `cyberphysical_v2`. It does not change `smart_door_demo` or require deleting its tables.

For the quickest local demo you can configure the server to use your existing MySQL `root` user. For a separate account, uncomment and customize the optional CREATE USER / GRANT lines in bootstrap.sql, then run them once. The server creates versioned tables on its first successful startup.

## 3. MAC — configure all three devices

Stop the OLD Java server so it is not polling the same Telegram bot. In Telegram, open your own bot, press Start and send hello (not to BotFather).

If you need your chat/owner IDs:

```bash
python3 tools/telegram_chat.py
```

It reads existing bot messages; no message is sent by this helper. For a private chat the chat ID and owner user ID are normally the same; use the values it prints.

Run:

```bash
python3 tools/configure.py
```

Enter the Mac's IPv4, MySQL username/password, bot token, chat ID, owner ID, and camera Wi-Fi name/password. Type `root` if you are using your existing root account. Blank bot token is allowed, but unknown fingerprints will then be denied without approval.

The helper creates:

- `server/config.properties` — Java/MySQL/Telegram secrets.
- `pi/config.json` — Pi settings with the same generated API key.
- `camera/CameraNode/Secrets.h` — Wi-Fi/server/API key for camera flashing.

They stay local and are ignored by Git. Do not rerun the helper casually: it rotates the API key, so you must recopy Pi config and reflash the camera afterward. To change only the Mac IP, edit `server_url` in Pi config and `SERVER_URL` in Secrets.h, then reflash the camera; the server can keep its current key.

## 4. MAC — start Java

```bash
cd ~/Gateway-Rebuild/server
bash start.sh
```

Expected: **Gateway V2 listening on port 8080 — MySQL connected**. Leave this terminal open. If port 8080 is already in use, stop the old server. Allow Java incoming connections in the macOS firewall on your demo network.

The first startup creates sample authorized fingerprint ID 1, named Demo User. It does NOT enroll the physical fingerprint sensor.

Dashboard: open `http://localhost:8080` on the Mac. Copy the value after `api.token=` in your local `server/config.properties` into its API-key box. It is kept in page memory, not in the URL or browser storage. Never screenshot the key.

## 5. PI — copy files and install

Copy the extracted project to the Pi home folder, named `Gateway-Rebuild`. Include the generated **pi/config.json**. Your Mac's server credentials and camera Secrets.h do not need to be copied to the Pi.

One option from the Mac (replace `PI_IP` with the actual Pi address):

```bash
ssh myrasp123@PI_IP 'mkdir -p ~/Gateway-Rebuild'
scp -r ~/Gateway-Rebuild/pi myrasp123@PI_IP:~/Gateway-Rebuild/
```

These commands run on the Mac; the following run in the Pi terminal:

```bash
cd ~/Gateway-Rebuild/pi
bash setup.sh
sudo raspi-config
```

In Interface Options: enable I2C; Serial login shell **No**, serial hardware **Yes**. Reboot if changed:

```bash
sudo reboot
```

After reconnecting:

```bash
cd ~/Gateway-Rebuild/pi
source .venv/bin/activate
python gateway.py config-check
readlink -f /dev/serial0
i2cdetect -y 1
```

Expect `27` for the LCD and `68` for MPU with AD0 grounded. Use the UART actually mapped to pins 8/10. If `/dev/serial0` resolves to your working `/dev/ttyAMA0`, leave it. Do not change serial overlays or disable Bluetooth just because the device name differs.

## 6. PI — independent sensor checks

Run one at a time:

```bash
python gateway.py lcd-test
python gateway.py finger-info
python gateway.py mpu-test
python gateway.py status
```

`status` reports each module separately. A fingerprint failure does not block `relay-test`.

`mpu-test` prints acceleration in g and rotation in degrees/second for six seconds. Gently tilt the housing. One acceleration axis near ±1g at rest is normal.

If ID 1 is already your finger, keep it. Otherwise:

```bash
python gateway.py enroll 1
```

Only to explicitly replace an existing ID 1:

```bash
python gateway.py delete 1 --confirm
python gateway.py enroll 1
```

Enrollment stores the template in the R307. SQL stores an ID/name/authorization record, not the fingerprint. For another ID, enroll on the Pi AND add that same ID using `database/users.sql` on the Mac. Deleting/reassigning a sensor ID should be accompanied by updating its SQL mapping.

## 7. PI — relay checks with 12V unplugged

```bash
python gateway.py relay-test 1 --confirm
python gateway.py relay-test 2 --confirm
```

First: buzzer sounds briefly. Second: deadbolt relay clicks only. Both finish off. If the buzzer rings on test 2, the channels/load terminal groups are swapped. If LED lights without a click, check the RY-VCC jumper and actual 5V coil supply.

Only after these pass: power everything off, check lock power/diode connections and exposed wires, then power Pi and 12V with the mock door open.

```bash
python gateway.py lock-test --confirm
```

The bolt should retract for 0.5 seconds and return. Do not lengthen this beyond the lock's duty rating; the client rejects pulses over 1 second. There is no physical door/bolt position feedback.

## 8. MAC — flash ESP32-CAM

Disconnect LM2596 power from the camera. Use its ESP32-CAM-MB USB programmer and a USB data cable.

1. Arduino IDE: install **esp32 by Espressif Systems**, core **3.x**. This sketch was compiled with **3.3.8**.
2. Open `camera/CameraNode/CameraNode.ino`; keep the generated `Secrets.h` beside it.
3. Board: **AI Thinker ESP32-CAM**. Select the programmer's USB port. Upload speed 115200 is a useful conservative choice.
4. Click Upload. If stuck at Connecting, hold IO0/BOOT while resetting; if your programmer has no boot button, connect GPIO0 to GND with power off, power/reset and upload. Remove GPIO0–GND after upload and reset.
5. Serial Monitor at **115200** should show `Camera upload HTTP 200` every few seconds while Java is running. HTTP 401 means an API-key mismatch; negative codes usually mean network/server failure.
6. For normal use, disconnect USB power before reconnecting the measured 5V LM2596 output. No Pi GPIO wires go to the camera.

The camera now uploads to **port 8080**, not the old 8081. Do not use the old camera firmware with this server.

## 9. PI — server and Telegram tests (no relay activation)

```bash
python gateway.py server-test
python gateway.py telegram-test
```

The Telegram test generates an approval request. Tap Approve, rerun and tap Deny, then rerun and let it expire. It prints the result but never activates a relay. Camera photos are sent separately if a fresh image is available. A camera failure does not prevent the text buttons from working.

The 30-second timer includes message/network delay. If you answer after expiry the server refuses the reply. Run only one Java server for the bot. Check the built-in dashboard for logged decisions.

## 10. PI — full fingerprint demonstration

```bash
python gateway.py run
```

- Registered, database-authorized ID with sufficient confidence → access granted → relay 2 pulse.
- Unknown/revoked/low-confidence finger → Telegram → Approve opens; Deny or expiry sounds buzzer.
- Poor-quality scan → lift and retry (no automatic intruder classification).
- Server/database unavailable → denied; no offline unlocking.
- Remove the finger before the next attempt. Hold a finger down to verify it does not repeatedly trigger.

Stop using **Ctrl+C**. On restart, activate `.venv` again. No automatic startup service is installed, so you stay in control of bench tests.

## 11. Enable motion/camera tamper demonstration after basic access works

Motion: stop `run`, edit Pi `config.json` to `"mpu_enabled": true`, keep the housing stationary and restart. It takes an initial baseline. Sustained motion or high rotation raises a warning, sounds the buzzer, notifies Telegram and cancels pending approvals. Tune `motion_delta_g`, `motion_gyro_dps`, `motion_samples` to your mounting. The initial values are starting points, not calibrated measurements.

Camera: stop Java, set `camera.monitor=true` in server/config.properties and restart. Give the camera up to 30 seconds to boot. Cover the lens: four consecutive frames below brightness 18 raise a warning. A gap of over 15 seconds raises camera-offline after startup grace. View measured brightness on the dashboard and adjust for your lighting. Camera checks can alarm for a dark room or a Wi-Fi outage; they cannot distinguish those from deliberate tampering.

Start the Pi client after enabling the server camera monitor. Alerts have a cooldown to avoid continuous buzzer/messages. Successful lock actuation can mechanically shake the MPU; mounting and thresholds need real testing. This version does not silently suppress that motion.

## Before publishing to your new GitHub repository

The local project is Git-ready but has not been published to your account. Create a new empty repository, then add its remote and push the source. Do not include local configs, credentials, backups, `.venv`, build caches or compiled secret-bearing camera binaries. The `.gitignore` covers the generated settings. Users cloning source need Maven to build Java; users of the provided ZIP have the prebuilt JAR.
