"""Hardware-free logic checks; not evidence of successful physical sensor tests."""
import copy
import io
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import check

CONFIG = json.loads(Path(__file__).with_name('config.json').read_text())
PROTO = SimpleNamespace(OK=0, NOFINGER=2, NOTFOUND=9)


class FakeSensor:
    def __init__(self):
        self.templates = [1]; self.template_count = 1
        self.library_size = 1000; self.security_level = 3
        self.finger_id = 1; self.confidence = 90
        self.get_image = Mock(return_value=0)
        self.image_2_tz = Mock(return_value=0)
        self.create_model = Mock(return_value=0)
        self.finger_search = Mock(return_value=0)
        self.store_model = Mock(side_effect=self.store)
    def store(self, slot):
        self.templates.append(slot); self.template_count += 1; return 0
    def read_sysparam(self): return 0
    def count_templates(self): return 0
    def read_templates(self): return 0


class LogicTests(unittest.TestCase):
    def test_default_config(self):
        check.validate_config(copy.deepcopy(CONFIG))

    def test_pin_conflicts_are_rejected(self):
        c = copy.deepcopy(CONFIG); c['relay_gpios'][0] = c['light_gpio']
        with self.assertRaises(ValueError): check.validate_config(c)

    def test_uart_pin_conflicts_are_rejected(self):
        c = copy.deepcopy(CONFIG); c['buzzer_gpio'] = 14
        with self.assertRaises(ValueError): check.validate_config(c)

    def test_nonfinite_and_long_pulses_rejected(self):
        for seconds in [0, -1, 1.1, float('nan'), float('inf')]:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError): check.bounded_seconds(seconds, 1)

    def test_interrupt_turns_relay_off(self):
        relay = Mock()
        def interruption(_): raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt): check.pulse(relay, .5, sleep=interruption)
        relay.on.assert_called_once(); relay.off.assert_called_once()

    def test_driver_on_failure_still_attempts_off(self):
        relay = Mock(); relay.on.side_effect = RuntimeError('driver error')
        with self.assertRaises(RuntimeError): check.pulse(relay, .5)
        relay.off.assert_called_once()

    def test_unknown_low_confidence_and_no_match_do_not_unlock(self):
        relay = Mock()
        with patch('check.pulse') as pulse:
            for match in [None, {'finger_id': 2, 'confidence': 100}, {'finger_id': 1, 'confidence': 49}]:
                self.assertFalse(check.handle_match(match, CONFIG, relay))
            pulse.assert_not_called()

    def test_allowed_fingerprint_pulses_only_once(self):
        relay = Mock()
        with patch('check.pulse') as pulse:
            self.assertTrue(check.handle_match({'finger_id': 1, 'confidence': 80}, CONFIG, relay))
            pulse.assert_called_once_with(relay, .5)

    def test_enroll_never_overwrites(self):
        s = FakeSensor(); f = check.Fingerprint(s, PROTO)
        with self.assertRaises(ValueError): f.enroll(1, 1)
        s.store_model.assert_not_called(); s.get_image.assert_not_called()

    def test_enroll_refuses_partial_template_list(self):
        s = FakeSensor(); s.template_count = 2; f = check.Fingerprint(s, PROTO)
        with self.assertRaises(RuntimeError): f.enroll(2, 1)
        s.store_model.assert_not_called()

    def test_enrollment_two_scans_and_removal_then_verification(self):
        s = FakeSensor(); f = check.Fingerprint(s, PROTO)
        with patch.object(f, 'wait_image') as wait, patch('sys.stderr', io.StringIO()):
            result = f.enroll(2, 1)
        self.assertEqual(result['finger_id'], 2)
        self.assertEqual(wait.call_args_list[1].kwargs, {'removed': True})
        self.assertEqual([c.args[0] for c in s.image_2_tz.call_args_list], [1, 2])
        s.store_model.assert_called_once_with(2)

    def test_mismatched_enrollment_is_not_stored(self):
        s = FakeSensor(); s.create_model.return_value = 10; f = check.Fingerprint(s, PROTO)
        with patch.object(f, 'wait_image'), patch('sys.stderr', io.StringIO()):
            with self.assertRaises(RuntimeError): f.enroll(2, 1)
        s.store_model.assert_not_called()

    def test_match_not_found_does_not_return_stale_id(self):
        s = FakeSensor(); s.finger_search.return_value = 9
        self.assertIsNone(check.Fingerprint(s, PROTO).match(.1))

    def test_capture_error_is_not_treated_as_match(self):
        s = FakeSensor(); s.get_image.return_value = 1
        with self.assertRaises(RuntimeError): check.Fingerprint(s, PROTO).match(.1)
        s.finger_search.assert_not_called()

    def test_no_finger_has_a_timeout(self):
        s = FakeSensor(); s.get_image.return_value = 2
        with patch('check.time.monotonic', side_effect=[0, 0, 2]), patch('check.time.sleep'):
            with self.assertRaises(TimeoutError): check.Fingerprint(s, PROTO).wait_image(1)

    def test_mpu_signed_units_and_temperature(self):
        bus = Mock(); bus.read_byte_data.return_value = 0x68
        bus.read_i2c_block_data.return_value = list(struct.pack('>7h', -16384, 0, 16384, 340, -131, 262, 0))
        sample = check.read_mpu(bus, 0x68)
        self.assertEqual(sample['accel_g'], [-1, 0, 1])
        self.assertEqual(sample['gyro_dps'], [-1, 2, 0])
        self.assertEqual(sample['chip_temperature_c'], 37.53)

    def test_wrong_mpu_identity_rejected(self):
        bus = Mock(); bus.read_byte_data.return_value = 0x70
        with self.assertRaises(RuntimeError): check.read_mpu(bus, 0x68)

    def test_lcd_four_row_offsets_and_padding(self):
        lcd = check.LCD.__new__(check.LCD); lcd.byte = Mock()
        lcd.lines('a', 'b', 'c', 'd')
        calls = lcd.byte.call_args_list
        self.assertEqual([calls[i*21].args[0] for i in range(4)], [0x80, 0xC0, 0x94, 0xD4])
        self.assertEqual(len(calls), 84)

    def test_relay_cleanup_off_precedes_close(self):
        events = []
        class Device:
            def __enter__(self): return self
            def __exit__(self, *args): events.append('close')
            def off(self): events.append('off')
        with self.assertRaises(RuntimeError):
            with check.Hardware(CONFIG) as h:
                h.resources['gpio'] = SimpleNamespace(OutputDevice=lambda *a, **k: Device())
                h.relay(1)
                raise RuntimeError('test failure')
        self.assertEqual(events, ['off', 'close'])

    def test_all_checks_do_not_create_outputs(self):
        h = Mock(); h.bus.return_value.read_byte_data.return_value = 0x68
        h.bus.return_value.read_i2c_block_data.return_value = list(struct.pack('>7h', 0, 0, 16384, 0, 0, 0, 0))
        h.light.return_value = {'raw_do': 1}; h.finger.return_value.info.return_value = {'stored_ids': [1]}
        with patch('check.emit'), patch('check.time.sleep'):
            self.assertEqual(check.all_checks(h, CONFIG), 0)
        h.relay.assert_not_called(); h.buzzer.assert_not_called()

    def test_actuation_requires_explicit_flag(self):
        with patch('check.Hardware') as hardware:
            with self.assertRaises(ValueError): check.main(['relay', '1'])
            hardware.assert_not_called()


if __name__ == '__main__':
    unittest.main()
