#!/usr/bin/env bash
set -euo pipefail

read -r -s -p 'Telegram bot token from BotFather: ' bot_token
echo
echo 'First open your bot in Telegram, press Start, and send it hello.'
read -r -p 'Press Enter after sending hello...'

response_file="$(mktemp)"
trap 'rm -f -- "$response_file"' EXIT
printf 'url = "https://api.telegram.org/bot%s/getUpdates"\n' "$bot_token" \
  | curl --fail --silent --show-error --config - > "$response_file"

python3 - "$response_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)

chats = {}
for update in response.get("result", []):
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    if "id" in chat:
        label = chat.get("username") or chat.get("first_name") or chat.get("title") or "unnamed"
        chats[str(chat["id"])] = label

if not chats:
    raise SystemExit("No chat found. Send the bot a message and run this helper again.")
for chat_id, label in chats.items():
    print(f"Chat ID: {chat_id}  ({label})")
PY
