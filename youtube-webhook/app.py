import sys
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr
from aiosmtplib import send
from email.message import EmailMessage
import hmac
import hashlib
import xml.etree.ElementTree as ET
import requests
import os
from loguru import logger
from typing import Optional
from youtube_service import YoutubeService
from dotenv import load_dotenv

# 添加控制台输出
logger.add(sys.stdout, level="INFO", format="{time} {level} {message}")

load_dotenv()

app = FastAPI()

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_URL = os.getenv("DIFY_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


def verify_signature(request_data: bytes, x_hub_signature: str, secret: str) -> bool:
    expected = 'sha1=' + hmac.new(
        secret.encode('utf-8'),
        request_data,
        hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected, x_hub_signature)


class DownloadVideoRequest(BaseModel):
    url: str
    resolution: str
    output_format: Optional[str] = "mp4"
    rename: Optional[str] = None

class DownloadVideoResponse(BaseModel):
    task_id: str
    output_path: str
    resolution: str
    format: str
    filename: str

@app.get("/youtube-webhook")
async def youtube_webhook_get(hub_challenge: Optional[str] = Query(None, alias="hub.challenge")):
    return PlainTextResponse(content=hub_challenge or "", status_code=200)

class BwfVideoInfo(BaseModel):
    video_id: str
    channel_id: str
    title: str
    published_at: str
    author: str
    video_url: str

@app.post("/youtube-webhook")
async def youtube_webhook_post(request: Request):
    logger.info("request",request)
    signature = request.headers.get("X-Hub-Signature", "")
    raw_body = await request.body()

    if not verify_signature(raw_body, signature, WEBHOOK_SECRET):
        return PlainTextResponse("Signature mismatch", status_code=403)

    xml = raw_body.decode("utf-8")

    # 定义命名空间
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015',
        'media': 'http://search.yahoo.com/mrss/'
    }

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        logger.error(f"XML Parse Error: {str(e)}")
        return PlainTextResponse("Invalid XML", status_code=400)

    # 提取基本字段
    video_id = root.find('yt:videoId', namespaces).text
    channel_id = root.find('yt:channelId', namespaces).text
    title = root.find('title').text
    link = root.find('link').attrib.get('href')
    author = root.find('author/name').text
    published = root.find('published').text

    # 提取 media 相关字段
    media_title = root.find('media:group/media:title', namespaces).text
    media_description = root.find('media:group/media:description', namespaces).text
    media_thumbnail = root.find('media:group/media:thumbnail', namespaces).attrib.get('url')
    views = root.find('media:group/media:community/media:statistics', namespaces).attrib.get('views')
    rating = root.find('media:group/media:community/media:starRating', namespaces).attrib.get('average')

    bwf_info= BwfVideoInfo(
                video_id = video_id,
                channel_id = channel_id,
                title = title,
                published_at= published,
                author = author,
                video_url= link,
                description = media_description
        )
    download_info =  await download_youtube_video(DownloadVideoRequest(url=link,  resolution="1080p"))
    await send_email2me(Email2MeRequest(video_download_info=download_info, bwf_video_info=bwf_info))

    return PlainTextResponse(status_code=204)


@app.post("/youtube/download",
          response_model=DownloadVideoResponse,
          summary="同步请求；下载YouTube视频 (V2)")
async def download_youtube_video(request: DownloadVideoRequest):
    try:
        youtube_service = YoutubeService()
        task_id, output_path, filename = await youtube_service.download_video(
            url=request.url,
            resolution=request.resolution,
            output_format=request.output_format,
            rename=request.rename
        )
        logger.exception(f"Download YouTube video successfully")
        return DownloadVideoResponse(
            task_id = task_id,
            output_path = output_path,
            resolution = request.resolution,
            format = request.output_format,
            filename = filename)

    except Exception as e:
        logger.exception(f"Download YouTube video failed: {str(e)}")
        return PlainTextResponse("Failed to download video", status_code=500)


# 从环境变量加载 SMTP 配置
SMTP_HOST = os.getenv("SMTP_HOST")      # 例如 smtp.gmail.com
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")      # 发件人邮箱
SMTP_PASS = os.getenv("SMTP_PASS")      # 授权码或密码
MY_EMAIL = os.getenv("MY_EMAIL")      # 收件人邮箱

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str


class Email2MeRequest(BaseModel):
    video_download_info: DownloadVideoResponse
    bwf_video_info: BwfVideoInfo


email_template = """
您好，

我们刚刚收到了一个新视频，欢迎查看并下载观看！以下是本次视频的详细信息：

📌 标题：{title}
🕒 发布时间：{publish_time}
✍️ 作者：{author}
📝 视频描述：
{description}

📥 下载链接：
{download_link}

如果您有任何反馈或建议，欢迎随时回复本邮件与我们联系。

感谢您的关注与支持！

祝好，  
{sender_name}
"""

async def send_email2me(req: Email2MeRequest):
    subject = """🎬 新视频发布通知 |《{title}》"""
    email_content = email_template.format(
        title=req.bwf_video_info.title,
        publish_time=req.bwf_video_info.publish_time,
        author=req.bwf_video_info.author,
        description=req.bwf_video_info.description,
        download_link=req.video_download_info.output_path,
        sender_name="soul"
    )
    eq = EmailRequest(
        to=MY_EMAIL,
        subject=subject,
        body=email_content
    )
    send_email(eq)


@app.post("/send-email")
async def send_email(req: EmailRequest):
    message = EmailMessage()
    message["From"] = SMTP_USER
    message["To"] = req.to
    message["Subject"] = req.subject
    message.set_content(req.body)

    try:
        await send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            start_tls=True
        )
        logger.info(message["Subject"],f"Email sent successfully to {req.to}")
        return {"message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")


# 可选：添加自动启动支持（仅用于调试）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
