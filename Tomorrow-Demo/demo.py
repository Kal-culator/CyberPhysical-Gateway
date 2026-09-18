#!/usr/bin/env python3
"""Minimal local demo: LCD + R307 + buzzer relay 1 + deadbolt relay 2."""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import signal
import socket
import sys
import time


def load_config(path):
    config = json.loads(path.read_text())
    if not isinstance(config["allowed_finger_ids"], list) or not config["allowed_finger_ids"]:
        raise ValueError("allowed_finger_ids must contain at least one enrolled ID")
    if any(type(value) is not int or value < 1 for value in config["allowed_finger_ids"]):
        raise ValueError("allowed_finger_ids must contain positive integers")
    for name, maximum in (("unlock_seconds", 1.0), ("buzzer_seconds", 2.0)):
        value = config[name]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(f"{name} must be greater than zero and at most {maximum}")
    if config["buzzer_relay_gpio"] == config["lock_relay_gpio"]:
        raise ValueError("The two relay GPIOs must be different")
    if type(config["server_enabled"]) is not bool:
        raise ValueError("server_enabled must be true or false")
    if config["server_enabled"]:
        if not isinstance(config["server_host"], str) or not config["server_host"].strip():
            raise ValueError("server_host must contain the laptop IP address")
        if type(config["server_port"]) is not int or not 1 <= config["server_port"] <= 65535:
            raise ValueError("server_port must be an integer from 1 to 65535")
        if not isinstance(config["device_id"], str) or not config["device_id"].strip():
            raise ValueError("device_id must contain a name")
        if type(config["approval_timeout_seconds"]) is not int or not 5 <= config["approval_timeout_seconds"] <= 60:
            raise ValueError("approval_timeout_seconds must be from 5 to 60")
    return config


def is_authorized(match, config):
    return bool(match
                and match["finger_id"] in config["allowed_finger_ids"]
                and match["confidence"] >= config["minimum_confidence"])


class LCD:
    """Common PCF8574 I2C backpack in four-bit mode."""

    ROWS = (0x00, 0x40, 0x14, 0x54)

    def __init__(self, bus, address):
        self.bus = bus
        self.address = address
        time.sleep(0.05)
        for value, pause in ((0x30, 0.005), (0x30, 0.001),
                             (0x30, 0.001), (0x20, 0.001)):
            self._nibble(value)
            time.sleep(pause)
        for command in (0x28, 0x08, 0x01, 0x06, 0x0C):
            self._byte(command)

    def _nibble(self, value):
        value |= 0x08
        self.bus.write_byte(self.address, value)
        self.bus.write_byte(self.address, value | 0x04)
        time.sleep(0.00005)
        self.bus.write_byte(self.address, value & ~0x04)
        time.sleep(0.00005)

    def _byte(self, value, data=False):
        rs = 1 if data else 0
        self._nibble((value & 0xF0) | rs)
        self._nibble(((value << 4) & 0xF0) | rs)
        if not data and value in (1, 2):
            time.sleep(0.003)

    def show(self, *lines):
        for row, offset in enumerate(self.ROWS):
            self._byte(0x80 | offset)
            text = str(lines[row] if row < len(lines) else "").encode("ascii", "replace")[:20]
            for character in text.ljust(20, b" "):
                self._byte(character, data=True)


