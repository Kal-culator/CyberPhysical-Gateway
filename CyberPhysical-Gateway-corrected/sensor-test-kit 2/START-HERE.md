# Quick sensor checks — Raspberry Pi 3B+

All sensor tests run on the Pi. The ESP32-CAM runs the included Arduino sketch and sends camera images over Wi-Fi. Its CAM-MB USB board is a serial programmer/power interface, not a USB webcam.

**Match `config.json` to your existing GPIO wiring before running any output test.** The defaults below are an example mapping, not a measurement of your current wiring. Read `WIRING.md` first: the Pi inputs accept 3.3V, and the relay/buzzer defaults assume transistor drivers. GPIO numbers in the code are BCM numbers.

## 1. Install once, on the Pi

Extract the ZIP, open a terminal **inside the extracted `sensor-test-kit` folder**, then run:

```bash
bash setup_pi.sh
sudo raspi-config
```

In Interface Options:

- Enable **I2C**.
- For **Serial Port**, answer **No** to a login shell over serial, then **Yes** to enabling the serial hardware.
- Reboot if you changed these settings.

After reboot, open a terminal in the same folder:

```bash
source .venv/bin/activate
i2cdetect -y 1
nano config.json
```

Typical addresses: LCD `27` or `3f`; MPU6050 `68` or `69`. Set the actual values in `config.json` as strings such as `"0x3f"`. The LCD driver assumes the usual four-wire I2C PCF8574 backpack on your listed display.

If the serial, GPIO or I2C devices report permission denied, add your Pi login account to the necessary groups, then log out and back in:

```bash
sudo usermod -aG gpio,i2c,dialout "$USER"
```

Do not run every diagnostic under sudo to hide a missing group or wrong virtual environment.

## 2. Fast test order

Run these one at a time. Stop any older hardware script or server first so it does not compete for the UART/GPIO/I2C bus.

```bash
python check.py all
python check.py lcd
python check.py mpu --seconds 10
python check.py light --seconds 10
python check.py finger-info
```

`all` checks LCD communication, one MPU sample, light DO and the fingerprint connection/library. It also checks the camera if `camera_url` is configured. **It never creates relay or buzzer outputs.** A successful communication report is not proof of a working display, changing LDR, audible buzzer or moving bolt.

Expected observations:

| Test | What you should see |
|---|---|
| LCD | Four different rows appear. Adjust the small contrast potentiometer if backlight is on but characters are invisible. |
| MPU6050 | At rest, acceleration magnitude is roughly 1g and gyro values are near zero, with some bias. Tilt/rotate it and values should change. Reported temperature is chip temperature, not a calibrated room thermometer. |
| Light | Cover/uncover the LDR. `raw_do` should change between 0 and 1 after adjusting the module's threshold potentiometer. Set `light_dark_level` to whichever value you observe when covered. It is not a lux or percentage reading. |
| Fingerprint info | Capacity and the list of stored slot IDs. Existing fingerprints are not erased. |

### Relay and buzzer

First disconnect the 12V lock from the relay contacts. Confirm the GPIOs, input interface and polarity in `WIRING.md`, then run:

```bash
python check.py relay 1 --actuate
python check.py relay 2 --actuate
python check.py buzzer --actuate
```

Each relay should click on briefly, then off. Check COM–NO continuity with a meter; a relay click alone does not prove contact wiring is right. The unused relay is commanded off during each relay test.

The default `relay_active_high: true` is for the documented NPN driver in front of an active-low relay module. With a **verified Pi-compatible direct active-low interface**, use `false` instead. Software polarity does not make an unsafe 5V input circuit compatible with the Pi.

The default buzzer test uses a 2kHz square wave through a transistor, suitable for a passive piezo. If your actual B-10N has an internal oscillator and needs steady DC, set `buzzer_kind` to `"active"`. The package does not assume the ambiguous shop description proves which construction you have.

## 3. Enroll and recognise a fingerprint

Choose an unused slot; ID 1 is the default allowed ID in the demo:

```bash
python check.py enroll 1
python check.py match
```

Enrollment asks you to place a finger, remove it, and place the **same finger** again. It verifies storage after enrollment. If ID 1 already exists, the command refuses to overwrite it: choose another unused ID and update `allowed_finger_ids` in `config.json` if that ID should open the demo lock.

`match` reports `finger_id` and the sensor's matching score. **It never operates the lock.** The score is not a probability or percentage. A match to an existing ID is distinct from permission to open the lock; the demo also checks the allow-list and `minimum_match_confidence`.

Fingerprint templates stay in the R307. The code does not export raw fingerprints or store template images on the Pi. Later, your database can map `(device_id, finger_id)` to your user record. A slot ID is local to a particular sensor and should not be treated as a global identity.

## 4. Test fingerprint → relay → lock

Once the relay-only test passes, connect the lock as shown in `WIRING.md` and align the mock door's bolt/strike. Then:

```bash
python check.py demo --actuate --seconds 120
```

The demo updates the LCD, matches a fingerprint, checks the allowed ID/score, then pulses relay 1 for **0.5 seconds** by default. The bolt should retract so you can pull the door open. A denied match leaves the relay off. Finger removal and a cooldown are required before another accepted scan can cause a pulse. Relay 2 stays off.

