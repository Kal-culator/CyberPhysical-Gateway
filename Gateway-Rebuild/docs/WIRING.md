# Gateway V2 — physical wiring reference

Based on the breadboard assignments agreed in this chat. All Pi pins below are PHYSICAL header numbers; software GPIO numbers are BCM. These are intended connections, not confirmation of unphotographed wiring.

## Scope and limitations
Gateway V2 supports R307, LCD, two relays, MPU6050 and camera. Both Pi and camera use HTTP port 8080. MPU/camera tamper monitoring defaults off until calibrated. No LDR is used.

Breadboard positions below are a NEW proposed routing, not stored in code or confirmation of previous wiring. Use an empty standard breadboard with rows through 51. Layout: two power rails | A B C D E | gap | F G H I J | two power rails. Only A–E groups are used. A5–E5 connect internally; different row numbers do not. All outside power rails and F–J remain unused. Match actual printed letters, not board orientation.

Disconnect both supplies while wiring. All Pi numbers below are PHYSICAL 40-pin header numbers. BCM numbers are software identifiers.

## Required electrical interfaces
- LCD at 5 V: use a bidirectional I2C 3.3 V/5 V level shifter unless your backpack's I2C voltage compatibility is verified. A resistor alone is not an equivalent interface. This guide uses LV/HV and LV1/HV1, LV2/HV2 labels; equivalent boards use different channel names.
- Relay: config relay_active_high=true. The described circuit uses TWO NPN drivers in front of a verified active-low relay module, making Pi HIGH energize a relay. Each uses a 1 kΩ base resistor and a 10 kΩ base-to-emitter pull-down. Verify transistor E/B/C from its own datasheet; don't assume package pin order. On the photographed board: bridge RY-VCC to VCC using a jumper cap or female-to-female wire. DO NOT bridge the neighboring GND. This was missing during the no-click fault. This assumes a shared-ground 5 V relay module and built-in coil suppression. If your relay is a verified 3.3 V-compatible direct-input board, driver wiring and polarity may differ; a photo/model is needed before substituting direct connections. Do not blindly retain true with a direct active-low input.
- Pi 5 V supplies R307/LCD/relay/buzzer only if the Pi supply and wiring can support the total load. Do not solve undervoltage by connecting another supply positive in parallel.

## 1. R307 (preserves the newly suggested rows)
Pi pin 2 → A5; R307 VCC (previously identified red) → E5.
Pi pin 6 → A10; R307 GND (black) → E10.
Pi pin 10 / GPIO15 RX → A15; R307 TXD (yellow) → E15.
Pi pin 8 / GPIO14 TX → A20; R307 RXD (green) → E20.
Unused blue and white: disconnected and separately insulated. Colours are for the previously identified harness only; confirm labels if cable changed.

Code: /dev/serial0, 57600 baud. Earlier /dev/ttyAMA0 can be its target, but verify with readlink -f /dev/serial0. Select the UART actually routed to header pins 8/10; do not assume any ttyAMA device is automatically that UART. Enable serial hardware and disable serial login console.

## 2. Distribute power and ground using numbered rows
B5 → A25 (5 V distribution).
B10 → A26 (ground distribution).
C10 → A31 (relay ground distribution).
D10 → A41 (optional MPU ground).
Pi pin 1 (3.3 V) → A40.
These are jumpers between different rows. Do not join row 5/25 to row 40.

## 3. LCD and I2C level shifter
LCD VCC → E25; LCD GND → E26.
Shifter HV → D25; shifter GND → D26; shifter LV → B40.
Pi pin 3 / GPIO2 SDA → A45; shifter LV1 → E45.
Pi pin 5 / GPIO3 SCL → A46; shifter LV2 → E46.
Shifter HV1 → A50; LCD SDA → E50.
Shifter HV2 → A51; LCD SCL → E51.
Do NOT bridge rows 45 to 50 or 46 to 51 directly; signals must pass through the shifter.
Code uses I2C bus 1, LCD address 0x27. Confirm actual address before running.

## 4. MPU6050 (enable monitoring after calibration)
For a breakout rated for 3.3 V input: VCC → E40; GND → E41; AD0 → D41 for address 0x68.
SDA → C45; SCL → C46 (3.3 V side of I2C).
INT and XDA/XCL unused. Mount rigidly with insulated hardware for movement sensing. Use mpu-test, then enable mpu_enabled for motion/offline monitoring.

## 5. Relay power and NPN drivers (conditional on module interface above)
Relay VCC → C5; relay GND → D31. RY-VCC must be bridged to VCC.

Channel 1, buzzer:
Pi physical pin 13 / GPIO27 → A30.
1 kΩ resistor between E30 and A32.
NPN #1 BASE → E32; EMITTER → E31; COLLECTOR → E33.
10 kΩ resistor between C32 and C31.
Relay IN1 → A33.

Channel 2, deadbolt:
B31 → A36 (ground jumper).
Pi physical pin 15 / GPIO22 → A35.
1 kΩ resistor between E35 and A37.
NPN #2 BASE → E37; EMITTER → E36; COLLECTOR → E38.
10 kΩ resistor between C37 and C36.
Relay IN2 → A38.

Map BASE/EMITTER/COLLECTOR with jumpers according to the actual transistor pinout; do not simply put its three adjacent legs into one A–E row, which would short them.

## 6. Active 5 V buzzer via relay 1 contacts
C25 (5 V) → COM1.
NO1 → buzzer +.
Buzzer − → C26 (GND).
NC1 unused. Current code switches DC for 0.8 seconds; a passive piezo may only click and needs a tone driver instead. There is NO GPIO23 buzzer output in this code.

## 7. 12 V adapter, lock, diode and LM2596
Use suitable insulated wire and rated terminals, NOT breadboard/Dupont connections, for the lock power circuit.
12 V adapter + branches to COM2 and LM2596 IN+.
12 V adapter − branches to deadbolt − and LM2596 IN−.
NO2 → deadbolt +; NC2 unused.
Flyback diode across lock: striped cathode to deadbolt +/NO2; unstriped anode to deadbolt −/adapter −. Insulate leads separately. Use a diode rated for the actual coil; do not connect it in series.
Lock is powered briefly to retract. Current code unlock_seconds=0.5; verify actual lock duty cycle. Use python gateway.py lock-test --confirm only after the relay-only checks pass.

## 8. ESP32-CAM power and network
Set LM2596 output to measured 5.0 V before connecting camera.
OUT+ → ESP32-CAM 5V; OUT− → ESP32-CAM GND. Use short adequate wires. Pi keeps its own micro-USB supply.
Do NOT connect LM2596 OUT+ to Pi pin 2/4 or breadboard rows 5/25. Do not simultaneously backfeed camera from converter and USB programmer supply.
No Pi TX/RX wires go to camera: new firmware sends JPEGs over Wi-Fi to laptop HTTP port 8080. Camera's existing ribbon cable carries its onboard camera signals. The firmware's GPIO0/5/18/19/21/22/23/25/26/27/32/34/35/36/39 assignments are ESP32 internal camera connections, NOT Pi wiring. Leave flashing jumper GPIO0-to-GND removed for normal operation.
No Pi-to-camera ground jumper is required purely for Wi-Fi; a shared non-isolated control circuit would change that requirement.


## Test commands
See START-HERE.md. Use gateway.py in this project, not the previous demo.py. No hardware tests require the old repository.
