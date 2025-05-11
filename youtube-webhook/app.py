from flask import Flask, request
import hmac
import hashlib
import requests
import os
from lxml import etree

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

    xml = request.data.decode("utf-8")
    print(xml)

    try:
        root = etree.fromstring(xml.encode('utf-8'))
    except Exception as e:
        print("XML Parse Error:", e)
        return "Invalid XML", 400

    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        video_id = entry.find(".//{http://www.youtube.com/xml/schemas/2015}videoId").text
        channel_id = entry.find(".//{http://www.youtube.com/xml/schemas/2015}channelId").text
        title = entry.find(".//{http://search.yahoo.com/mrss/}title").text
        description = entry.find(".//{http://search.yahoo.com/mrss/}description").text
        thumbnail = entry.find(".//{http://search.yahoo.com/mrss/}thumbnail").attrib.get("url")
        publish_time = entry.find(".//{http://www.w3.org/2005/Atom}published").text
        author = entry.find(".//{http://www.w3.org/2005/Atom}name").text
        link = f"https://www.youtube.com/watch?v={video_id}"

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
            "user": "soulxhy"
        }

        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(DIFY_URL, json=payload, headers=headers)
        print("Dify response:", response.status_code, response.text)

    return "", 204
