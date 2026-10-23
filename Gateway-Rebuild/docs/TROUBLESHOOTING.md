# Troubleshooting

| Symptom | Check |
|---|---|
| Invalid JSON at line 1 | `python3 -m json.tool pi/config.json`; do not paste Markdown fences. `gateway.py config-check` reports missing fields. |
| File not found | This package is `~/Gateway-Rebuild/pi`, not Tomorrow-Demo or Final-Release. |
| Relay LED on, no click | Your photographed board requires RY-VCC bridged to VCC, 5V coil supply and common ground. Do not connect 12V to board input pins. |
| Buzzer on lock-test | IN1/IN2 or load terminal groups are swapped. Verify physical pin13→BCM27→IN1; pin15→BCM22→IN2. |
| Relay clicks, bolt doesn't move | Check correct COM2/NO2, 12V adapter, diode orientation and voltage at lock during pulse. No firmware can fix a supply/wiring fault. |
| UART packet error | Stop all other sensor programs; verify serial hardware enabled, login disabled, correct port, TX/RX crossed and common ground. Do not guess cable colors on a replacement harness. |
| Scan unclear | Clean/dry finger and optical window; lift then place flat. Enroll only after finger-info succeeds. |
| LCD address present but blank | Contrast/backpack pin mapping/supply compatibility. Never solve it by feeding unprotected 5V into Pi I²C. `lcd_enabled=false` allows console mode. |
| HTTP 401 | Pi/camera API key differs from server. Re-running configure.py rotates it. |
| HTTP 503 | Look at Java console; database or service failed. Access is denied. |
| Connection refused/timed out | Java running, same LAN, actual Mac IPv4, firewall, no guest Wi-Fi isolation. New camera uses 8080 too. |
| Telegram message absent | Stop old Java server, check own bot Start, token/chat/owner settings and Internet. Use tools/telegram_chat.py with server stopped. |
| Telegram click ignored | Wrong owner/chat, expired request, repeated click, or another bot poller. The server logs terminal decisions. |
| Old MySQL full_name error | You're running the old schema. New DB is cyberphysical_v2 with gateway_users/gateway_events. Do not delete the old DB. |
| MySQL Access denied | Match db.user/db.password to a working MySQL login. Do not assume the Mac login password. |
| MPU alarm at rest | Run mpu-test, mount firmly, capture stationary startup baseline, adjust thresholds. |
| Camera dark warning | Inspect scene lighting and dashboard brightness; darkness alone is not proof of obstruction. |
| Camera HTTP negative | Mac IP, Wi-Fi, power, Java server. HTTP 401 is a key problem, not a camera hardware fault. |

Do not run old and new Pi clients simultaneously. The new client prevents concurrent new-client hardware commands for the same OS user but cannot stop unrelated old software or protect against physical shorts.
