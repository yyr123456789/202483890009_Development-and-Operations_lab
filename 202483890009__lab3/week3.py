import random
import string

import boto3

AMI_ID = 'ami-0c230065b91270bc6'

ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')

# ---------------- A. EC2 ----------------
instances = ec2.create_instances(
    ImageId=AMI_ID,
    MinCount=1,
    MaxCount=1,
    InstanceType='t2.nano',
)
instance = instances[0]
print('Created instance:', instance.id)

instance.wait_until_running()   
instance.reload()               
print('Instance Running.')

# ---------------- B. S3 ----------------
suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
bucket_name = 'week3-demo-' + suffix
s3.create_bucket(Bucket=bucket_name)

website_configuration = {
    'ErrorDocument': {'Key': 'error.html'},
    'IndexDocument': {'Suffix': 'index.html'},
}
bucket_website = s3.BucketWebsite(bucket_name)
bucket_website.put(WebsiteConfiguration=website_configuration)

print('Bucket name:', bucket_name)
print('Upload an index.html file to test it works!')
print('Endpoint: http://%s.s3-website-us-east-1.amazonaws.com' % bucket_name)
