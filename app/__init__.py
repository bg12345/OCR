from flask import Flask
from dotenv import load_dotenv
from flask_pymongo import PyMongo
from botocore.config import Config
import os,boto3,urllib

load_dotenv()

app=Flask(__name__)
app.config["MONGO_URI"]=os.getenv("MONGO_URI") or f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}/{os.getenv('MONGO_DB')}"
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
