#!/usr/bin/env python3
"""Pi 3B+ bench diagnostics. GPIO numbers are BCM, not physical header numbers.

Hardware imports are lazy: --help and the unit tests run without a Pi.
Run only one instance; this program does not share the serial/I2C buses with a server.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import signal
import struct
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen


def emit(event, **values):
    item = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **values}
    print(json.dumps(item, allow_nan=False), flush=True)
    return item


def validate_config(c):
    pins = [c['light_gpio'], c['buzzer_gpio'], *c['relay_gpios']]
    if len(c['relay_gpios']) != 2 or len(set(pins)) != len(pins):
        raise ValueError('Choose two relay GPIOs and distinct GPIOs for light/buzzer/relays')
    if any(type(p) is not int or p < 4 or p > 27 or p in (14, 15) for p in pins):
        raise ValueError('Use BCM GPIO 4..27, excluding UART GPIO14/15; I2C uses GPIO2/3')
    if type(c['relay_active_high']) is not bool:
        raise ValueError('relay_active_high must be JSON true or false')
    if c['light_dark_level'] not in (0, 1):
        raise ValueError('light_dark_level must be 0 or 1')
    if c['buzzer_kind'] not in ('active', 'passive'):
        raise ValueError('buzzer_kind must be active or passive')
    bounded_seconds(c['unlock_seconds'], 1.0)
    if not math.isfinite(c['unlock_cooldown_seconds']) or c['unlock_cooldown_seconds'] < 5:
        raise ValueError('Use an unlock cooldown of at least 5 seconds for this bench demo')
    if not isinstance(c['allowed_finger_ids'], list) or any(type(i) is not int or i < 1 for i in c['allowed_finger_ids']):
        raise ValueError('allowed_finger_ids must contain positive integer slot IDs')
    if not math.isfinite(c['minimum_match_confidence']) or c['minimum_match_confidence'] < 0:
        raise ValueError('minimum_match_confidence must be finite and nonnegative')
    for key in ['lcd_address', 'mpu_address']:
        if not 0x08 <= address(c[key]) <= 0x77:
            raise ValueError(f'{key} must be a 7-bit I2C address')
    pwd = c['fingerprint_password']
    if len(pwd) != 4 or any(type(b) is not int or not 0 <= b <= 255 for b in pwd):
        raise ValueError('fingerprint_password must be four bytes')
    return c


def address(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def bounded_seconds(value, maximum):
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f'Duration must be greater than zero and at most {maximum} seconds')
    return value


class LCD:
    """Common PCF8574 backpack: P0=RS P1=RW P2=E P3=backlight P4..7=D4..7."""
    ROWS = (0x00, 0x40, 0x14, 0x54)

    def __init__(self, bus, addr):
        self.bus, self.addr = bus, addr
        time.sleep(.05)
        for value, pause in [(0x30, .005), (0x30, .001), (0x30, .001), (0x20, .001)]:
            self.nibble(value)
            time.sleep(pause)
        for command in (0x28, 0x08, 0x01, 0x06, 0x0C):
            self.byte(command)

    def nibble(self, value):
        value |= 0x08  # Backlight on; RW is always low.
        self.bus.write_byte(self.addr, value)
        self.bus.write_byte(self.addr, value | 0x04)
        time.sleep(.00005)
        self.bus.write_byte(self.addr, value & ~0x04)
        time.sleep(.00005)

    def byte(self, value, data=False):
        rs = 1 if data else 0
        self.nibble((value & 0xF0) | rs)
        self.nibble(((value << 4) & 0xF0) | rs)
        if not data and value in (1, 2):
            time.sleep(.003)

    def lines(self, *lines):
        for row, start in enumerate(self.ROWS):
            self.byte(0x80 | start)
            text = str(lines[row] if row < len(lines) else '').encode('ascii', 'replace')[:20]
            for char in text.ljust(20, b' '):
                self.byte(char, data=True)


def read_mpu(bus, addr, initialize=False):
    who = bus.read_byte_data(addr, 0x75)
    if who != 0x68:
        raise RuntimeError(f'MPU6050 WHO_AM_I was 0x{who:02x}, expected 0x68')
    if initialize:
        for reg, value in [(0x6B, 0x01), (0x1B, 0), (0x1C, 0), (0x1A, 3), (0x19, 9)]:
            bus.write_byte_data(addr, reg, value)
        time.sleep(.10)
    values = struct.unpack('>7h', bytes(bus.read_i2c_block_data(addr, 0x3B, 14)))
    acc = [round(v / 16384.0, 4) for v in values[:3]]
    return {'accel_g': acc, 'gyro_dps': [round(v / 131.0, 3) for v in values[4:]],
            'chip_temperature_c': round(values[3] / 340.0 + 36.53, 2),
            'accel_magnitude_g': round(math.sqrt(sum(v*v for v in acc)), 4)}


class Fingerprint:
    def __init__(self, sensor, protocol):
        self.sensor, self.p = sensor, protocol

    def require_ok(self, code, operation):
        if code != self.p.OK:
            raise RuntimeError(f'{operation} failed: sensor status 0x{code:02x}')

    def info(self):
        self.require_ok(self.sensor.read_sysparam(), 'Read parameters')
        self.require_ok(self.sensor.count_templates(), 'Count templates')
        self.require_ok(self.sensor.read_templates(), 'List templates')
        ids = sorted(set(self.sensor.templates))
        if len(ids) != self.sensor.template_count:
            raise RuntimeError('Template list/count mismatch; refusing to enroll over an uncertain slot')
        return {'capacity': self.sensor.library_size, 'stored_ids': ids,
                'security_level': self.sensor.security_level}

    def wait_image(self, timeout=15, removed=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.sensor.get_image()
            if status == (self.p.NOFINGER if removed else self.p.OK):
                return
            if status not in (self.p.NOFINGER, self.p.OK):
                self.require_ok(status, 'Capture image; clean/reposition finger')
            time.sleep(.10)
        raise TimeoutError('Remove finger' if removed else 'No fingerprint captured before timeout')

    def enroll(self, slot, timeout):
        info = self.info()
        if not 1 <= slot < info['capacity']:
            raise ValueError(f'Use an ID from 1 to {info["capacity"] - 1}')
        if slot in info['stored_ids']:
            raise ValueError(f'ID {slot} already exists; choose another ID (no overwrite performed)')
        print('Place the finger to enroll.', file=sys.stderr, flush=True)
        self.wait_image(timeout)
        self.require_ok(self.sensor.image_2_tz(1), 'First scan')
        print('Remove your finger.', file=sys.stderr, flush=True)
        self.wait_image(timeout, removed=True)
        print('Place the SAME finger again.', file=sys.stderr, flush=True)
        self.wait_image(timeout)
        self.require_ok(self.sensor.image_2_tz(2), 'Second scan')
        self.require_ok(self.sensor.create_model(), 'Combine scans; use the same finger twice')
        self.require_ok(self.sensor.store_model(slot), 'Store template')
        if slot not in self.info()['stored_ids']:
            raise RuntimeError('Store returned success, but the new ID was not found on verification')
        return {'finger_id': slot, 'stored_on': 'R307 sensor flash'}

    def match(self, timeout=15):
        self.wait_image(timeout)
        self.require_ok(self.sensor.image_2_tz(1), 'Convert image')
        code = self.sensor.finger_search()
        if code == self.p.NOTFOUND:
            return None
        self.require_ok(code, 'Search fingerprint library')
        return {'finger_id': self.sensor.finger_id, 'confidence': self.sensor.confidence}


def authorized(match, c):
    return bool(match and match['finger_id'] in c['allowed_finger_ids']
                and match['confidence'] >= c['minimum_match_confidence'])


def pulse(device, seconds, sleep=time.sleep):
    bounded_seconds(seconds, 1.0)
    try:
        device.on()
        sleep(seconds)
    finally:
        device.off()


def handle_match(match, c, relay):
    """Single testable authorization point. No network/DB call while relay is on."""
    if not authorized(match, c):
        return False
    pulse(relay, c['unlock_seconds'])
    return True


class Hardware:
    def __init__(self, c):
        self.c, self.stack, self.resources = c, ExitStack(), {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def bus(self):
        if 'bus' not in self.resources:
            from smbus2 import SMBus
            self.resources['bus'] = self.stack.enter_context(SMBus(self.c['i2c_bus']))
        return self.resources['bus']

    def lcd(self):
        if 'lcd' not in self.resources:
            self.resources['lcd'] = LCD(self.bus(), address(self.c['lcd_address']))
        return self.resources['lcd']

    def finger(self):
        if 'finger' not in self.resources:
            import serial
            import adafruit_fingerprint as af
            uart = self.stack.enter_context(serial.Serial(self.c['fingerprint_port'],
                       self.c['fingerprint_baud'], timeout=1, write_timeout=1, exclusive=True))
            uart.reset_input_buffer()
            sensor = af.Adafruit_Fingerprint(uart, passwd=tuple(self.c['fingerprint_password']))
            self.resources['finger'] = Fingerprint(sensor, af)
        return self.resources['finger']

    def gpio(self):
        if 'gpio' not in self.resources:
            import gpiozero
            from gpiozero.pins.lgpio import LGPIOFactory
            factory = LGPIOFactory()
            gpiozero.Device.pin_factory = factory
            self.stack.callback(factory.close)
            self.resources['gpio'] = gpiozero
        return self.resources['gpio']

    def light(self):
        if 'light' not in self.resources:
            dev = self.gpio().DigitalInputDevice(self.c['light_gpio'], pull_up=True)
            self.resources['light'] = self.stack.enter_context(dev)
        raw = int(self.resources['light'].pin.state)
        return {'raw_do': raw, 'dark': raw == self.c['light_dark_level'], 'units': 'threshold, not lux'}

    def relay(self, channel):
        key = f'relay{channel}'
        if key not in self.resources:
            dev = self.gpio().OutputDevice(self.c['relay_gpios'][channel-1],
                     active_high=self.c['relay_active_high'], initial_value=False)
            self.stack.enter_context(dev)
            self.stack.callback(dev.off)  # Off before close; then GPIO returns to input.
            self.resources[key] = dev
        return self.resources[key]

    def buzzer(self):
        if 'buzzer' not in self.resources:
            gpio = self.gpio()
            if self.c['buzzer_kind'] == 'passive':
                dev = gpio.PWMOutputDevice(self.c['buzzer_gpio'], initial_value=0,
                         frequency=self.c['buzzer_frequency_hz'])
            else:
                dev = gpio.OutputDevice(self.c['buzzer_gpio'], initial_value=False)
            self.stack.enter_context(dev)
            self.stack.callback(dev.off)
            self.resources['buzzer'] = dev
        return self.resources['buzzer']


def camera_check(url, output=None):
    if urlparse(url).scheme not in ('http', 'https') or not urlparse(url).hostname:
        raise ValueError('Set camera_url to http://<ESP32-IP>, from its Serial Monitor')
    request_url = url.rstrip('/') + '/capture'
    with urlopen(request_url, timeout=5) as response:
        if response.headers.get_content_type() != 'image/jpeg':
            raise RuntimeError('Camera endpoint did not return image/jpeg')
        image = response.read(2_000_001)
    if len(image) > 2_000_000 or not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
        raise RuntimeError('Response was an oversized, incomplete or invalid JPEG')
    if output:
        with Path(output).open('xb') as file:  # Never overwrite an existing photograph.
            file.write(image)
    return {'jpeg_bytes': len(image), 'saved_to': str(output) if output else None}


def all_checks(hw, c):
    failures = 0
    tasks = [
        ('lcd', lambda: (hw.lcd().lines('LCD TEST 20 x 4', 'Row 2: 12345678901234',
                   'Row 3: ABCDEFGHIJKLMN', 'Row 4: visible?'), {'check': 'Visually confirm all four rows'})[1]),
        ('mpu', lambda: read_mpu(hw.bus(), address(c['mpu_address']), True)),
        ('light', hw.light), ('fingerprint', lambda: hw.finger().info())]
    if c['camera_url']:
        tasks.append(('camera', lambda: camera_check(c['camera_url'])))
    else:
        emit('camera', status='SKIP', reason='Set camera_url after flashing the ESP32 sketch')
    for name, task in tasks:
        try:
            emit(name, status='READ_OK', data=task())
        except Exception as error:
            failures += 1
            emit(name, status='ERROR', error=str(error))
    emit('outputs', status='SKIP', reason='Relay and buzzer require their explicit --actuate test')
    emit('lm2596', status='MANUAL', reason='Measure output with a multimeter; the Pi has no built-in ADC')
    return 1 if failures else 0


def demo(hw, c, duration):
    finger, lcd, relay = hw.finger(), hw.lcd(), hw.relay(1)
    hw.relay(2)  # Explicitly keep the unused channel off too.
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        lcd.lines('FINGERPRINT DEMO', 'Place finger', 'Relay 1: OFF', 'Ctrl+C to stop')
        try:
            match = finger.match(min(5, max(.1, deadline-time.monotonic())))
        except TimeoutError:
            continue
        if authorized(match, c):
            # Complete potentially blocking display writes before energising the lock.
            lcd.lines('MATCH ACCEPTED', f'ID: {match["finger_id"]}', 'Unlocking briefly', 'Pull door to open')
        else:
            lcd.lines('ACCESS DENIED', 'No allowed match', 'Relay stays OFF')
        granted = handle_match(match, c, relay)
        emit('access_decision', granted=granted, match=match, relay_command='pulsed' if granted else 'off')
        # Require removal before the next authentication; a held finger cannot retrigger.
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            break
        finger.wait_image(min(15, remaining), removed=True)
        if granted:
            lcd.lines('Relay 1: OFF', 'Cooldown', 'Close the door')
            time.sleep(min(c['unlock_cooldown_seconds'], max(0, deadline-time.monotonic())))
    lcd.lines('TEST FINISHED', 'Relay 1: OFF', 'Relay 2: OFF')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('config.json'))
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('all', 'lcd', 'finger-info', 'power'):
        sub.add_parser(name)
    for name in ('mpu', 'light'):
        s = sub.add_parser(name); s.add_argument('--seconds', type=float, default=10)
    s = sub.add_parser('enroll'); s.add_argument('id', type=int); s.add_argument('--timeout', type=float, default=30)
    s = sub.add_parser('match'); s.add_argument('--timeout', type=float, default=15)
    s = sub.add_parser('relay'); s.add_argument('channel', type=int, choices=(1, 2))
    s.add_argument('--seconds', type=float, default=.5); s.add_argument('--actuate', action='store_true')
    s = sub.add_parser('buzzer'); s.add_argument('--seconds', type=float, default=.3)
    s.add_argument('--actuate', action='store_true')
    s = sub.add_parser('camera'); s.add_argument('--url'); s.add_argument('--save', type=Path)
    s = sub.add_parser('demo'); s.add_argument('--seconds', type=float, default=120)
    s.add_argument('--actuate', action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    c = validate_config(json.loads(args.config.read_text()))
    if hasattr(args, 'seconds'):
        bounded_seconds(args.seconds, 1 if args.command in ('relay', 'buzzer') else 3600)
    if hasattr(args, 'timeout'):
        bounded_seconds(args.timeout, 120)
    if args.command in ('relay', 'buzzer', 'demo') and not args.actuate:
        raise ValueError('Add --actuate only after checking pin mapping, driver polarity and wiring')
    with Hardware(c) as hw:
        if args.command == 'all':
            return all_checks(hw, c)
        if args.command == 'lcd':
            hw.lcd().lines('LCD TEST 20 x 4', 'Row 2: 12345678901234', 'Row 3: ABCDEFGHIJKLMN', 'Row 4: visible?')
            emit('lcd', status='WRITE_OK', check='Confirm all 4 rows; turn contrast potentiometer if needed')
        elif args.command in ('mpu', 'light'):
            end, first = time.monotonic()+args.seconds, True
            while time.monotonic() < end:
                data = read_mpu(hw.bus(), address(c['mpu_address']), first) if args.command == 'mpu' else hw.light()
                emit(args.command, **data); first = False; time.sleep(.25)
        elif args.command == 'finger-info':
            emit('fingerprint', **hw.finger().info())
        elif args.command == 'enroll':
            emit('finger_enrolled', **hw.finger().enroll(args.id, args.timeout))
        elif args.command == 'match':
            print('Place a finger. This command NEVER opens the lock.', file=sys.stderr, flush=True)
            result = hw.finger().match(args.timeout)
            emit('finger_match', matched=result is not None, match=result, allowed_for_demo=authorized(result, c))
            return 0 if result else 2
        elif args.command == 'relay':
            relay = hw.relay(args.channel); hw.relay(3-args.channel)
            pulse(relay, args.seconds)
            emit('relay_test', channel=args.channel, command='pulse_complete', note='Verify click/contact/bolt physically; no feedback sensor fitted')
        elif args.command == 'buzzer':
            buzzer = hw.buzzer()
            try:
                buzzer.value = .5 if c['buzzer_kind'] == 'passive' else 1
                time.sleep(args.seconds)
            finally:
                buzzer.off()
            emit('buzzer_test', command='complete', note='Listen for the tone; software cannot verify sound')
        elif args.command == 'camera':
            emit('camera', **camera_check(args.url or c['camera_url'], args.save))
        elif args.command == 'demo':
            demo(hw, c, args.seconds)
        elif args.command == 'power':
            emit('lm2596', test='Use a multimeter on OUT+/OUT-. Adjust to the required rail voltage before connecting loads. Check again under load. Never connect 12V to a Pi GPIO or power pin.')
    return 0


if __name__ == '__main__':
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Stopped; acquired outputs were commanded off during cleanup.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
