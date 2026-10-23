#!/usr/bin/env python3
"""Real HTTP integration test with disposable in-memory SQL. No Telegram or physical hardware."""
from pathlib import Path
import json,subprocess,tempfile,time,urllib.request,urllib.error,socket,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pi'))
from gateway import API,load

def main():
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    token='integration-test-key-'+'a'*48
    with tempfile.TemporaryDirectory() as folder:
        config=Path(folder)/'test.properties'
        config.write_text(f'server.bind=127.0.0.1\nserver.port={port}\napi.token={token}\nsimulation=true\napproval.seconds=5\n')
        with (Path(folder)/'server.log').open('w+') as log:
            proc=subprocess.Popen(['java','-jar',str(ROOT/'server/target/gateway-server-1.0.0.jar'),str(config)],stdout=log,stderr=log)
            try:
                base=f'http://127.0.0.1:{port}'
                for _ in range(80):
                    if proc.poll() is not None:log.seek(0);raise RuntimeError(log.read())
                    try:urllib.request.urlopen(base+'/health',timeout=.2).close();break
                    except Exception:time.sleep(.1)
                else:raise RuntimeError('Server did not start')
                c=load(ROOT/'pi/config.example.json');c.update(server_url=base,api_key=token)
                api=API(c,simulation=True)
                assert api.call('/health')['simulation']
                try:API(c).call('/health');raise AssertionError('Physical client accepted simulation')
                except RuntimeError:pass
                try:urllib.request.urlopen(base+'/api/events');raise AssertionError('Missing auth accepted')
                except urllib.error.HTTPError as e:assert e.code==401
                known=api.access(1,90);assert known['action']=='OPEN'
                unknown=api.access(None,0);assert unknown['action']=='PENDING'
                assert api.call('/api/simulate/decision',{'request_id':unknown['request_id'],'approve':True})['accepted']
                assert api.call('/api/requests/'+unknown['request_id'])['action']=='OPEN'
                assert not api.call('/api/simulate/decision',{'request_id':unknown['request_id'],'approve':True})['accepted']
                denied=api.access(None,0);api.call('/api/simulate/decision',{'request_id':denied['request_id'],'approve':False})
                assert api.call('/api/requests/'+denied['request_id'])['action']=='DENY'
                pending=api.access(None,0);time.sleep(5.2)
                assert api.call('/api/requests/'+pending['request_id'])['reason']=='TIMEOUT'
                pending=api.access(None,0);api.call('/api/tamper',{'reason':'MPU_MOTION'})
                assert api.call('/api/requests/'+pending['request_id'])['action']=='DENY'
                assert api.call('/api/security')['blocked']
                assert api.access(1,90)['action']=='DENY'
                assert len(api.call('/api/events')['events'])>=6
                print('PASS: HTTP auth, registered access, approval, denial, timeout, replay protection, tamper cancellation and physical/simulation separation.')
            finally:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':main()
