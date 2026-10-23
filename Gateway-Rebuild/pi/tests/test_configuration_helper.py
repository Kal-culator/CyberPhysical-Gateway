import sys,json,tempfile,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('configure',ROOT/'tools/configure.py')
configure=importlib.util.module_from_spec(spec);spec.loader.exec_module(configure)

class ConfigureTests(unittest.TestCase):
    def test_generated_configs_share_key_and_preserve_passwords(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for sub in ('pi','server','camera/CameraNode'):(root/sub).mkdir(parents=True)
            (root/'pi/config.example.json').write_bytes((ROOT/'pi/config.example.json').read_bytes())
            inputs=['192.168.1.50','gateway','123','123','Demo WiFi']
            passwords=[' db pass:=! ','123456:fake-test-token','wifi-pass']
            with patch.object(configure,'ROOT',root),patch('builtins.input',side_effect=inputs),patch.object(configure.getpass,'getpass',side_effect=passwords),patch('builtins.print'):
                configure.main()
            pi=json.loads((root/'pi/config.json').read_text())
            props=(root/'server/config.properties').read_text()
            header=(root/'camera/CameraNode/Secrets.h').read_text()
            self.assertEqual(64,len(pi['api_key']))
            self.assertIn('api.token='+pi['api_key'],props)
            self.assertIn(pi['api_key'],header)
            self.assertIn('db.password='+configure.prop(passwords[0]),props)
            self.assertEqual('http://192.168.1.50:8080',pi['server_url'])
            self.assertEqual(0o600,(root/'server/config.properties').stat().st_mode&0o777)
    def test_java_property_escaping(self):
        self.assertEqual(r'a\ b\:\=\!',configure.prop('a b:=!'))
        self.assertEqual(r'a\\b',configure.prop('a\\b'))
        self.assertEqual(r'\u00e9',configure.prop('é'))
if __name__=='__main__':unittest.main()
