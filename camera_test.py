import os
import time
from datetime import datetime
import boto3
import configparser
import sys

# Check if a non-default config file has been specified
if len(sys.argv) > 1:
  config_path = sys.argv[1]
else:
  config_path = "config.ini"
config = configparser.RawConfigParser()
config.read(config_path)

aws_access_key = config['AWS_S3_IMAGES']['access_key']
aws_secret_key = config['AWS_S3_IMAGES']['secret_key']
s3_upload_path = config['AWS_S3_IMAGES']['s3_upload_path']
s3_bucket = config['AWS_S3_IMAGES']['s3_bucket_name']
timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')

os.system(f"libcamera-still -e png -o /tmp/{timestamp}.png")

s3 = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key)
temp = s3.upload_file(f"/tmp/{timestamp}.png", s3_bucket, f"{s3_upload_path}/{timestamp}.png")

print(f"https://{s3_bucket}.s3.eu-central-1.amazonaws.com/{s3_upload_path}/{timestamp}.png")
