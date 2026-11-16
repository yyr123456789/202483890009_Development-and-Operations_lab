#!/usr/bin/env python3
"""
Week 4 exercise - subprocess.run + S3 static website hosting

1. use subprocess.run to run curl and download an image to the local machine
2. create an S3 bucket that allows objects to be publicly readable
3. enable S3 static website hosting on the bucket
4. build index.html locally, with an <img> pointing at the image in the bucket
5. upload index.html to the bucket
6. set the correct ContentType for both uploaded files
"""

import json
import random
import string
import subprocess
import urllib.request

import boto3

# --------------------------------------------------------------------------
IMAGE_URL = 'https://www.python.org/static/img/python-logo.png'
IMAGE_NAME = 'logo.png'
IMAGE_TYPE = 'image/png'
INDEX_NAME = 'index.html'
REGION = 'us-east-1'

# --------------------------------------------------------------------------
# Step 1: download the image with curl, driven by subprocess.run
# --------------------------------------------------------------------------
print('Downloading %s with curl ...' % IMAGE_URL)
result = subprocess.run(
    ['curl', '-sS', '-L', '-o', IMAGE_NAME, IMAGE_URL],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    raise SystemExit('curl failed: ' + result.stderr)
print('Saved to %s' % IMAGE_NAME)

# --------------------------------------------------------------------------
# Step 2: create a globally unique bucket
# --------------------------------------------------------------------------
suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
bucket_name = 'week4-static-' + suffix

s3_client = boto3.client('s3', region_name=REGION)
s3_client.create_bucket(Bucket=bucket_name)
print('Created bucket: %s' % bucket_name)

# allow public access on this bucket (block public access is on by default)
s3_client.put_public_access_block(
    Bucket=bucket_name,
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': False,
        'IgnorePublicAcls': False,
        'BlockPublicPolicy': False,
        'RestrictPublicBuckets': False,
    },
)

# allow ACLs, so the objects can be made public
s3_client.put_bucket_ownership_controls(
    Bucket=bucket_name,
    OwnershipControls={'Rules': [{'ObjectOwnership': 'BucketOwnerPreferred'}]},
)

# bucket policy: let anyone read the objects
policy = {
    'Version': '2012-10-17',
    'Statement': [
        {
            'Sid': 'PublicReadGetObject',
            'Effect': 'Allow',
            'Principal': '*',
            'Action': 's3:GetObject',
            'Resource': 'arn:aws:s3:::%s/*' % bucket_name,
        }
    ],
}
s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
print('Applied public-read bucket policy')

# --------------------------------------------------------------------------
# Step 3: enable static website hosting
# --------------------------------------------------------------------------
website_configuration = {
    'IndexDocument': {'Suffix': INDEX_NAME},
    'ErrorDocument': {'Key': 'error.html'},
}
s3_client.put_bucket_website(Bucket=bucket_name, WebsiteConfiguration=website_configuration)

endpoint = 'http://%s.s3-website-%s.amazonaws.com' % (bucket_name, REGION)
print('Enabled static website hosting')

# --------------------------------------------------------------------------
# Step 4: build index.html locally, pointing at the image in the bucket
# --------------------------------------------------------------------------
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lab 4 - Static Website</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 0;
         background: #0f172a; color: #e2e8f0; text-align: center; }}
  .wrap {{ max-width: 760px; margin: 6% auto; padding: 44px; background: #1e293b;
          border-radius: 16px; box-shadow: 0 12px 44px rgba(0,0,0,.55); }}
  h1 {{ color: #38bdf8; margin: 0 0 6px; }}
  .sub {{ color: #94a3b8; margin-bottom: 28px; }}
  img {{ max-width: 320px; background: #fff; padding: 18px; border-radius: 12px; }}
  .foot {{ margin-top: 26px; color: #64748b; font-size: 13px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Static Website on Amazon S3</h1>
    <div class="sub">AWS Academy &mdash; Week 4 &middot; Fan Chenxuan</div>
    <img src="{endpoint}/{image_name}" alt="logo">
    <div class="foot">Served from Amazon S3 &middot; bucket: {bucket}</div>
  </div>
</body>
</html>
""".format(endpoint=endpoint, image_name=IMAGE_NAME, bucket=bucket_name)

with open(INDEX_NAME, 'w', encoding='utf-8') as f:
    f.write(html)
print('Wrote %s' % INDEX_NAME)

# --------------------------------------------------------------------------
# Step 5 + 6: upload both files with the correct ContentType
# --------------------------------------------------------------------------
s3_client.upload_file(
    IMAGE_NAME, bucket_name, IMAGE_NAME,
    ExtraArgs={'ContentType': IMAGE_TYPE},
)
print('Uploaded %s (%s)' % (IMAGE_NAME, IMAGE_TYPE))

s3_client.upload_file(
    INDEX_NAME, bucket_name, INDEX_NAME,
    ExtraArgs={'ContentType': 'text/html'},
)
print('Uploaded %s (text/html)' % INDEX_NAME)

# --------------------------------------------------------------------------
# Verify
# --------------------------------------------------------------------------
with urllib.request.urlopen(endpoint + '/', timeout=20) as r:
    body = r.read(400).decode('utf-8', 'ignore')
print('HTTP', r.status, 'from the website endpoint')

print()
print('Bucket name :', bucket_name)
print('Endpoint    :', endpoint)
print('Done.')
