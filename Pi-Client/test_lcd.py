#!/usr/bin/env python3
"""Standalone I2C LCD diagnostic for PCF8574 backpack."""

import sys
import time
from smbus2 import SMBus

# Change to 0x3F if i2cdetect showed 3f
LCD_ADDRESS = 0x27
I2C_BUS = 1

ROWS = (0x00, 0x40, 0x14, 0x54)

def write_nibble(bus, addr, val):
    val |= 0x08  
    bus.write_byte(addr, val)
    bus.write_byte(addr, val | 0x04) 
    time.sleep(0.00005)
    bus.write_byte(addr, val & ~0x04) 
    time.sleep(0.00005)

def write_byte(bus, addr, val, data=False):
    rs = 1 if data else 0
    write_nibble(bus, addr, (val & 0xF0) | rs)
    write_nibble(bus, addr, ((val << 4) & 0xF0) | rs)
    if not data and val in (1, 2):
        time.sleep(0.003)

def init_lcd(bus, addr):
    time.sleep(0.05)
    for val, pause in ((0x30, 0.005), (0x30, 0.001), (0x30, 0.001), (0x20, 0.001)):
        write_nibble(bus, addr, val)
        time.sleep(pause)
    for cmd in (0x28, 0x08, 0x01, 0x06, 0x0C):
        write_byte(bus, addr, cmd)

def print_lines(bus, addr, *lines):
    for row, offset in enumerate(ROWS):
        write_byte(bus, addr, 0x80 | offset)
        text = str(lines[row] if row < len(lines) else "").encode("ascii", "replace")[:20]
        for char in text.ljust(20, b" "):
            write_byte(bus, addr, char, data=True)

if __name__ == "__main__":
    print(f"Connecting to LCD at I2C bus {I2C_BUS}, address 0x{LCD_ADDRESS:02x}...")
    try:
        with SMBus(I2C_BUS) as bus:
            init_lcd(bus, LCD_ADDRESS)
            print_lines(
                bus,
                LCD_ADDRESS,
                "== ZERO-TRUST HUB ==",
                "SYSTEM: ONLINE",
                "FINGERPRINT: READY",
                "LCD TEST OK"
            )
            print("Successfully sent text to LCD.")
            print("If screen is blank or solid blocks, turn the small blue potentiometer on the back now!")
    except Exception as e:
        print(f"ERROR: Could not communicate with LCD: {e}")
        print("Check connections: SDA->Pin 3, SCL->Pin 5, VCC->Pin 2/4 (5V), GND->Pin 6")