`Ctrl+C`, SIGTERM and ordinary Python exceptions run cleanup that commands acquired outputs off. Power loss, SIGKILL or a hung OS cannot be handled by Python; the documented external pull-downs keep the transistor drivers off when their GPIOs float. These are bench diagnostics, not a complete unattended door controller.

The 0.5-second pulse and 10-second cooldown are test settings, **not a certified duty cycle for the lock**. Follow its manufacturer's energisation limits. Do not increase the pulse to hold an intermittent-duty solenoid open. The test code caps any individual pulse at one second.

The demo has no bolt-position or door-contact sensor. `relay_command: "pulsed"` means a GPIO command was sent, not that the door physically opened.

## 5. Camera

In Arduino IDE, install **esp32 by Espressif Systems**, version **3.x**, and choose **AI Thinker ESP32-CAM** for the supplied ESP32-CAM/MB kit.

1. Open `esp32_camera_test/esp32_camera_test.ino`.
2. Fill in `secrets.h` with your **2.4GHz** Wi-Fi name/password.
3. Connect the CAM-MB programmer to the computer running Arduino IDE and upload. If it does not enter download mode automatically, follow that MB board's boot/reset procedure; remove any temporary GPIO0-to-GND boot link before normal operation.
4. Open Serial Monitor at **115200 baud** and reset the board. Read the printed `http://...` address.
5. Put the Pi on the same reachable network. Open the printed address in a browser and press Capture. The camera can then be powered from an adequate USB source; its image connection is Wi-Fi.

On the Pi, replace the example IP with the printed one:

```bash
python check.py camera --url http://192.168.1.80 --save camera-test.jpg
```

The command refuses to overwrite an existing photo; use a new name for a second saved capture. It checks the HTTP response and JPEG start/end markers. Open the saved image to check framing, focus and scene content. Set `camera_url` in `config.json` if you want the `all` diagnostic to include this check.

The sketch also serves `/health`, which reports successful camera initialisation, not successful capture of every frame. This small HTTP camera server has no authentication; use it on your private test network and do not expose it publicly.

## 6. LM2596

```bash
python check.py power
```

This prints the manual test instructions. With the load disconnected, measure OUT+ to OUT− using a multimeter and adjust to the intended rail voltage, then check again under load. A 12V input does **not** imply a safe 5V output until adjusted. The Pi has no built-in analogue input; reading buck output or LDR AO would require an ADC and appropriate voltage scaling.

## Server/database handoff

Each result on stdout is one JSON object. Prompts/errors go to stderr, so you can capture results cleanly:

```bash
python check.py match > match-result.json
python check.py demo --actuate --seconds 120 | tee access-events.jsonl
```

An accepted access event contains `granted`, `match.finger_id`, `match.confidence` and `relay_command`. Keep the later database/network operations outside the interval in which the lock coil is energised. Do not run this diagnostic and a separate hardware-owning server simultaneously.

No server/database dependency is needed for these tests. Enrollment, recognition and local relay operation can be checked first.

## Troubleshooting

- **No I2C addresses:** check I2C enablement, SDA/SCL, ground and voltage translation. Inspect short bench leads before routing between boxes.
- **LCD has blocks or nonsense:** adjust contrast, confirm address, and confirm PCF8574 wiring is the common mapping. Different backpack mappings need a driver change.
- **Fingerprint cannot be found:** check TX/RX crossover, `/dev/serial0`, serial-console disabled, supply voltage and ground. Default baud is 57600; a previously reconfigured unit may differ. For a USB-to-UART adapter use its actual `/dev/ttyUSB...` or `/dev/serial/by-id/...` path. Do not connect the camera UART and fingerprint reader to the same Pi UART.
- **Fingerprint library list/count mismatch:** do not enroll. Stop competing serial processes, inspect power/baud, and retry. The code fails closed rather than overwriting an uncertain slot.
- **LDR does not change:** turn the threshold potentiometer while covering/uncovering it; an open/disconnected GPIO can also read high, so one static reading is not proof of connection.
- **Relay remains on/off:** disconnect lock power and verify physical driver topology before changing software polarity. Confirm VCC/JD-VCC connections from the exact module markings.
- **Camera brownout or ribbon error:** check the seated ribbon and a stable adequate 5V supply; a weak USB source/cable can fail even if the power LED lights.
- **Camera timeout:** check Wi-Fi/IP, client isolation and whether the camera was reset after failed Wi-Fi startup.

## Validation performed

21 hardware-free Python tests passed, covering enrollment protection, template-list mismatch, match allow-list/score gating, relay-off on interruption/errors, cleanup order, finite pulse limits, MPU conversion and LCD row addressing. Python and installer syntax were checked. These checks do **not** constitute physical sensor testing. The ESP32 sketch follows current Espressif camera APIs but was not compiled/flashed here because the Arduino ESP32 toolchain and your hardware are not attached.

References: [Pi GPIO and voltages](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [Pi UART setup](https://www.raspberrypi.com/documentation/computers/configuration.html), [Adafruit fingerprint API](https://docs.circuitpython.org/projects/fingerprint/en/latest/index.html), [TDK MPU6050 register map](https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf), [Espressif camera example](https://github.com/espressif/arduino-esp32/blob/master/libraries/ESP32/examples/Camera/CameraWebServer/CameraWebServer.ino).
