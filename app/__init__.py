from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_pymongo import PyMongo
from botocore.config import Config
from time import time
import os,boto3,urllib

load_dotenv()

app=Flask(__name__)
app.config["MONGO_URI"]=os.getenv("MONGO_URI") or f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}/{os.getenv('MONGO_DB')}"
app.config["MAX_CONTENT_LENGTH"]=int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
mongo=PyMongo(app)
s3=boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_ACCESS_SECRET"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"}
    )
)

rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
rate_limit_paths = {"/pan_ocr", "/dl_ocr", "/aadhaar_ocr"}
request_log = {}


@app.before_request
def rate_limit_ocr_endpoints():
    if request.path not in rate_limit_paths:
        return None

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    now = time()
    timestamps = [
        timestamp for timestamp in request_log.get(client_ip, [])
        if now - timestamp < rate_limit_window
    ]

    if len(timestamps) >= rate_limit_requests:
        return jsonify({
            "message": "Too many requests. Please try again later."
        }), 429

    timestamps.append(now)
    request_log[client_ip] = timestamps
    return None


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "message": f"File too large. Maximum upload size is {os.getenv('MAX_UPLOAD_MB', '10')} MB."
    }), 413
