from flask import Flask
from dotenv import load_dotenv
from flask_pymongo import PyMongo
import os,boto3,urllib

load_dotenv()

app=Flask(__name__)
app.config["MONGO_URI"]=f"mongodb+srv://{os.getenv('MONGO_USERNAME')}:{urllib.parse.quote(os.getenv('MONGO_PASSWORD'))}" \
                        f"@{os.getenv('MONGO_HOST')}/{os.getenv('MONGO_DB')}?retryWrites=true&w=majority"
mongo=PyMongo(app)
s3=boto3.client("s3",aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("AWS_ACCESS_SECRET"))