class DemoHardware:
    def __init__(self, config, outputs=False):
        self.config = config
        self.outputs = outputs
        self.stack = ExitStack()

    def __enter__(self):
        try:
            from smbus2 import SMBus
            import serial
            import adafruit_fingerprint

            self.af = adafruit_fingerprint
            self.bus = self.stack.enter_context(SMBus(1))
            self.lcd = LCD(self.bus, int(self.config["lcd_address"], 0))
            self.uart = self.stack.enter_context(serial.Serial(
                self.config["fingerprint_port"],
                self.config["fingerprint_baud"], timeout=1, write_timeout=1,
                exclusive=True))
            self.uart.reset_input_buffer()
            self.finger = adafruit_fingerprint.Adafruit_Fingerprint(self.uart)

            self.buzzer_relay = None
            self.lock_relay = None
            if self.outputs:
                import gpiozero
                from gpiozero.pins.lgpio import LGPIOFactory
                factory = LGPIOFactory()
                gpiozero.Device.pin_factory = factory
                self.stack.callback(factory.close)
                self.buzzer_relay = self.stack.enter_context(gpiozero.OutputDevice(
                    self.config["buzzer_relay_gpio"],
                    active_high=self.config["relay_active_high"], initial_value=False))
                self.lock_relay = self.stack.enter_context(gpiozero.OutputDevice(
                    self.config["lock_relay_gpio"],
                    active_high=self.config["relay_active_high"], initial_value=False))
                self.stack.callback(self.buzzer_relay.off)
                self.stack.callback(self.lock_relay.off)
            return self
        except Exception:
            self.stack.close()
            raise

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def template_ids(self):
        if self.finger.read_templates() != self.af.OK:
            raise RuntimeError("Could not read fingerprint IDs")
        return sorted(set(self.finger.templates))

    def wait_for_image(self, timeout=None, removed=False):
        deadline = None if timeout is None else time.monotonic() + timeout
        wanted = self.af.NOFINGER if removed else self.af.OK
        while deadline is None or time.monotonic() < deadline:
            status = self.finger.get_image()
            if status == wanted:
                return
            if status not in (self.af.OK, self.af.NOFINGER):
                raise RuntimeError(f"Fingerprint capture error 0x{status:02x}")
            time.sleep(0.1)
        raise TimeoutError("Fingerprint operation timed out")

    def identify(self):
        self.wait_for_image()
        if self.finger.image_2_tz(1) != self.af.OK:
            return None
        status = self.finger.finger_search()
        if status == self.af.NOTFOUND:
            return None
        if status != self.af.OK:
            raise RuntimeError(f"Fingerprint search error 0x{status:02x}")
        return {"finger_id": int(self.finger.finger_id),
                "confidence": int(self.finger.confidence)}

    def pulse(self, device, seconds):
        try:
            device.on()
            time.sleep(seconds)
        finally:
            device.off()


def status(hw, config):
    if hw.finger.read_sysparam() != hw.af.OK:
        raise RuntimeError("R307 did not return valid system parameters")
    ids = hw.template_ids()
    hw.lcd.show("SYSTEM READY", "R307 + LCD OK", f"Stored IDs: {ids}")
    print(f"LCD connected at {config['lcd_address']}")
    print(f"R307 connected; stored fingerprint IDs: {ids}")


def enroll(hw, slot):
    if slot in hw.template_ids():
        raise ValueError(f"Fingerprint ID {slot} already exists; delete it or choose another ID")
    hw.lcd.show("ENROLL FINGER", f"ID {slot}", "Place finger")
    print("Place the finger.")
    hw.wait_for_image(30)
    if hw.finger.image_2_tz(1) != hw.af.OK:
        raise RuntimeError("First fingerprint scan failed")
    hw.lcd.show("REMOVE FINGER")
    print("Remove the finger.")
    hw.wait_for_image(15, removed=True)
    hw.lcd.show("SAME FINGER AGAIN")
    print("Place the same finger again.")
    hw.wait_for_image(30)
    if hw.finger.image_2_tz(2) != hw.af.OK:
        raise RuntimeError("Second fingerprint scan failed")
    if hw.finger.create_model() != hw.af.OK:
        raise RuntimeError("The two scans did not match")
    if hw.finger.store_model(slot) != hw.af.OK:
        raise RuntimeError("Could not store fingerprint")
    hw.lcd.show("ENROLLMENT SAVED", f"Fingerprint ID {slot}")
    print(f"Fingerprint ID {slot} stored successfully.")


def delete(hw, slot):
    if hw.finger.delete_model(slot) != hw.af.OK:
        raise RuntimeError(f"Could not delete fingerprint ID {slot}")
    hw.lcd.show("FINGER DELETED", f"ID {slot}")
    print(f"Fingerprint ID {slot} deleted.")


