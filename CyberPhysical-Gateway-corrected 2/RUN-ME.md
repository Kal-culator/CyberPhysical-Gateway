# Start here

For tomorrow, use only the `Tomorrow-Demo` folder. Its `README.md` gives the exact laptop and Raspberry Pi commands in order.

That simplified version includes:

- R307 fingerprint matching on the Raspberry Pi
- 20x4 LCD messages
- relay channel 2 for the deadbolt on GPIO22
- relay channel 1 for the active buzzer on GPIO27
- a Java server on the laptop
- a MySQL `users` table and `access_events` log
- Telegram YES/NO approval with a 30-second timeout for unknown fingerprints
- local opening for registered ID 1 even if the laptop connection fails

The other folders contain the larger camera, obstruction, light, and tamper project. Keep them for the later phase; do not mix those commands into tomorrow's demonstration.

Open `Tomorrow-Demo/EXECUTE-GUIDE.md` and begin at step A1. Every command is labelled **LAPTOP** or **RASPBERRY PI**.
