#!/usr/bin/env python3
"""Raspberry Pi door node using the final breadboard wiring."""

import json
import os
import socket
import time

import adafruit_fingerprint
import RPi.GPIO as GPIO
import serial


SERVER_IP = os.environ.get("GATEWAY_SERVER_IP", "")
SERVER_PORT = int(os.environ.get("GATEWAY_SERVER_PORT", "8080"))
ALLOWED_FINGER_IDS = {
    int(value) for value in os.environ.get("ALLOWED_FINGER_IDS", "1").split(",")
    if value.strip()
}

# BCM numbers followed by physical header-pin numbers in comments.
BUZZER_RELAY_PIN = 27  # pin 13, NPN driver to relay channel 1
LOCK_RELAY_PIN = 22    # pin 15, NPN driver to relay channel 2
LIGHT_PIN = 17       # pin 11, LM393 digital output (DO)
RELAY_ON = GPIO.HIGH # NPN stage inverts the active-low relay input
RELAY_OFF = GPIO.LOW
UNLOCK_SECONDS = 0.5


def send_to_server(payload):
    if not SERVER_IP:
        print("Gateway reporting skipped: set GATEWAY_SERVER_IP when starting.")
        return
    try:
        message = json.dumps(payload, separators=(",", ":")) + "\n"
        with socket.create_connection((SERVER_IP, SERVER_PORT), timeout=3) as connection:
            connection.sendall(message.encode("utf-8"))
        print(f"Sent to gateway: {message.strip()}")
    except OSError as error:
        print(f"Gateway unavailable ({error}); local lock operation continues.")


def pulse_lock():
    try:
        GPIO.output(LOCK_RELAY_PIN, RELAY_ON)
        time.sleep(UNLOCK_SECONDS)
    finally:
        GPIO.output(LOCK_RELAY_PIN, RELAY_OFF)


def sound_buzzer(seconds=0.8):
    try:
        GPIO.output(BUZZER_RELAY_PIN, RELAY_ON)
        time.sleep(seconds)
    finally:
        GPIO.output(BUZZER_RELAY_PIN, RELAY_OFF)


def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_RELAY_PIN, GPIO.OUT, initial=RELAY_OFF)
    GPIO.setup(LOCK_RELAY_PIN, GPIO.OUT, initial=RELAY_OFF)
    GPIO.setup(LIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # Pi TX GPIO14/pin 8 -> R307 RX; R307 TX -> Pi RX GPIO15/pin 10.
    uart = serial.Serial("/dev/serial0", baudrate=57600, timeout=1)
    finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

    print("Door node ready. Place a finger on the R307; Ctrl+C stops safely.")
    print(f"Allowed fingerprint IDs: {sorted(ALLOWED_FINGER_IDS)}")
    print("Relay 1 controls the active 5V buzzer; relay 2 controls the deadbolt.")
    try:
        while True:
            status = finger.get_image()
            if status == adafruit_fingerprint.NOFINGER:
                time.sleep(0.1)
                continue
            if status != adafruit_fingerprint.OK:
                print(f"Fingerprint capture error: 0x{status:02x}")
                time.sleep(0.5)
                continue
            if finger.image_2_tz(1) != adafruit_fingerprint.OK:
                print("Could not convert fingerprint image.")
                continue

            found = finger.finger_search() == adafruit_fingerprint.OK
            finger_id = int(finger.finger_id) if found else None
            confidence = int(finger.confidence) if found else 0
            granted = found and finger_id in ALLOWED_FINGER_IDS
            light_dark = GPIO.input(LIGHT_PIN) == GPIO.LOW
            payload = {
                "sensor": "R307_Fingerprint",
                "uid": finger_id if finger_id is not None else -1,
                "confidence": confidence,
                "light_dark": light_dark,
                "action": "unlock" if granted else "denied",
            }

            if granted:
                print(f"GRANTED: fingerprint ID {finger_id}, confidence {confidence}")
                send_to_server(payload)
                pulse_lock()
            else:
                print("DENIED: unknown or disallowed fingerprint")
                send_to_server(payload)
                sound_buzzer()

            while finger.get_image() != adafruit_fingerprint.NOFINGER:
                time.sleep(0.1)
            time.sleep(1)
    finally:
        GPIO.output(BUZZER_RELAY_PIN, RELAY_OFF)
        GPIO.output(LOCK_RELAY_PIN, RELAY_OFF)
        uart.close()
        GPIO.cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped; relay and buzzer switched off.")
