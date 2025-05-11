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

    # 定义命名空间
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/"
    }

    root = ET.fromstring(request.data.decode("utf-8"))

    for entry in root.findall("atom:entry", ns):
        video_id = entry.find("yt:videoId", ns).text
        channel_id = entry.find("yt:channelId", ns).text
        title = entry.find("media:group/media:title", ns).text
        description = entry.find("media:group/media:description", ns).text
        thumbnail = entry.find("media:group/media:thumbnail", ns).attrib.get("url")
        publish_time = entry.find("atom:published", ns).text
        author = entry.find("atom:author/atom:name", ns).text
        link = f"https://www.youtube.com/watch?v={video_id}"

        # 构造发送给 Dify 的 payload
        payload = {
            "inputs": {
                "video_id": video_id,
                "channel_id": channel_id,
                "title": title,
                "description": description,
                "thumbnail": thumbnail,
                "published_at": publish_time,
                "author": author,
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
