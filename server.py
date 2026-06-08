import os
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import requests

# Указываем Flask, что статичные файлы лежат в папке static
app = Flask(__name__, static_folder="static")

# Сюда вставьте ваши настоящие данные Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
CHAT_ID = os.environ.get("CHAT_ID", "ВАШ_ID_ЧАТА")


def send_photo_to_telegram(img_data):
    """Исправленная функция отправки бинарных данных в Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    files = {"photo": ("capture.jpg", img_data, "image/jpeg")}
    caption = f"📸 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    payload = {"chat_id": CHAT_ID, "caption": caption}

    try:
        response = requests.post(url, files=files, data=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки в TG: {e}")
        return False


@app.route("/")
def index():
    """Отдаем главную страницу из папки static."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/upload", methods=["POST"])
def upload_image():
    """Принимаем фото от фронтенда."""
    if "photo" not in request.files:
        return jsonify({"error": "Файл не найден"}), 400

    file = request.files["photo"]
    img_data = file.read()  # Читаем в байты

    if send_photo_to_telegram(img_data):
        return jsonify({"status": "success", "message": "Фото улетело в Telegram!"})
    else:
        return (
            jsonify({"status": "error", "message": "Ошибка отправки в Telegram"}),
            500,
        )


if __name__ == "__main__":
    # На Render порт выдается динамически через переменную окружения PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
