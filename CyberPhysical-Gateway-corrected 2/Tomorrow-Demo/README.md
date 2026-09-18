# Tomorrow's fingerprint-door demonstration

For the clearest command-by-command instructions, open `EXECUTE-GUIDE.md`. Every command there is labelled **LAPTOP** or **RASPBERRY PI**.

The Raspberry Pi accepts registered fingerprint ID 1 locally. An unknown fingerprint starts a 30-second Telegram approval request with **YES - OPEN** and **NO - DENY** buttons.

```text
R307 scan on Pi
      |
      +-- ID 1 accepted --> LCD ACCESS GRANTED --> relay 2 --> deadbolt
      |
      +-- unknown finger --> Java sends Telegram question --> wait up to 30 seconds
                                      |
                                      +-- YES --> relay 2 --> deadbolt
                                      |
                                      +-- NO, timeout, or error --> relay 1 --> buzzer

Every result --> MySQL access_events
```

If the laptop, server, Wi-Fi, or Telegram is unavailable, registered ID 1 still opens locally. An unknown fingerprint fails safely to the buzzer.

## Final GPIO assignment

| Function | BCM GPIO | Pi physical pin |
|---|---:|---:|
| R307 green TX into Pi RX | 15 | 10 |
| R307 yellow RX from Pi TX | 14 | 8 |
| LCD SDA | 2 | 3 |
| LCD SCL | 3 | 5 |
| Relay 1: active 5V buzzer | 27 | 13 |
| Relay 2: 12V deadbolt | 22 | 15 |

## 1. Laptop: create the Telegram bot

1. In Telegram, open the verified **@BotFather** account.
2. Send `/newbot`, choose a name, and copy the bot token.
3. Open the new bot's private chat, press **Start**, and send `hello`.
4. In Terminal, enter the extracted folder and run:

```bash
cd Tomorrow-Demo/Java-Server
bash get_chat_id.sh
```

Paste the bot token when asked. Copy the printed chat ID. Use a private chat so only you can approve entry. Do not put the bot token in Git or inside a source file.

## 2. Laptop: create the MySQL database

From the `Tomorrow-Demo` folder:

```bash
mysql -u root -p < database.sql
```

Enter the MySQL root password. This creates `smart_door_demo`, adds authorized fingerprint ID 1, and creates a fresh `access_events` table. Running it again resets the event log.

If MySQL or Maven is missing on a Mac:

```bash
brew install mysql maven
brew services start mysql
```

## 3. Laptop: start Java

```bash
cd Java-Server
bash run_server.sh
```

Enter these three values when asked:

1. MySQL root password
2. Telegram bot token from BotFather
3. Telegram private chat ID from step 1

Keep this Terminal open. Correct startup shows:

```text
MySQL connection OK.
Telegram bot connection OK.
Gateway server listening on port 8080.
```

## 4. Laptop: find its Wi-Fi IP address

On a Mac:

```bash
ipconfig getifaddr en0
```

If that prints nothing:

```bash
ipconfig getifaddr en1
```

The laptop and Pi must use the same Wi-Fi. Allow incoming Java connections if the firewall asks.

## 5. Pi: pull the files and set the laptop IP

```bash
cd ~/CyberPhysical-Gateway
git pull
cd CyberPhysical-Gateway-corrected/Tomorrow-Demo
nano demo_config.json
```

Replace `192.168.1.50` in `server_host` with the laptop IP from step 4. Leave `approval_timeout_seconds` at `30`. Save with `Ctrl+O`, Enter, then exit with `Ctrl+X`.

If your Git repository opens directly into `CyberPhysical-Gateway-corrected`, omit that one folder name from the `cd` command.

## 6. Pi: one-time setup

```bash
bash setup.sh
sudo raspi-config
```

Enable I2C. Under Serial Port, disable the login shell and enable the serial hardware. Reboot, return to this folder, then run:

```bash
source .venv/bin/activate
```

## 7. Test Java, MySQL, and Telegram without hardware

Keep Java running on the laptop. On the Pi:

```bash
python demo.py server-test
python demo.py telegram-test
```

The first command stores a normal ID 1 event. The second sends a simulated unknown fingerprint. Press **YES - OPEN** or **NO - DENY** in Telegram; the Pi terminal prints which relay it would activate. Run `telegram-test` again and do not press anything to verify the 30-second timeout selects the buzzer.

## 8. Test LCD and fingerprint sensor

```bash
i2cdetect -y 1
python demo.py status
```

`i2cdetect` should show the LCD at `27` or sometimes `3f`. If it shows `3f`, change `lcd_address` in `demo_config.json` to `0x3f`.

If fingerprint ID 1 is missing:

```bash
python demo.py enroll 1
```

To replace ID 1:

```bash
python demo.py delete 1
python demo.py enroll 1
```

## 9. Run the complete demonstration

```bash
python demo.py run
```

- Enrolled ID 1: LCD grants access and relay 2 opens the lock immediately.
- Unknown finger, Telegram **YES** within 30 seconds: relay 2 opens the lock.
- Telegram **NO**, no answer for 30 seconds, server error, or Telegram error: relay 1 powers the buzzer.

Stop the Pi program with `Ctrl+C`; it commands both relay outputs off. Stop Java with `Ctrl+C` in its laptop terminal.

## 10. Show the stored events

On the laptop:

```bash
mysql -u root -p -e "SELECT event_id, event_time, fingerprint_id, pi_decision, telegram_decision, final_action, relay_channel FROM smart_door_demo.access_events ORDER BY event_id DESC LIMIT 20;"
```

## Hardware limits

The buzzer must be an active 5V buzzer because relay 1 supplies steady DC. A passive piezo will only click.

Do not connect 12V to the deadbolt until a flyback diode is fitted across its coil. Until then, leave 12V disconnected and demonstrate authorization with the relay 2 click and LCD message.
