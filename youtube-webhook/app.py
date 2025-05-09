from flask import Flask, request
import hmac
import hashlib
import xml.etree.ElementTree as ET
import requests
import os

app = Flask(__name__)

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_URL = os.getenv("DIFY_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

def verify_signature(request_data, x_hub_signature, secret):
    expected = 'sha1=' + hmac.new(
        secret.encode('utf-8'),
        request_data,
        hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected, x_hub_signature)

@app.route("/youtube-webhook", methods=["GET", "POST"])
def youtube_webhook():
    if request.method == "GET":
        return request.args.get("hub.challenge", ""), 200

    # 验证签名
    signature = request.headers.get("X-Hub-Signature", "")
    if not verify_signature(request.data, signature, WEBHOOK_SECRET):
        return "Signature mismatch", 403

    # 解析 XML
    root = ET.fromstring(request.data.decode("utf-8"))
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        video_id = entry.find("{http://www.youtube.com/xml/schemas/2015}videoId").text
        title = entry.find("{http://www.w3.org/2005/Atom}title").text
        publish_time = entry.find("{http://www.w3.org/2005/Atom}published").text
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # 调用 Dify API
        payload = {
            "inputs": {
                "video_url": video_url,
                "title": title,
                "published_at": publish_time
            },
            "response_mode": "blocking",
            "user": "youtube-auto"
        }

        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(DIFY_URL, json=payload, headers=headers)
        print("Dify response:", response.json())

    return "", 204
