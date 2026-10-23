"""Drivers are lazy: testing a relay never opens the UART or the LCD."""
import time
import threading
from contextlib import ExitStack

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



class Outputs:
    def __init__(self,cfg): self.cfg=cfg;self.stack=ExitStack();self.guard=threading.Lock()
    def __enter__(self):
        from gpiozero import Device,OutputDevice
        from gpiozero.pins.lgpio import LGPIOFactory
        try:
            factory=LGPIOFactory();self.stack.callback(factory.close);Device.pin_factory=factory
            self.buzzer=self.stack.enter_context(OutputDevice(self.cfg['buzzer_gpio'],active_high=self.cfg['relay_active_high'],initial_value=False))
            self.lock=self.stack.enter_context(OutputDevice(self.cfg['lock_gpio'],active_high=self.cfg['relay_active_high'],initial_value=False))
            return self
        except BaseException:self.stack.close();raise
    def off(self):
        self.lock.off();self.buzzer.off()
    def pulse(self,kind):
        with self.guard:
            self.off()
            device=self.lock if kind=='lock' else self.buzzer
            seconds=self.cfg['unlock_seconds'] if kind=='lock' else self.cfg['buzzer_seconds']
            try:device.on();time.sleep(seconds)
            finally:device.off()
    def __exit__(self,*args):
        try:self.off()
        finally:self.stack.close()

class Fingerprint:
    def __init__(self,cfg):self.cfg=cfg
    def __enter__(self):
        import serial,adafruit_fingerprint
        self.af=adafruit_fingerprint
        self.uart=serial.Serial(self.cfg['fingerprint_port'],self.cfg['fingerprint_baud'],timeout=1,write_timeout=1,exclusive=True)
        try:self.sensor=adafruit_fingerprint.Adafruit_Fingerprint(self.uart);return self
        except BaseException:self.uart.close();raise
    def __exit__(self,*args):self.uart.close()
    def ids(self):
        if self.sensor.read_templates()!=self.af.OK:raise RuntimeError('R307 could not list stored IDs')
        return sorted(self.sensor.templates)
    def scan(self):
        status=self.sensor.get_image()
        if status==self.af.NOFINGER:return 'EMPTY',None,0
        if status!=self.af.OK:
            if status in (self.af.IMAGEFAIL,):return 'RETRY',None,0
            raise RuntimeError(f'R307 capture error 0x{status:02x}')
        if self.sensor.image_2_tz(1)!=self.af.OK:return 'RETRY',None,0
        status=self.sensor.finger_search()
        if status==self.af.NOTFOUND:return 'MATCH',None,0
        if status!=self.af.OK:raise RuntimeError(f'R307 search error 0x{status:02x}')
        return 'MATCH',int(self.sensor.finger_id),int(self.sensor.confidence)
    def wait(self,removed=False,seconds=30):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            code=self.sensor.get_image()
            if code==(self.af.NOFINGER if removed else self.af.OK):return
            time.sleep(0.1)
        raise TimeoutError('Fingerprint wait timed out; lift and replace your finger')
    def enroll(self,slot):
        if slot in self.ids():raise ValueError(f'ID {slot} already exists. Delete it explicitly or choose a different ID.')
        for buffer in (1,2):
            print('Place finger' if buffer==1 else 'Place SAME finger again',flush=True)
            self.wait()
            if self.sensor.image_2_tz(buffer)!=self.af.OK:raise RuntimeError('Scan was unclear; clean/dry finger and retry enrollment')
            if buffer==1:print('Remove finger',flush=True);self.wait(removed=True,seconds=15)
        if self.sensor.create_model()!=self.af.OK:raise RuntimeError('Scans did not match')
        if self.sensor.store_model(slot)!=self.af.OK:raise RuntimeError('Fingerprint could not be stored')
        print(f'Enrolled ID {slot}. Add/authorize that ID in MySQL too.')

class Display:
    def __init__(self,cfg):self.cfg=cfg;self.bus=None;self.lcd=None
    def __enter__(self):
        if self.cfg['lcd_enabled']:
            from smbus2 import SMBus
            self.bus=SMBus(1)
            try:self.lcd=LCD(self.bus,int(self.cfg['lcd_address'],0))
            except BaseException:self.bus.close();raise
        return self
    def show(self,*lines):
        print(' | '.join(map(str,lines)),flush=True)
        if self.lcd:self.lcd.show(*lines)
    def __exit__(self,*args):
        if self.bus:self.bus.close()

class MPU:
    def __init__(self,cfg):self.address=int(cfg['mpu_address'],0);self.bus=None
    def __enter__(self):
        from smbus2 import SMBus
        self.bus=SMBus(1)
        try:
            if self.bus.read_byte_data(self.address,0x75)!=0x68:raise RuntimeError('Unexpected MPU WHO_AM_I')
            self.bus.write_byte_data(self.address,0x6B,0)
            self.bus.write_byte_data(self.address,0x1C,0) # +/-2g
            self.bus.write_byte_data(self.address,0x1B,0) # +/-250 deg/s
            self.bus.write_byte_data(self.address,0x1A,3) # digital low-pass filter
            time.sleep(0.1);return self
        except BaseException:self.bus.close();raise
    def read(self):
        data=self.bus.read_i2c_block_data(self.address,0x3B,14)
        def s(i):
            n=(data[i]<<8)|data[i+1]
            return n-65536 if n>=32768 else n
        return [s(i)/16384 for i in (0,2,4)],[s(i)/131 for i in (8,10,12)]
    def __exit__(self,*args):
        if self.bus:self.bus.close()
