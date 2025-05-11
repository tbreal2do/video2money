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
    
    # 注册命名空间，防止解析失败
    ET.register_namespace('yt', "http://www.youtube.com/xml/schemas/2015")
    ET.register_namespace('media', "http://search.yahoo.com/mrss/")
    ET.register_namespace('atom', "http://www.w3.org/2005/Atom")
    
    xml = request.data.decode("utf-8")
    print(xml)

    root = ET.fromstring(xml)

    for entry in root.findall("entry"):
        video_id = entry.findtext("videoId")
        channel_id = entry.findtext("channelId")
        title = entry.findtext("title")
        publish_time = entry.findtext("published")
        author_elem = entry.find("author")
        author = author_elem.findtext("name") if author_elem is not None else ""
        link_elem = entry.find("link")
        link = link_elem.attrib.get("href") if link_elem is not None else f"https://www.youtube.com/watch?v={video_id}"

        media_group = entry.find("group")
        description = thumbnail = ""
        if media_group is not None:
            title = media_group.findtext("title") or title
            description = media_group.findtext("description") or ""
            thumbnail_elem = media_group.find("thumbnail")
            if thumbnail_elem is not None:
                thumbnail = thumbnail_elem.attrib.get("url", "")

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
