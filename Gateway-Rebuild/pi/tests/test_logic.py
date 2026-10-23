import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gateway
from hardware import Outputs

class LogicTests(unittest.TestCase):
    def setUp(self):self.c=json.loads((gateway.ROOT/'config.example.json').read_text())
    def test_bad_config_explained(self):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            f.write('');f.flush()
            with self.assertRaisesRegex(ValueError,'Invalid config JSON'):gateway.load(f.name)
    def test_pulse_bounds(self):
        for value in (0,2,float('nan'),True):
            self.c['unlock_seconds']=value
            with tempfile.NamedTemporaryFile(mode='w') as f:
                json.dump(self.c,f);f.flush()
                with self.assertRaises(ValueError):gateway.load(f.name)
    def test_motion_persistence(self):
        detector=gateway.MotionDetector([0,0,1],self.c)
        self.assertFalse(detector.update([0,0,1],[0,0,0]))
        self.assertFalse(detector.update([1,0,1],[0,0,0]))
        self.assertFalse(detector.update([1,0,1],[0,0,0]))
        self.assertTrue(detector.update([1,0,1],[0,0,0]))
        self.assertFalse(detector.update([0,0,1],[0,0,0]))
    def test_pulse_turns_off_even_on_interrupt(self):
        output=Outputs(self.c);output.lock=MagicMock();output.buzzer=MagicMock()
        with patch('hardware.time.sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):output.pulse('lock')
        output.lock.on.assert_called_once();self.assertGreaterEqual(output.lock.off.call_count,2)
        output.buzzer.on.assert_not_called()
    def test_pending_tamper_denies(self):
        result=gateway.wait_decision(MagicMock(),{'action':'PENDING'},self.c,lambda:True)
        self.assertEqual('DENY',result['action'])
    def test_invalid_action_rejected(self):
        with self.assertRaises(RuntimeError):gateway.wait_decision(MagicMock(),{'action':'UNLOCK_FOREVER'},self.c)
    def test_simulation_cannot_drive_real_pi(self):
        self.c.update(server_url='http://localhost:8080',api_key='a'*64)
        response=MagicMock();response.__enter__.return_value=response;response.read.return_value=b'{"simulation":true,"action":"OPEN"}'
        with patch('urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(RuntimeError,'Simulation'):gateway.API(self.c).call('/health')
    def test_default_config_valid(self):
        self.assertEqual(22,gateway.load(gateway.ROOT/'config.example.json')['lock_gpio'])
if __name__=='__main__':unittest.main()
