> **Laptop webcam update:** Follow [LAPTOP-WEBCAM.md](LAPTOP-WEBCAM.md) to replace only the ESP32-CAM. Pull this update on both laptop and Pi.

# Exact execution guide: laptop versus Raspberry Pi

Use the standalone `Tomorrow-Demo` folder for this demonstration. Commands marked **LAPTOP** run on your Mac laptop. Commands marked **RASPBERRY PI** run in the Pi terminal. Keep the laptop and Pi connected to the same Wi-Fi.

## A. One-time preparation

### A1. LAPTOP — put the files in Git

Extract `Tomorrow-Demo.zip`. Copy the resulting `Tomorrow-Demo` folder into the top level of your cloned `CyberPhysical-Gateway` repository.

In the laptop terminal:

```bash
cd /path/to/CyberPhysical-Gateway
git add Tomorrow-Demo
git commit -m "Add fingerprint Telegram demonstration"
git push
```

Replace `/path/to/CyberPhysical-Gateway` with the real repository location on the laptop. If the files have already been pushed, skip this step.

### A2. LAPTOP — install Java, Maven, and MySQL

Check what is installed:

```bash
java -version
mvn -version
mysql --version
```

On a Mac with Homebrew, install anything missing:

```bash
brew install openjdk maven mysql
brew services start mysql
```

### A3. LAPTOP — create the database

```bash
cd /path/to/CyberPhysical-Gateway/Tomorrow-Demo
mysql -u root -p < database.sql
```

Enter the MySQL root password. If the local MySQL root account has no password, press Enter. This creates:

- database `smart_door_demo`
- authorized fingerprint ID 1
- table `access_events`

Running `database.sql` again resets the event log.

### A4. LAPTOP/TELEGRAM — create the bot

1. Open Telegram and find the verified **@BotFather**.
2. Send `/newbot`.
3. Choose the bot name and username.
4. Copy the bot token that BotFather gives you.
5. Open your new bot's private chat.
6. Press **Start** and send `hello`.

Now find your private chat ID on the laptop:

```bash
cd /path/to/CyberPhysical-Gateway/Tomorrow-Demo/Java-Server
bash get_chat_id.sh
```

Paste the bot token when asked. Copy the number printed after `Chat ID:`. Keep both the bot token and chat ID ready. Do not commit the token to Git.

### A5. LAPTOP — find the laptop IP address

```bash
ipconfig getifaddr en0
```

If nothing appears:

```bash
ipconfig getifaddr en1
```

Example result: `192.168.1.50`. Your number may be different.

### A6. RASPBERRY PI — pull the project

```bash
cd ~/CyberPhysical-Gateway
git pull
find . -type d -name Tomorrow-Demo
```

If the result is `./Tomorrow-Demo`, enter:

```bash
cd ~/CyberPhysical-Gateway/Tomorrow-Demo
```

If `find` prints a different location, use that exact location after `cd`. This avoids the “no such file or directory” problem.

### A7. RASPBERRY PI — enter the laptop IP

While inside `Tomorrow-Demo`:

```bash
nano demo_config.json
```

Find:

```json
"server_host": "192.168.1.50"
```

Replace only the IP address with the laptop IP from A5. Leave the port at `8080` and the approval timer at `30`.

Save using `Ctrl+O`, press Enter, and exit using `Ctrl+X`.

### A8. RASPBERRY PI — install the Pi software

```bash
bash setup.sh
sudo raspi-config
```

In `raspi-config`:

1. Enable **I2C**.
2. Open **Serial Port**.
3. Answer **No** to serial login shell.
4. Answer **Yes** to serial hardware.
5. Finish and reboot.

After reboot:

```bash
cd ~/CyberPhysical-Gateway/Tomorrow-Demo
source .venv/bin/activate
```

If your `find` command in A6 showed another location, return to that location instead.

## B. Exact order every time you run the demonstration

### B1. LAPTOP — ensure MySQL is running

```bash
brew services start mysql
```

### B2. LAPTOP — start the Java server

Open a laptop Terminal window:

```bash
cd /path/to/CyberPhysical-Gateway/Tomorrow-Demo/Java-Server
bash run_server.sh
```

Enter, in order:

1. MySQL root password
2. Telegram bot token
3. Telegram private chat ID

Do not close this terminal. Wait for all three lines:

```text
MySQL connection OK.
Telegram bot connection OK.
Gateway server listening on port 8080.
```

If the macOS firewall asks whether Java may accept incoming connections, choose **Allow**.

### B3. RASPBERRY PI — activate the program environment

Open the Pi terminal:

```bash
cd ~/CyberPhysical-Gateway/Tomorrow-Demo
source .venv/bin/activate
```

### B4. RASPBERRY PI — test laptop and database communication

```bash
python demo.py server-test
```

Expected Pi result:

```text
Event sent to laptop server.
```

The Java terminal should show an event for `Demo User`.

### B5. RASPBERRY PI — test Telegram without operating relays

```bash
python demo.py telegram-test
```

Telegram should show **YES - OPEN** and **NO - DENY**.

- Press **YES - OPEN**: the Pi terminal says it would activate relay 2/lock.
- Run the command again and press **NO - DENY**: it says relay 1/buzzer.
- Run it again and do nothing: after 30 seconds it says relay 1/buzzer.

This test does not operate the physical relays.

### B6. RASPBERRY PI — check LCD and R307

```bash
i2cdetect -y 1
python demo.py status
```

The LCD should appear at address `27`. If it appears at `3f`, edit `demo_config.json` and change `lcd_address` to `0x3f`.

The status command prints the fingerprint IDs stored inside the R307.

If ID 1 is missing:

```bash
python demo.py enroll 1
```

To replace ID 1:

```bash
python demo.py delete 1
python demo.py enroll 1
```

### B7. RASPBERRY PI — run the real demonstration

```bash
python demo.py run
```

Leave this Pi terminal running.

Expected behavior:

| Test | LCD/Telegram | Physical result |
|---|---|---|
| Enrolled fingerprint ID 1 | `ACCESS GRANTED` | Relay 2 opens lock |
| Unknown finger, Telegram YES within 30 seconds | `OWNER APPROVED` | Relay 2 opens lock |
| Unknown finger, Telegram NO | `ACCESS DENIED` | Relay 1 activates buzzer |
| Unknown finger, no reply for 30 seconds | `ACCESS DENIED` | Relay 1 activates buzzer |
| Telegram/server failure for unknown finger | `ACCESS DENIED` | Relay 1 activates buzzer |

### B8. LAPTOP — show the SQL event history

Open a second laptop Terminal while Java remains open in the first:

```bash
mysql -u root -p -e "SELECT event_id, event_time, fingerprint_id, pi_decision, telegram_decision, final_action, relay_channel FROM smart_door_demo.access_events ORDER BY event_id DESC LIMIT 20;"
```

### B9. Stop everything

On the Raspberry Pi, press `Ctrl+C` in the running demo. On the laptop, press `Ctrl+C` in the Java server terminal.

## Hardware safety before the real lock test

The 5V buzzer must be an active buzzer. A passive piezo may only click.

Do not connect the deadbolt's 12V supply until a flyback diode is installed across the deadbolt coil. Before that, demonstrate a successful opening using the relay 2 click and LCD message while the 12V supply remains disconnected.
