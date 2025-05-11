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

    signature = request.headers.get("X-Hub-Signature", "")
    if not verify_signature(request.data, signature, WEBHOOK_SECRET):
        return "Signature mismatch", 403
    print("verify_signature success")

    xml = request.data.decode("utf-8")
    print(xml)

    # 清理命名空间前缀
    xml = xml.replace("yt:", "yt_").replace("media:", "media_")

    root = ET.fromstring(xml)

    for entry in root.findall(".//entry"):
        video_id = entry.find("yt_videoId").text if entry.find("yt_videoId") is not None else ""
        channel_id = entry.find("yt_channelId").text if entry.find("yt_channelId") is not None else ""
        title = entry.find("title").text if entry.find("title") is not None else ""
        published = entry.find("published").text if entry.find("published") is not None else ""
        author_elem = entry.find("author")
        author_name = author_elem.find("name").text if author_elem is not None and author_elem.find("name") is not None else ""
        link = f"https://www.youtube.com/watch?v={video_id}"

        payload = {
            "inputs": {
                "video_id": video_id,
                "channel_id": channel_id,
                "title": title,
                "published_at": published,
                "author": author_name,
                "video_url": link
            },
            "response_mode": "blocking",
            "user": "youtube-auto"
        }

        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(DIFY_URL, json=payload, headers=headers)
        print("Dify response:", response.status_code, response.text)

    return "", 204
