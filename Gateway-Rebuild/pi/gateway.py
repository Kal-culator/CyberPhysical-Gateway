#!/usr/bin/env python3
"""Gateway V2: independent checks, bounded pulses, fail-closed server decisions."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time
import uuid
import urllib.request
import urllib.error
from contextlib import contextmanager
from hardware import Outputs,Fingerprint,Display,MPU

ROOT=Path(__file__).resolve().parent

def load(path):
    try:
        c=json.loads(Path(path).read_text())
    except FileNotFoundError:raise ValueError('config.json missing. Run tools/configure.py on the Mac and copy its pi/config.json here.')
    except json.JSONDecodeError as e:raise ValueError(f'Invalid config JSON on line {e.lineno}: {e.msg}. Use config.example.json as the template.')
    if not isinstance(c,dict):raise ValueError('Configuration must be a JSON object')
    required=json.loads((ROOT/'config.example.json').read_text())
    missing=set(required)-set(c)
    if missing:raise ValueError('Missing config fields: '+', '.join(sorted(missing)))
    for k in ('lcd_enabled','mpu_enabled','relay_active_high'):
        if type(c[k]) is not bool:raise ValueError(k+' must be true or false')
    for k,maximum in [('unlock_seconds',1),('buzzer_seconds',2)]:
        if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not 0<c[k]<=maximum:raise ValueError(k+' outside safe pulse range')
    if c['buzzer_gpio']!=27 or c['lock_gpio']!=22:raise ValueError('This build is wired for BCM27 buzzer and BCM22 lock. Review wiring before changing software.')
    for k in ('lcd_address','mpu_address'):
        if not 0x03<=int(c[k],0)<=0x77:raise ValueError('Invalid I2C address')
    for k,low,high in [('minimum_confidence',1,1000),('approval_timeout_seconds',5,60),('motion_samples',1,100),('tamper_cooldown_seconds',1,300)]:
        if type(c[k]) is not int or not low<=c[k]<=high:raise ValueError('Invalid '+k)
    for k in ('motion_delta_g','motion_gyro_dps'):
        if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or c[k]<=0:raise ValueError('Invalid '+k)
    if c['device_id']!='door-1':raise ValueError('Use device_id door-1 for this single-door demo')
    return c

class API:
    def __init__(self,cfg,simulation=False):self.c=cfg;self.simulation=simulation
    def call(self,path,data=None):
        if 'YOUR_MAC' in self.c['server_url'] or len(self.c['api_key'])<32 or 'CHANGE_ME' in self.c['api_key']:raise ValueError('Set server_url and api_key using tools/configure.py first')
        body=None if data is None else json.dumps(data).encode()
        request=urllib.request.Request(self.c['server_url'].rstrip('/')+path,data=body,headers={'X-API-Key':self.c['api_key'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=3) as response:
                raw=response.read(65537)
                if len(raw)>65536:raise RuntimeError('Server response too large')
                result=json.loads(raw)
        except urllib.error.HTTPError as e:raise RuntimeError(f'Server HTTP {e.code}: check API key, server logs and configuration') from None
        except (urllib.error.URLError,TimeoutError):raise RuntimeError('Server unavailable: check Mac IP, Wi-Fi and Java server') from None
        except json.JSONDecodeError:raise RuntimeError('Server returned non-JSON; check that this is Gateway V2 on port 8080') from None
        if not isinstance(result,dict):raise RuntimeError('Invalid server response')
        if result.get('simulation') and not self.simulation:raise RuntimeError('Simulation server cannot control physical hardware')
        return result
    def access(self,finger,confidence,force=False):
        return self.call('/api/access',{'request_id':str(uuid.uuid4()),'device_id':self.c['device_id'],'fingerprint_id':finger,'confidence':confidence,'force_review':force})

class MotionDetector:
    def __init__(self,baseline,cfg):self.baseline=baseline;self.c=cfg;self.count=0
    def update(self,acc,gyro):
        delta=math.sqrt(sum((a-b)**2 for a,b in zip(acc,self.baseline)))
        moved=delta>self.c['motion_delta_g'] or max(map(abs,gyro))>self.c['motion_gyro_dps']
        self.count=self.count+1 if moved else 0
        return self.count>=self.c['motion_samples']

class Motion:
    def __init__(self,cfg):self.c=cfg;self.events=queue.Queue(maxsize=1);self.stop=threading.Event();self.thread=None
    def put(self,reason):
        try:self.events.put_nowait(reason)
        except queue.Full:pass
    def start(self):
        if not self.c['mpu_enabled']:return
        self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start()
    def worker(self):
        last=0
        try:
            with MPU(self.c) as m:
                samples=[]
                for _ in range(20):
                    if self.stop.wait(.05):return
                    samples.append(m.read()[0])
                baseline=[sum(s[i] for s in samples)/len(samples) for i in range(3)]
                detector=MotionDetector(baseline,self.c)
                print('MPU monitoring armed; baseline captured. Keep housing fixed.',flush=True)
                while not self.stop.wait(.1):
                    moved=detector.update(*m.read())
                    if moved and time.monotonic()-last>self.c['tamper_cooldown_seconds']:
                        self.put('MPU_MOTION');last=time.monotonic()
        except Exception:self.put('MPU_OFFLINE')
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=2)

@contextmanager
def exclusive():
    # Shared across project copies for the same Pi user; prevents two relay/fingerprint owners.
    path=Path.home()/'.gateway-v2-hardware.lock'
    with path.open('a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another Gateway V2 hardware command is running. Stop it with Ctrl+C.')
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)

def wait_decision(api,result,cfg,tick=lambda:False):
    deadline=time.monotonic()+cfg['approval_timeout_seconds']+5
    while result.get('action')=='PENDING':
        if tick():return {'action':'DENY','reason':'LOCAL_TAMPER'}
        if time.monotonic()>=deadline:return {'action':'DENY','reason':'CLIENT_TIMEOUT'}
        time.sleep(.4)
        result=api.call('/api/requests/'+result['request_id'])
    if result.get('action') not in ('OPEN','DENY'):raise RuntimeError('Invalid server action; access denied')
    return result

def run(cfg):
    api=API(cfg);motion=Motion(cfg)
    with exclusive(),Outputs(cfg) as outputs,Display(cfg) as display,Fingerprint(cfg) as finger:
        finger.ids();api.call('/health')
        sequence=api.call('/api/security')['sequence'];last_poll=0;quiet_until=0
        motion.start()
        def tick():
            nonlocal sequence,last_poll,quiet_until
            reason=None
            try:reason=motion.events.get_nowait()
            except queue.Empty:pass
            if reason:
                outputs.off();quiet_until=time.monotonic()+5
                try:api.call('/api/tamper',{'reason':reason})
                except Exception as e:print(e,flush=True)
                display.show('TAMPER WARNING',reason);outputs.pulse('buzzer')
                return True
            if time.monotonic()-last_poll>=2:
                last_poll=time.monotonic()
                try:
                    sec=api.call('/api/security');new=sec['sequence']
                    if new!=sequence:
                        sequence=new;quiet_until=time.monotonic()+5
                        display.show('SECURITY WARNING',sec['reason']);outputs.pulse('buzzer');return True
                    if sec['blocked']:quiet_until=time.monotonic()+2
                except Exception as e:print(e,flush=True)
            return time.monotonic()<quiet_until
        try:
            waiting_for_lift=False;display.show('SMART DOOR','Put fingerprint')
            while True:
                if tick():time.sleep(.2);continue
                try:state,slot,confidence=finger.scan()
                except Exception:
                    outputs.off()
                    try:api.call('/api/tamper',{'reason':'FINGERPRINT_OFFLINE'})
                    except Exception:pass
                    outputs.pulse('buzzer');raise
                if state=='EMPTY':
                    if waiting_for_lift:display.show('SMART DOOR','Put fingerprint')
                    waiting_for_lift=False;time.sleep(.1);continue
                if waiting_for_lift:time.sleep(.1);continue
                if state=='RETRY':display.show('SCAN UNCLEAR','Lift and try again');waiting_for_lift=True;continue
                waiting_for_lift=True
                try:
                    display.show('CHECKING ACCESS')
                    result=api.access(slot,confidence)
                    if result['action']=='PENDING':display.show('UNKNOWN FINGER','Check Telegram','Answer within 30s')
                    result=wait_decision(api,result,cfg,tick)
                    # Recheck security immediately before any opening command.
                    security=api.call('/api/security')
                    allowed=result['action']=='OPEN' and not security['blocked'] and not tick()
                    if allowed:display.show('ACCESS GRANTED','Opening briefly');outputs.pulse('lock');display.show('LOCK POWER OFF','Remove finger')
                    else:display.show('ACCESS DENIED',result.get('reason',''));outputs.pulse('buzzer')
                except Exception as e:
                    outputs.off();display.show('SERVER UNAVAILABLE','Access denied');outputs.pulse('buzzer');print(e,flush=True)
        finally:motion.close();outputs.off()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.json'));s=p.add_subparsers(dest='command',required=True)
    for name in ('config-check','status','lcd-test','finger-info','mpu-test','server-test','telegram-test','run'):s.add_parser(name)
    for name in ('enroll','delete'):
        q=s.add_parser(name);q.add_argument('id',type=int)
        if name=='delete':q.add_argument('--confirm',action='store_true',required=True)
    q=s.add_parser('relay-test');q.add_argument('channel',type=int,choices=(1,2));q.add_argument('--confirm',action='store_true',required=True)
    q=s.add_parser('lock-test');q.add_argument('--confirm',action='store_true',required=True)
    args=p.parse_args();cfg=load(args.config);cmd=args.command
    if hasattr(args,'id') and not 1<=args.id<=127:raise ValueError('Use fingerprint IDs 1 through 127')
    if cmd=='config-check':print('Configuration valid. GPIO27 buzzer; GPIO22 deadbolt.');return
    if cmd=='server-test':
        api=API(cfg);print(api.call('/health'));print(api.call('/api/security'));return
    if cmd=='telegram-test':
        api=API(cfg);result=wait_decision(api,api.access(None,0,True),cfg);print('TEST ONLY (no relays):',result);return
    if cmd=='run':run(cfg);return
    with exclusive():
        if cmd in ('relay-test','lock-test'):
            channel=2 if cmd=='lock-test' else args.channel
            print('Testing channel',channel,'— this command switches its connected load.',flush=True)
            with Outputs(cfg) as outputs:time.sleep(1);outputs.pulse('lock' if channel==2 else 'buzzer')
            print('Finished: both outputs OFF.');return
        if cmd=='lcd-test':
            with Display(cfg) as display:display.show('GATEWAY V2','LCD working','20 x 4 display','Independent test')
            return
        if cmd=='mpu-test':
            with MPU(cfg) as m:
                for _ in range(30):a,g=m.read();print('Acceleration g:',[round(x,2) for x in a],'Gyro deg/s:',[round(x,1) for x in g]);time.sleep(.2)
            return
        if cmd=='status':
            failures=[]
            for name,cls in [('LCD',Display),('Fingerprint',Fingerprint),('MPU6050',MPU)]:
                try:
                    with cls(cfg) as hw:
                        if name=='LCD':hw.show('SYSTEM CHECK','LCD OK' if cfg['lcd_enabled'] else 'LCD disabled')
                        elif name=='Fingerprint':print('Stored IDs:',hw.ids())
                        else:hw.read()
                    print(name,'OK' if name!='LCD' or cfg['lcd_enabled'] else 'DISABLED')
                except Exception as e:print(name,'FAILED:',e);failures.append(name)
            if failures:raise RuntimeError('Failed modules: '+', '.join(failures))
            return
        with Fingerprint(cfg) as f:
            if cmd=='finger-info':print('Stored IDs:',f.ids())
            elif cmd=='enroll':f.enroll(args.id)
            elif cmd=='delete':
                if f.sensor.delete_model(args.id)!=f.af.OK:raise RuntimeError('Delete failed')
                print('Deleted sensor ID',args.id,'— database user is unchanged.')

if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    try:main()
    except KeyboardInterrupt:print('\nStopped; initialized relay outputs released.')
    except Exception as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
