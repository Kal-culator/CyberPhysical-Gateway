# Pin mapping and electrical interfaces

**Your exact GPIO connections have not been supplied.** Edit `config.json` to match your wiring; this table is the package's default. Do not confuse physical header numbers with BCM GPIO numbers. Power off before moving wires.

| Module signal | BCM GPIO | Physical Pi header pin | Notes |
|---|---:|---:|---|
| LCD SDA | 2 | 3 | Through a bidirectional 3.3V↔5V I2C level shifter if backpack is powered at 5V |
| LCD SCL | 3 | 5 | Same shifter; common I2C bus |
| MPU6050 SDA | 2 | 3 | 3.3V side of I2C bus |
| MPU6050 SCL | 3 | 5 | 3.3V side of I2C bus |
| R307 RXD | 14 / TXD | 8 | Pi transmits to sensor RXD; use the reader's pin labels, not assumed wire colours |
| R307 TXD | 15 / RXD | 10 | Sensor transmits to Pi RXD; verify 3.3V signalling or use suitable UART level translation |
| LDR DO | 17 | 11 | Power this module at 3.3V; do not connect AO directly to a Pi GPIO |
| Relay channel 1 driver | 27 | 13 | Via transistor/interface described below |
| Relay channel 2 driver | 22 | 15 | Via transistor/interface described below |
| Buzzer driver | 23 | 16 | Via transistor; GPIO does not supply the 5V buzzer's power |
| 3.3V supply | — | 1 or 17 | MPU breakout (if rated for 3.3V input), LDR and shifter LV |
| 5V supply | — | 2 or 4 | Available rail, not a GPIO. Use an adequate supply arrangement for the total load |
| Ground | — | 6, 9, 14, 20, 25, 30, 34 or 39 | Common reference for non-isolated interfaces |

The Pi's GPIO pins are **3.3V-tolerant**. The availability of 5V power pins does not make its GPIO inputs 5V tolerant. [Official voltage specifications](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#voltage-specifications)

## LCD + MPU6050

The LCD's I2C backpack often has pull-ups to its 5V supply. Keep those pull-ups off the Pi's 3.3V bus by using an appropriate bidirectional I2C level shifter. Pi SDA/SCL and MPU SDA/SCL go on the LV side; LCD SDA/SCL go on the HV side. Shifter LV=3.3V, HV=5V and GND=common ground. A passive one-way divider is not a replacement for a bidirectional I2C interface.

The code assumes PCF8574 P0=RS, P1=RW, P2=E, P3=backlight, P4..P7=D4..D7. Confirm the module uses this common mapping. Typical address is 0x27 or 0x3F. MPU AD0 low gives 0x68; AD0 high gives 0x69. Power your MPU breakout according to its board specification and keep its SDA/SCL pull-ups at 3.3V.

## R307

Use the module's main rated supply, commonly 5V for the R307, and a common ground. Main supply voltage and UART signalling voltage are separate properties. Do not power a reader from 3.3V just because the Pi's UART uses 3.3V, and do not feed an unverified 5V TX signal into the Pi. Connect TX/RX crossed as in the table. Leave unused touch/USB pins alone for this UART test; do not join them to arbitrary power rails.

The R307 uses the Pi's primary UART in the default configuration. If the ESP32-CAM currently shares Pi GPIO14/15, disconnect that shared UART arrangement before running the fingerprint test. Use Wi-Fi for camera images. A separate USB-UART adapter for one device is another option, with the correct port configured.

## Two-channel 5V relay: default transistor interface

The default config has `relay_active_high: true` because it expects one NPN transistor per input in front of an active-low relay board:

```text
Pi GPIO27 -- 1kΩ -- base of NPN #1
                      |
                    10kΩ
                      |
Common GND -------- emitter of NPN #1
Relay IN1 --------- collector of NPN #1

Repeat using GPIO22 and IN2 for NPN #2.
Relay board supply: regulated 5V and common ground.
```

Use a suitable small signal NPN such as a correctly identified 2N2222, checking its actual emitter/base/collector pinout. The collector pulls the module's active-low input low; Pi GPIO HIGH therefore means relay ON. The input must return high when the transistor is off; confirm the module provides the appropriate input pull-up. Keep the module's VCC/JD-VCC arrangement consistent with its own documentation; this simple example uses a shared-ground interface, not galvanic isolation.

If your relay already has a **verified 3.3V-compatible direct input** and no inverting transistor stage, set the software polarity for that input (`false` for active-low). A board labelled only “5V relay” does not establish safe direct GPIO compatibility. Do not change polarity to troubleshoot a connected lock until the relay has been checked with lock power disconnected.

The 10kΩ base-to-ground resistors keep the transistor drivers off when Pi GPIOs are floating during startup/shutdown. Code alone cannot guarantee the power-on state of an unspecified relay circuit.

## Buzzer

Use an NPN low-side driver: GPIO23 → approximately 1kΩ → base; 10kΩ base-to-ground; emitter → GND; collector → buzzer negative; buzzer positive → its rated 5V rail. Confirm transistor pinout. Do not connect a 5V buzzer's supply directly to a GPIO.

For a passive piezo, the code produces a 2kHz PWM tone. For a self-oscillating active buzzer, select `"active"` in the config to use steady DC. If the actual sounder is inductive rather than piezoelectric, use appropriate flyback protection for that load.

## Deadbolt power path

```text
12V supply + ---- relay channel 1 COM
relay channel 1 NO ---- lock +
lock - --------------- 12V supply -
```

COM/NO are the isolated switching contacts, not VCC/IN/GND. Using NO means the lock is unpowered when the relay is off. The linked lock retracts when energised and extends when unpowered. It is listed as 12V/1.1A with intermittent energisation. [Same-ASIN uxcell specification](https://www.amazon.com/dp/B07TMWY94C)

Use suitable insulated wire and the relay screw terminals for the lock current; keep this current out of the solderless breadboard and Dupont jumpers. Fit suitable inductive suppression across the lock, accounting for any protection already built in. For a conventional DC coil flyback diode, cathode goes to lock positive and anode to lock negative; choose its rating for the coil current and energy. Never put an unprotected solenoid directly on a GPIO.

The relay-control circuit and the lock-contact circuit are different circuits. The contact side does not need a connection to Pi GPIO ground merely to switch the lock; share grounds only where required by the power/converter/control arrangement.

## Supplies and LM2596

- Keep the Pi on its proper micro-USB supply as planned.
- Adjust the LM2596 output using a multimeter **before** connecting any 5V loads. Check its output again with the actual load connected.
- Do not join the output of the buck converter to the Pi adapter's positive rail unless you have specifically designed that power-sharing arrangement. Common ground for logic is different from tying two power outputs together.
- Never connect 12V to the Pi header or the ESP32-CAM's 5V pin.
- Test the camera with a stable adequate supply. Its CAM-MB USB connection can provide power/programming, while the test image transfer uses Wi-Fi.
- Run short I2C wires for the first bench test. A long harness between the two boxes may need slower bus timing, appropriate pull-ups or a different interconnect after bench validation.
