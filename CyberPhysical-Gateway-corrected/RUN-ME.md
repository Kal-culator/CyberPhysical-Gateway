# Corrected project: what runs where

## Final Raspberry Pi pin map (BCM numbering)

| Device | BCM GPIO | Physical pin |
|---|---:|---:|
| R307 RX connected from Pi TX | 14 | 8 |
| R307 TX connected to Pi RX | 15 | 10 |
| Relay channel 1 NPN driver | 27 | 13 |
| 5V buzzer NPN driver | 23 | 16 |
| LM393 light sensor DO | 17 | 11 |
| LCD and MPU6050 SDA | 2 | 3 |
| LCD and MPU6050 SCL | 3 | 5 |

The current integrated Pi program uses the R307, relay 1, buzzer and LM393. LCD, MPU6050 and relay 2 remain available in `sensor-test-kit 2/check.py` for separate checks. Read `sensor-test-kit 2/WIRING.md` before applying power. The 12V lock current must not pass through the breadboard or a Pi GPIO.

## 1. Laptop: run the Java gateway

The laptop and Pi must be on the same network. In a terminal:

```bash
cd Java-Backend
javac GatewayServer.java SecurityAnalytics.java TelegramNotifier.java
java GatewayServer
```

This uses TCP port 8080 for Pi events and port 8081 for ESP32-CAM JPEG images. Permit these ports if the laptop firewall asks. Find the laptop's Wi-Fi IP address and use it in the Pi and ESP32 steps.

Telegram is optional. The code runs without it. The old repository contained a bot token directly in source; revoke that token in BotFather. For a replacement token, set these before `java GatewayServer`:

```bash
export TELEGRAM_BOT_TOKEN='replacement-token'
export TELEGRAM_CHAT_ID='your-chat-id'
```

## 2. Raspberry Pi: enroll once, then run the door node

Copy the corrected project to the Pi. In a Pi terminal:

```bash
cd CyberPhysical-Gateway/Pi-Client
bash setup_pi_client.sh
sudo raspi-config
```

In `raspi-config`, disable the serial login shell and enable serial hardware, then reboot. To enroll fingerprint ID 1, use the included sensor kit:

```bash
cd "../sensor-test-kit 2"
bash setup_pi.sh
source .venv/bin/activate
python check.py finger-info
python check.py enroll 1
```

Return to the Pi client and start it. Replace the example address with the laptop's actual Wi-Fi IP:

```bash
cd ../Pi-Client
source .venv/bin/activate
export GATEWAY_SERVER_IP='192.168.1.50'
export ALLOWED_FINGER_IDS='1'
export BUZZER_KIND='passive'
python main_pi.py
```

Use `BUZZER_KIND='active'` if the B-10N produces a continuous tone when briefly powered directly from a verified 5V supply. Keep `passive` if it needs a generated tone.

The Pi still unlocks locally if the Java gateway is offline. Press `Ctrl+C` to stop and command the relay and buzzer off. Test relay polarity with the lock's 12V supply disconnected before running the integrated program.

`EdgeNode.py` is an old simulated network client and is not part of the hardware run sequence.

## 3. ESP32-CAM: upload the camera firmware

Open `ESP32-Firmware/CameraNode.ino` in Arduino IDE. Install the Espressif ESP32 board package 3.x, select **AI Thinker ESP32-CAM**, then edit:

```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverIP = "192.168.1.50";
```

Use the same laptop IP used on the Pi. Upload through the ESP32-CAM-MB and open Serial Monitor at 115200 baud. The AI Thinker camera pin definitions in the sketch are fixed internal camera connections and already match the listed ESP32-CAM board.

The camera tries port 8081 every ten seconds. After the Pi reports a denied fingerprint, the Java gateway waits up to 15 seconds for the next image and performs the luminance check.

## 4. Optional individual checks

On the Pi, from `sensor-test-kit 2` with its environment active:

```bash
python check.py finger-info
python check.py match
python check.py light --seconds 10
python check.py relay 1 --actuate
python check.py buzzer --seconds 0.8 --actuate
```

Do not run `check.py` and `main_pi.py` simultaneously because they would compete for the same UART and GPIO pins.
