#!/usr/bin/env python3
"""Run on the Mac. Writes local ignored configs, never changes live hardware or databases."""
from pathlib import Path
import getpass
import ipaddress
import json
import os
import secrets
ROOT=Path(__file__).resolve().parents[1]

def prop(value):
    # Java Properties.load(InputStream) uses Latin-1 escapes.
    out=''
    for c in str(value):
        if c=='\\':out+='\\\\'
        elif c=='\n':out+='\\n'
        elif c=='\r':out+='\\r'
        elif c=='\t':out+='\\t'
        elif c in ' =:#!':out+='\\'+c
        elif ord(c)>127:
            for i in range(0,len(c.encode('utf-16-be')),2):out+='\\u'+c.encode('utf-16-be')[i:i+2].hex()
        else:out+=c
    return out

def write(path,text):
    if path.exists():
        backup=path.with_name(path.name+'.previous')
        # A fixed local backup, also ignored by git.
        backup.write_bytes(path.read_bytes());os.chmod(backup,0o600)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)
    os.chmod(path,0o600)

def main():
    paths=[ROOT/'server/config.properties',ROOT/'pi/config.json',ROOT/'camera/CameraNode/Secrets.h']
    if any(p.exists() for p in paths):
        if input('Replace existing local configurations and rotate the shared key? Type REPLACE: ')!='REPLACE':return
    host=input('Mac IPv4 address on your Wi-Fi (example 192.168.1.50): ').strip()
    ip=ipaddress.ip_address(host)
    if ip.version!=4 or ip.is_loopback or ip.is_unspecified:raise ValueError('Use the Mac Wi-Fi IPv4 address, not localhost')
    dbuser=input('MySQL user [gateway]: ').strip() or 'gateway'
    dbpass=getpass.getpass('MySQL password for that user: ')
    bot=getpass.getpass('Telegram bot token (blank disables Telegram): ').strip()
    chat=owner=''
    if bot:
        chat=input('Telegram chat ID: ').strip();owner=input('Telegram owner user ID (same as chat ID for a private chat): ').strip()
        int(chat);int(owner)
    ssid=input('Camera 2.4 GHz Wi-Fi name: ')
    wifi=getpass.getpass('Camera Wi-Fi password: ')
    token=secrets.token_hex(32)
    props={'server.bind':'0.0.0.0','server.port':8080,'api.token':token,'simulation':'false',
      'db.url':'jdbc:mysql://localhost:3306/cyberphysical_v2?connectTimeout=3000&socketTimeout=5000','db.user':dbuser,'db.password':dbpass,
      'telegram.token':bot,'telegram.chat_id':chat,'telegram.owner_id':owner,'approval.seconds':30,'minimum.confidence':50,
      'camera.monitor':'false','camera.dark_threshold':18,'camera.dark_frames':4}
    write(paths[0],'# Local secrets. Do not publish.\n'+''.join(prop(k)+'='+prop(v)+'\n' for k,v in props.items()))
    cfg=json.loads((ROOT/'pi/config.example.json').read_text());cfg['server_url']='http://'+host+':8080';cfg['api_key']=token
    write(paths[1],json.dumps(cfg,indent=2)+'\n')
    header='#pragma once\n'
    for k,v in {'WIFI_SSID':ssid,'WIFI_PASSWORD':wifi,'SERVER_URL':cfg['server_url'],'API_KEY':token}.items():header+='#define '+k+' '+json.dumps(v,ensure_ascii=False)+'\n'
    write(paths[2],header)
    print('Created server/config.properties, pi/config.json and camera/CameraNode/Secrets.h.')
    print('Copy pi/config.json privately to the Pi. Flash the camera with its Secrets.h. Do not commit these files.')
if __name__=='__main__':
    try:main()
    except (ValueError,KeyboardInterrupt) as e:raise SystemExit(str(e) or 'Cancelled')
