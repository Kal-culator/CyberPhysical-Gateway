#!/usr/bin/env python3
"""Offline integration tests: fake camera and Telegram; no GPIO, webcam or real messages."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent


class WebcamFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.build = Path(cls.tmp.name)
        subprocess.run(['javac', '--release', '11', '-d', str(cls.build),
                        *map(str, (ROOT / 'src/main/java').glob('*.java'))], check=True)
        cls.helper = cls.build / 'camera.py'
        cls.helper.write_text('''import os, sys, time
from pathlib import Path
mode = os.environ['TEST_CAMERA']
if mode == 'hang': time.sleep(30)
if mode == 'fail': sys.exit(1)
out = Path(sys.argv[sys.argv.index('--output') + 1])
out.write_bytes(b'bad' if mode == 'invalid' else b'\\xff\\xd8test-photo\\xff\\xd9')
''')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def exercise(self, answer='YES', camera='ok', upload_failure=False,
                 cleanup_failure=False, decision='REVIEW'):
        calls = []
        state = {'request': None, 'answered': False}

        class Telegram(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                method = self.path.rsplit('/', 1)[-1]
                body = self.rfile.read(int(self.headers['Content-Length']))
                calls.append((method, body))
                status = 200
                result = {'ok': True, 'result': True}
                if method in ('sendPhoto', 'sendMessage'):
                    text = body.decode('utf-8', errors='replace')
                    if method == 'sendMessage': text = str(parse_qs(text))
                    state['request'] = re.search(r'YES:([a-f0-9]+)', text).group(1)
                    result['result'] = {'message_id': 123}
                    if upload_failure:
                        status, result = 500, {'ok': False}
                elif method == 'getUpdates':
                    result['result'] = []
                    if state['request'] and answer and not state['answered']:
                        state['answered'] = True
                        result['result'] = [{'update_id': 1, 'callback_query': {
                            'id': 'cb1', 'data': answer + ':' + state['request']}}]
                    else:
                        time.sleep(.03)
                elif cleanup_failure and method in ('answerCallbackQuery', 'editMessageCaption'):
                    status, result = 500, {'ok': False}
                data = json.dumps(result).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        api = ThreadingHTTPServer(('127.0.0.1', 0), Telegram)
        threading.Thread(target=api.serve_forever, daemon=True).start()
        with socket.socket() as available:
            available.bind(('127.0.0.1', 0))
            port = available.getsockname()[1]
        env = dict(os.environ, SERVER_PORT=str(port), APPROVAL_TIMEOUT_SECONDS='1',
                   TELEGRAM_API_BASE=f'http://127.0.0.1:{api.server_port}',
                   TELEGRAM_BOT_TOKEN='fake', TELEGRAM_CHAT_ID='123',
                   WEBCAM_PYTHON=sys.executable, WEBCAM_SCRIPT=str(self.helper), TEST_CAMERA=camera)
        process = subprocess.Popen(['java', '-cp', str(self.build), 'GatewayServer'], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    connection = socket.create_connection(('127.0.0.1', port), .2)
                    break
                except OSError:
                    if time.monotonic() > deadline: raise
                    time.sleep(.05)
            with connection:
                connection.settimeout(15)
                event = dict(device_id='door-1', fingerprint_id=None, confidence=0,
                             pi_decision=decision, relay_channel=0)
                connection.sendall(json.dumps(event).encode() + b'\n')
                response = json.loads(connection.makefile('r').readline())
            return response, calls
        finally:
            process.terminate()
            process.wait(timeout=5)
            api.shutdown()
            api.server_close()

    def test_photo_yes(self):
        response, calls = self.exercise()
        self.assertEqual(response['action'], 'OPEN')
        photo = next(body for method, body in calls if method == 'sendPhoto')
        self.assertIn(b'name="caption"', photo)
        self.assertIn(b'name="reply_markup"', photo)
        self.assertIn(b'\xff\xd8test-photo\xff\xd9', photo)
        self.assertIn('editMessageCaption', [method for method, _ in calls])

    def test_photo_no(self):
        response, _ = self.exercise(answer='NO')
        self.assertEqual(response, {'action': 'BUZZER', 'telegram_decision': 'NO'})

    def test_timeout(self):
        response, _ = self.exercise(answer=None)
        self.assertEqual(response, {'action': 'BUZZER', 'telegram_decision': 'TIMEOUT'})

    def test_camera_failure_fallback(self):
        for camera in ('fail', 'invalid', 'hang'):
            with self.subTest(camera=camera):
                response, calls = self.exercise(camera=camera)
                self.assertEqual(response['action'], 'OPEN')
                self.assertNotIn('sendPhoto', [m for m, _ in calls])
                message = next(b for m, b in calls if m == 'sendMessage')
                self.assertIn('Photo unavailable', parse_qs(message.decode())['text'][0])

    def test_upload_failure_denies(self):
        response, _ = self.exercise(upload_failure=True)
        self.assertEqual(response, {'action': 'BUZZER', 'telegram_decision': 'ERROR'})

    def test_cosmetic_failure_preserves_yes(self):
        response, _ = self.exercise(cleanup_failure=True)
        self.assertEqual(response['action'], 'OPEN')

    def test_registered_finger_does_not_capture(self):
        response, calls = self.exercise(decision='GRANTED', camera='fail')
        self.assertEqual(response['action'], 'OPEN')
        self.assertFalse(any(m in ('sendPhoto', 'sendMessage') for m, _ in calls))


if __name__ == '__main__':
    unittest.main()
