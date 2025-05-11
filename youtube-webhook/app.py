from flask import Flask, request
import hmac
import hashlib
import xml.etree.ElementTree as ET
import requests
import os
from pydantic import BaseModel
from loguru import logger
from fastapi import  BackgroundTasks
from typing import Optional, List
from youtube_service import YoutubeService

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

class DownloadVideoResponse(BaseModel):
    task_id: str
    output_path: str
    resolution: str
    format: str
    filename: str

class DownloadVideoRequest(BaseModel):
    url: str
    resolution: str
    output_format: Optional[str] = "mp4"
    rename: Optional[str] = None

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


@app.route(
    "/youtube/download",
    methods=["GET", "POST"],
    response_model=DownloadVideoResponse,
    summary="同步请求；下载YouTube视频 (V2)")
async def download_youtube_video(
        request: DownloadVideoRequest
):
    """
    下载指定分辨率的YouTube视频
    """
    try:
        youtube_service = YoutubeService()
        task_id, output_path, filename = await youtube_service.download_video(
            url=request.url,
            resolution=request.resolution,
            output_format=request.output_format,
            rename=request.rename
        )

        return {
            "task_id": task_id,
            "output_path": output_path,
            "resolution": request.resolution,
            "format": request.output_format,
            "filename": filename
        }

    except Exception as e:
        logger.exception(f"Download YouTube video failed: {str(e)}")
        raise
