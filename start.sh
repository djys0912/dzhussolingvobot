#!/bin/bash
# Создаем директорию для секретов и размещаем ключ Firebase
mkdir -p /etc/secrets/
echo "$FIREBASE_AUTH" > /etc/secrets/firebase_key.json
chmod 600 /etc/secrets/firebase_key.json

# Запускаем бота
python3 bot.py