def send_event(match, decision, relay_channel, config, wait_for_action=False):
    """Send an event and optionally wait for the owner's Telegram decision."""
    if not config["server_enabled"]:
        return "BUZZER" if wait_for_action else None
    payload = {
        "device_id": config["device_id"],
        "fingerprint_id": match["finger_id"] if match else None,
        "confidence": match["confidence"] if match else 0,
        "pi_decision": decision,
        "relay_channel": relay_channel,
    }
    try:
        with socket.create_connection(
                (config["server_host"], config["server_port"]), timeout=0.8) as connection:
            connection.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            if wait_for_action:
                connection.settimeout(config["approval_timeout_seconds"] + 7)
                with connection.makefile("r", encoding="utf-8") as response_stream:
                    response = response_stream.readline(2049)
                if not response or len(response) > 2048:
                    raise OSError("The server returned no valid decision")
                action = json.loads(response).get("action")
                if action not in ("OPEN", "BUZZER"):
                    raise OSError("The server returned an unknown decision")
                print(f"Telegram decision received: {action}")
                return action
        print("Event sent to laptop server.")
    except OSError as error:
        print(f"Server unavailable; local demo continued ({error}).", file=sys.stderr)
    except (json.JSONDecodeError, ValueError) as error:
        print(f"Invalid server response; access denied ({error}).", file=sys.stderr)
    return "BUZZER" if wait_for_action else None


def run_demo(hw, config):
    print("Demo running. Press Ctrl+C to stop.")
    while True:
        hw.lcd.show("SMART DOOR", "Put fingerprint", "Waiting...")
        match = hw.identify()
        if is_authorized(match, config):
            hw.lcd.show("ACCESS GRANTED", f"Fingerprint ID {match['finger_id']}",
                        "Opening lock...")
            print(f"ACCESS GRANTED: {match}")
            hw.pulse(hw.lock_relay, config["unlock_seconds"])
            send_event(match, "GRANTED", 2, config)
            hw.lcd.show("DOOR LOCKED", "Remove finger")
        else:
            hw.lcd.show("UNKNOWN FINGER", "Check Telegram", "Waiting 30 seconds")
            print(f"UNKNOWN FINGERPRINT: {match}; waiting for Telegram approval")
            action = send_event(match, "REVIEW", 0, config, wait_for_action=True)
            if action == "OPEN":
                hw.lcd.show("OWNER APPROVED", "ACCESS GRANTED", "Opening lock...")
                hw.pulse(hw.lock_relay, config["unlock_seconds"])
                hw.lcd.show("DOOR LOCKED", "Remove finger")
            else:
                hw.lcd.show("ACCESS DENIED", "No owner approval", "Buzzer ON")
                hw.pulse(hw.buzzer_relay, config["buzzer_seconds"])
        try:
            hw.wait_for_image(15, removed=True)
        except TimeoutError:
            pass
        time.sleep(config["cooldown_seconds"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).with_name("demo_config.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("run")
    sub.add_parser("server-test")
    sub.add_parser("telegram-test")
    enroll_parser = sub.add_parser("enroll")
    enroll_parser.add_argument("id", type=int)
    delete_parser = sub.add_parser("delete")
    delete_parser.add_argument("id", type=int)
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "server-test":
        send_event({"finger_id": 1, "confidence": 99}, "GRANTED", 2, config)
        return
    if args.command == "telegram-test":
        print("Sending a simulated unknown fingerprint. Answer the Telegram message.")
        action = send_event(None, "REVIEW", 0, config, wait_for_action=True)
        print(f"The Pi would activate: {'relay 2 / lock' if action == 'OPEN' else 'relay 1 / buzzer'}")
        return

    with DemoHardware(config, outputs=args.command == "run") as hardware:
        if args.command == "status":
            status(hardware, config)
        elif args.command == "enroll":
            enroll(hardware, args.id)
        elif args.command == "delete":
            delete(hardware, args.id)
        else:
            run_demo(hardware, config)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Both relay outputs were commanded off.", file=sys.stderr)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
