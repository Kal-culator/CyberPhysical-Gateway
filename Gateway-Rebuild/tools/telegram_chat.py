#!/usr/bin/env python3
"""Read your bot's recent updates; does not send a message. Stop the Java server first."""
import getpass,json,urllib.request,urllib.error
try:
    token=getpass.getpass('Bot token: ').strip()
    input('Open YOUR bot in Telegram, press Start and send hello. Then press Enter here. ')
    url='https://api.telegram.org/bot'+token+'/getUpdates'
    with urllib.request.urlopen(url,timeout=15) as r:data=json.load(r)
    found=set()
    for update in data.get('result',[]):
        m=update.get('message',{})
        if 'chat' in m and 'from' in m:
            pair=(m['chat']['id'],m['from']['id'])
            if pair not in found:print('Chat ID:',pair[0],'Owner user ID:',pair[1]);found.add(pair)
    if not found:print('No messages found. Send hello to your bot, not BotFather. Stop other bot pollers and retry.')
except urllib.error.HTTPError as e:print('Telegram HTTP',e.code,'— check token; do not share it in screenshots.')
except Exception:print('Could not read Telegram updates. Check internet/token and retry.')
