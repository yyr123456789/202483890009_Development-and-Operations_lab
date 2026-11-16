#!/usr/bin/env python3
"""
Developer Operations - Assignment 1
===================================

Automates the deployment of a public-facing web server on AWS:

  1. launches an Amazon EC2 nano instance from the latest Amazon Linux 2023 AMI
  2. configures it (key pair, security group, tags) at launch
  3. seeds it with a User Data script that patches the OS, installs Apache and
     writes an index page showing the instance metadata
  4. downloads an image and builds a static website in an S3 bucket
  5. writes both URLs to a file and opens them in a browser
  6. copies monitoring.sh to the instance with scp and runs it over ssh
  7. (additional) reports CloudWatch CPU utilisation for the new instance

AWS credentials are read from ~/.aws/credentials - nothing is hard-coded here.

Usage:
    python3 devops_ass1.py [--key-name NAME] [--student SUFFIX]
                           [--skip-cloudwatch] [--terminate]

Author: Fan Chenxuan
"""

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - only hit on a broken environment
    print("FATAL: boto3 is not installed. Try: pip3 install boto3")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration - everything adjustable lives here, nothing is repeated in
# the body of the program.
# ---------------------------------------------------------------------------
REGION = "us-east-1"
INSTANCE_TYPE = "t2.nano"
INSTANCE_NAME_TAG = "devops-ass1-webserver"
SECURITY_GROUP_NAME = "devops-ass1-sg"

# Default SSH key. Can be overridden with --key-name.
DEFAULT_KEY_NAME = "vockey"

# Private key file used for scp/ssh. In the AWS Academy lab the key pair is
# called "vockey" but the file you download is "labsuser.pem", so the file
# name is kept separate from the key pair name. Can be overridden with
# --key-file.
DEFAULT_KEY_FILE = "labsuser.pem"

# Student identifier used in the bucket name and the output file name, e.g.
# jbloggs -> bucket "<6 random chars>-jbloggs" and file "jbloggs-websites.txt"
DEFAULT_STUDENT = "fchenxuan"

# The image suggested by the assignment. That host no longer resolves, so a
# list of candidates is tried in order and the first one that downloads is
# used. Keeping this as a list means the code does not depend on one URL.
IMAGE_URLS = [
    "http://devops.witdemo.net/logo.jpg",
    "https://www.python.org/static/img/python-logo.png",
]

# How long to wait for the User Data script to finish (seconds).
USER_DATA_TIMEOUT = 420

# How long to wait for CloudWatch metrics to appear (seconds).
CLOUDWATCH_TIMEOUT = 360


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def log(message):
    """Timestamped console output, so the run can be followed live."""
    print("[{}] {}".format(datetime.now().strftime("%H:%M:%S"), message), flush=True)


def log_error(message):
    print("[{}] ERROR: {}".format(datetime.now().strftime("%H:%M:%S"), message), flush=True)


def random_bucket_prefix(length=6):
    """Six random lowercase letters/digits, as required by the brief."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Step 1 - find the latest Amazon Linux 2023 AMI
# ---------------------------------------------------------------------------
def get_latest_ami(ec2_client):
    """Return the id of the most recent Amazon Linux 2023 x86_64 image."""
    log("Looking up the latest Amazon Linux 2023 AMI ...")
    try:
        response = ec2_client.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name", "Values": ["al2023-ami-2023.*-x86_64"]},
                {"Name": "state", "Values": ["available"]},
                {"Name": "architecture", "Values": ["x86_64"]},
            ],
        )
    except (ClientError, BotoCoreError) as error:
        log_error("could not query AMIs: {}".format(error))
        raise

    images = response.get("Images", [])
    if not images:
        raise RuntimeError("no Amazon Linux 2023 images were returned by AWS")

    # Newest first.
    images.sort(key=lambda image: image["CreationDate"], reverse=True)
    newest = images[0]
    log("AMI {} ({})".format(newest["ImageId"], newest["CreationDate"]))
    return newest["ImageId"]


# ---------------------------------------------------------------------------
# Step 2 - security group
# ---------------------------------------------------------------------------
def ensure_security_group(ec2_client, vpc_id):
    """
    Return a security group id that allows SSH and HTTP.

    An existing group with our name is reused, otherwise one is created, so
    the script can be run repeatedly without piling up security groups.
    """
    log("Checking security group '{}' ...".format(SECURITY_GROUP_NAME))
    try:
        found = ec2_client.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [SECURITY_GROUP_NAME]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )
        groups = found.get("SecurityGroups", [])
        if groups:
            group_id = groups[0]["GroupId"]
            log("reusing security group {}".format(group_id))
            return group_id

        created = ec2_client.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description="SSH and HTTP for the Assignment 1 web server",
            VpcId=vpc_id,
        )
        group_id = created["GroupId"]
        log("created security group {}".format(group_id))

        for port, label in ((22, "SSH"), (80, "HTTP")):
            ec2_client.authorize_security_group_ingress(
                GroupId=group_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": port,
                        "ToPort": port,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": label}],
                    }
                ],
            )
        log("opened ports 22 and 80")
        return group_id
    except (ClientError, BotoCoreError) as error:
        log_error("security group setup failed: {}".format(error))
        raise


# ---------------------------------------------------------------------------
# Step 3 - User Data
# ---------------------------------------------------------------------------
def build_user_data(student):
    """
    Build the cloud-init script that runs on first boot.

    It patches the operating system, installs and starts Apache, then writes
    an index page containing the instance metadata (id, private ip, type,
    availability zone) plus a little extra content.
    """
    script = """#!/bin/bash
set -e
exec > /var/log/user-data.log 2>&1

echo "=== starting user data ==="

# --- apply operating system patches -------------------------------------
yum update -y

# --- install and start the web server -----------------------------------
yum install -y httpd
systemctl enable httpd
systemctl start httpd

# --- collect instance metadata (IMDSv2 requires a token first) -----------
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \\
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
meta() {
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \\
         "http://169.254.169.254/latest/meta-data/$1"
}

INSTANCE_ID=$(meta instance-id)
PRIVATE_IP=$(meta local-ipv4)
INSTANCE_TYPE=$(meta instance-type)
AVAILABILITY_ZONE=$(meta placement/availability-zone)
PUBLIC_IP=$(meta public-ipv4)
HOSTNAME=$(meta hostname)

# --- write the index page ------------------------------------------------
cat > /var/www/html/index.html <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DevOps Assignment 1 - web server</title>
<style>
  body { font-family: "Segoe UI", Arial, sans-serif; margin:0; background:#0f172a;
         color:#e2e8f0; text-align:center; }
  .wrap { max-width:720px; margin:7% auto; padding:40px; background:#1e293b;
          border-radius:14px; box-shadow:0 12px 44px rgba(0,0,0,.55); }
  h1 { color:#38bdf8; margin:0 0 6px; }
  .sub { color:#94a3b8; margin-bottom:26px; }
  table { width:100%; border-collapse:collapse; text-align:left; }
  td { padding:11px 6px; border-bottom:1px solid #334155; }
  td.k { color:#94a3b8; width:38%; }
  td.v { color:#f1f5f9; font-family:Consolas, monospace; }
  .foot { margin-top:24px; color:#64748b; font-size:13px; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Web Server running on Amazon EC2</h1>
    <div class="sub">DevOps Assignment 1 &middot; __STUDENT__</div>
    <table>
      <tr><td class="k">Instance ID</td><td class="v">__INSTANCE_ID__</td></tr>
      <tr><td class="k">Private IP address</td><td class="v">__PRIVATE_IP__</td></tr>
      <tr><td class="k">Instance type</td><td class="v">__INSTANCE_TYPE__</td></tr>
      <tr><td class="k">Availability zone</td><td class="v">__AZ__</td></tr>
      <tr><td class="k">Public IP address</td><td class="v">__PUBLIC_IP__</td></tr>
      <tr><td class="k">Hostname</td><td class="v">__HOSTNAME__</td></tr>
    </table>
    <div class="foot">Page generated by the User Data script at boot time.</div>
  </div>
</body>
</html>
HTML

# substitute the values collected above into the page
sed -i "s|__INSTANCE_ID__|$INSTANCE_ID|g"      /var/www/html/index.html
sed -i "s|__PRIVATE_IP__|$PRIVATE_IP|g"        /var/www/html/index.html
sed -i "s|__INSTANCE_TYPE__|$INSTANCE_TYPE|g"  /var/www/html/index.html
sed -i "s|__AZ__|$AVAILABILITY_ZONE|g"         /var/www/html/index.html
sed -i "s|__PUBLIC_IP__|$PUBLIC_IP|g"          /var/www/html/index.html
sed -i "s|__HOSTNAME__|$HOSTNAME|g"            /var/www/html/index.html

systemctl restart httpd
echo "=== user data finished ==="
"""
    return script.replace("__STUDENT__", student)


# ---------------------------------------------------------------------------
# Step 4 - launch the instance
# ---------------------------------------------------------------------------
def launch_instance(ec2, ami_id, key_name, security_group_id, student):
    """Create the instance and wait until it is running and reachable."""
    log("Launching a {} instance ...".format(INSTANCE_TYPE))
    user_data = build_user_data(student)

    try:
        instances = ec2.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=INSTANCE_TYPE,
            # Detailed monitoring gives one-minute metrics, so the
            # CloudWatch report has data within a few minutes instead of
            # waiting for the five-minute basic interval.
            Monitoring={"Enabled": True},
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            UserData=user_data,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": INSTANCE_NAME_TAG},
                        {"Key": "Project", "Value": "DevOps Assignment 1"},
                        {"Key": "Owner", "Value": student},
                    ],
                }
            ],
        )
    except (ClientError, BotoCoreError) as error:
        log_error("instance launch failed: {}".format(error))
        raise

    instance = instances[0]
    log("instance created: {}".format(instance.id))

    log("waiting for the instance to reach the running state ...")
    instance.wait_until_running()
    instance.reload()
    log("state is now {} - public IP {}".format(instance.state["Name"],
                                                instance.public_ip_address))
    return instance


def wait_for_website(url, timeout=USER_DATA_TIMEOUT):
    """
    Poll the URL until it answers with HTTP 200.

    wait_until_running() only says the machine is up - the User Data script
    is still running at that point, so the site has to be polled separately.
    """
    log("waiting for the web server to answer on {} ...".format(url))
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    log("web server responded after {} attempt(s)".format(attempt))
                    return True
        except (urllib.error.URLError, OSError):
            pass
        if attempt % 6 == 0:
            log("  still starting, {}s elapsed ...".format(int(time.time() - (deadline - timeout))))
        time.sleep(10)

    log_error("the web server did not respond within {}s".format(timeout))
    return False


# ---------------------------------------------------------------------------
# Step 5 - S3 static website
# ---------------------------------------------------------------------------
# Magic numbers used to work out what an image really is. The brief says the
# image may change, so the file is identified from its contents rather than
# from the URL - that way the ContentType sent to S3 is always right.
IMAGE_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
    (b"GIF87a", ".gif", "image/gif"),
    (b"GIF89a", ".gif", "image/gif"),
]


def detect_image_type(data):
    """Return (extension, content type) for the image bytes passed in."""
    for signature, extension, content_type in IMAGE_SIGNATURES:
        if data.startswith(signature):
            return extension, content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    # Unknown format - fall back to the type used in the brief.
    return ".jpg", "image/jpeg"


def download_image(urls, stem="logo"):
    """
    Try each candidate URL and save the first one that works.

    Returns (local file name, content type, source URL). The file extension
    follows the real image format, so a PNG is saved as .png and served as
    image/png.
    """
    for url in urls:
        log("downloading {} ...".format(url))
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
            if not data:
                log_error("empty response from {}".format(url))
                continue

            extension, content_type = detect_image_type(data)
            destination = stem + extension
            with open(destination, "wb") as output:
                output.write(data)
            log("saved {} bytes to {} ({})".format(len(data), destination, content_type))
            return destination, content_type, url
        except (urllib.error.URLError, OSError) as error:
            log_error("download failed for {}: {}".format(url, error))

    raise RuntimeError("could not download the image from any of the candidate URLs")


def setup_s3(s3, s3_client, bucket_name, image_path, image_type, image_url, student):
    """Create the bucket, upload both objects and enable website hosting."""
    log("creating bucket {} ...".format(bucket_name))
    try:
        s3.create_bucket(Bucket=bucket_name)
    except ClientError as error:
        raise RuntimeError("could not create bucket {}: {}".format(bucket_name, error))

    try:
        # Buckets block public access by default - that has to be removed
        # before the objects can be served to the internet.
        s3_client.delete_public_access_block(Bucket=bucket_name)
        log("public access block removed")

        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:::{}/*".format(bucket_name),
            }],
        }
        s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))
        log("bucket policy applied (public read)")
    except ClientError as error:
        log_error("could not make the bucket public: {}".format(error))
        raise

    # --- upload the image -------------------------------------------------
    content_type = image_type
    try:
        s3.Bucket(bucket_name).upload_file(
            image_path,
            os.path.basename(image_path),
            ExtraArgs={"ContentType": content_type},
        )
        log("uploaded {} ({})".format(os.path.basename(image_path), content_type))
    except ClientError as error:
        log_error("could not upload the image: {}".format(error))
        raise

    # --- build and upload the index page ----------------------------------
    website_host = "{}.s3-website-{}.amazonaws.com".format(bucket_name, REGION)
    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Static website on Amazon S3</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin:0; background:#0f172a;
         color:#e2e8f0; text-align:center; }}
  .wrap {{ max-width:760px; margin:7% auto; padding:40px; background:#1e293b;
          border-radius:14px; box-shadow:0 12px 44px rgba(0,0,0,.55); }}
  h1 {{ color:#38bdf8; margin:0 0 6px; }}
  .sub {{ color:#94a3b8; margin-bottom:26px; }}
  img {{ max-width:340px; background:#fff; padding:16px; border-radius:12px; }}
  .foot {{ margin-top:24px; color:#64748b; font-size:13px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Static website hosted on Amazon S3</h1>
    <div class="sub">DevOps Assignment 1 &middot; {student}</div>
    <img src="http://{host}/{image}" alt="downloaded image">
    <div class="foot">Image source: {source}<br>bucket: {bucket}</div>
  </div>
</body>
</html>
""".format(student=student, host=website_host,
           image=os.path.basename(image_path), source=image_url, bucket=bucket_name)

    with open("index.html", "w", encoding="utf-8") as output:
        output.write(page)

    try:
        s3.Bucket(bucket_name).upload_file(
            "index.html", "index.html", ExtraArgs={"ContentType": "text/html"}
        )
        log("uploaded index.html (text/html)")
    except ClientError as error:
        log_error("could not upload index.html: {}".format(error))
        raise

    # --- enable static website hosting ------------------------------------
    try:
        s3.BucketWebsite(bucket_name).put(
            WebsiteConfiguration={
                "IndexDocument": {"Suffix": "index.html"},
                "ErrorDocument": {"Key": "error.html"},
            }
        )
        log("static website hosting enabled")
    except ClientError as error:
        log_error("could not enable website hosting: {}".format(error))
        raise

    return "http://{}/".format(website_host)


# ---------------------------------------------------------------------------
# Step 6 - write the URLs to a file
# ---------------------------------------------------------------------------
def write_urls_file(filename, ec2_url, s3_url):
    """Write both URLs to the hand-in file."""
    try:
        with open(filename, "w", encoding="utf-8") as output:
            output.write("Web server (EC2): {}\n".format(ec2_url))
            output.write("Static website (S3): {}\n".format(s3_url))
        log("URLs written to {}".format(filename))
    except OSError as error:
        log_error("could not write {}: {}".format(filename, error))
        raise

    with open(filename, encoding="utf-8") as handle:
        for line in handle:
            log("  " + line.strip())


# ---------------------------------------------------------------------------
# Step 7 - monitoring over scp and ssh
# ---------------------------------------------------------------------------
def run_monitoring(ip_address, key_path, script_name="monitoring.sh"):
    """Copy monitoring.sh to the instance and execute it over ssh."""
    if not os.path.exists(key_path):
        log_error("private key {} not found - skipping monitoring".format(key_path))
        return False

    ssh_options = ["-o", "StrictHostKeyChecking=no",
                   "-o", "UserKnownHostsFile=/dev/null",
                   "-o", "ConnectTimeout=20"]

    # --- scp the script up -------------------------------------------------
    scp_command = ["scp", "-i", key_path] + ssh_options + [
        script_name, "ec2-user@{}:.".format(ip_address)
    ]
    log("scp {} -> ec2-user@{}".format(script_name, ip_address))
    try:
        scp_result = subprocess.run(scp_command, capture_output=True, text=True)
    except OSError as error:
        log_error("could not run scp: {}".format(error))
        return False

    if scp_result.returncode != 0:
        log_error("scp failed ({}): {}".format(scp_result.returncode, scp_result.stderr.strip()))
        return False
    log("scp finished")

    # --- make it executable and run it ------------------------------------
    commands = [
        "chmod 700 {}".format(script_name),
        "./{}".format(script_name),
    ]
    for remote_command in commands:
        ssh_command = ["ssh", "-i", key_path] + ssh_options + [
            "ec2-user@{}".format(ip_address), remote_command
        ]
        log("ssh: {}".format(remote_command))
        try:
            result = subprocess.run(ssh_command, capture_output=True, text=True)
        except OSError as error:
            log_error("could not run ssh: {}".format(error))
            return False

        if result.returncode != 0:
            log_error("remote command failed ({}): {}".format(
                result.returncode, result.stderr.strip()))
            return False

        if result.stdout.strip():
            print(result.stdout.rstrip())

    log("monitoring script finished")
    return True


# ---------------------------------------------------------------------------
# Step 8 - additional functionality: CloudWatch CPU utilisation
# ---------------------------------------------------------------------------
def report_cpu_utilisation(cloudwatch, instance_id, timeout=CLOUDWATCH_TIMEOUT):
    """
    Report the average CPU utilisation of the instance from CloudWatch.

    This is the additional functionality: it shows the instance interacting
    with a second AWS service through boto3.
    """
    log("requesting CloudWatch CPU metrics for {}".format(instance_id))
    try:
        metrics = list(cloudwatch.metrics.filter(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        ))
        if not metrics:
            log_error("no CPUUtilization metric found")
            return False

        metric = metrics[0]
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = metric.get_statistics(
                StartTime=datetime.now(timezone.utc) - timedelta(minutes=5),
                EndTime=datetime.now(timezone.utc),
                Period=60,
                Statistics=["Average", "Maximum"],
            )
            points = response.get("Datapoints", [])
            if points:
                point = points[-1]
                log("CPU utilisation: average {:.2f}%, maximum {:.2f}% ({})".format(
                    point["Average"], point["Maximum"], point.get("Unit", "")))
                return True
            log("  no data points yet, waiting 30s ...")
            time.sleep(30)
    except (ClientError, BotoCoreError) as error:
        log_error("CloudWatch query failed: {}".format(error))
        return False

    log_error("CloudWatch did not return any data points in time")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Deploy an EC2 web server and an S3 static website on AWS.")
    parser.add_argument("--key-name", default=DEFAULT_KEY_NAME,
                        help="EC2 key pair name (default: %(default)s)")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE,
                        help="private key file used for scp/ssh "
                             "(default: %(default)s)")
    parser.add_argument("--student", default=DEFAULT_STUDENT,
                        help="suffix used in the bucket and file names "
                             "(default: %(default)s)")
    parser.add_argument("--skip-cloudwatch", action="store_true",
                        help="skip the CloudWatch CPU report")
    parser.add_argument("--terminate", action="store_true",
                        help="terminate the instance when the run finishes")
    return parser.parse_args()


def main():
    args = parse_arguments()
    started = time.time()

    log("=" * 62)
    log("DevOps Assignment 1 - starting")
    log("region {}, instance type {}, key {}".format(REGION, INSTANCE_TYPE, args.key_name))
    log("=" * 62)

    try:
        session = boto3.Session(region_name=REGION)
        ec2 = session.resource("ec2")
        ec2_client = session.client("ec2")
        s3 = session.resource("s3")
        s3_client = session.client("s3")
        cloudwatch = session.resource("cloudwatch")
    except (BotoCoreError, ClientError) as error:
        log_error("could not create an AWS session - are the credentials in "
                  "~/.aws/credentials? ({})".format(error))
        return 1

    instance = None
    try:
        # ---- EC2 ---------------------------------------------------------
        ami_id = get_latest_ami(ec2_client)
        vpc_id = ec2_client.describe_vpcs(
            Filters=[{"Name": "is-default", "Values": ["true"]}]
        )["Vpcs"][0]["VpcId"]
        security_group_id = ensure_security_group(ec2_client, vpc_id)

        instance = launch_instance(ec2, ami_id, args.key_name, security_group_id, args.student)
        ec2_url = "http://{}".format(instance.public_ip_address)

        site_ready = wait_for_website(ec2_url)

        # ---- S3 ----------------------------------------------------------
        bucket_name = "{}-{}".format(random_bucket_prefix(), args.student)
        image_path, image_type, used_url = download_image(IMAGE_URLS, "logo")
        s3_url = setup_s3(s3, s3_client, bucket_name, image_path, image_type,
                          used_url, args.student)

        # ---- URLs --------------------------------------------------------
        urls_file = "{}-websites.txt".format(args.student)
        write_urls_file(urls_file, ec2_url, s3_url)

        log("opening both URLs in the default browser ...")
        for url in (ec2_url, s3_url):
            try:
                webbrowser.open_new_tab(url)
            except Exception as error:  # browser problems must not kill the run
                log_error("could not open the browser: {}".format(error))

        # ---- monitoring --------------------------------------------------
        monitoring_ok = run_monitoring(instance.public_ip_address, args.key_file)

        # ---- additional: CloudWatch --------------------------------------
        if not args.skip_cloudwatch:
            report_cpu_utilisation(cloudwatch, instance.id)

        # ---- summary -----------------------------------------------------
        log("=" * 62)
        log("DEPLOYMENT COMPLETE in {:.0f} seconds".format(time.time() - started))
        log("  instance id      : {}".format(instance.id))
        log("  instance state   : {}".format(instance.state["Name"]))
        log("  public IP        : {}".format(instance.public_ip_address))
        log("  EC2 website      : {}  ({})".format(
            ec2_url, "OK" if site_ready else "NOT RESPONDING"))
        log("  S3 bucket        : {}".format(bucket_name))
        log("  S3 website       : {}".format(s3_url))
        log("  URLs file        : {}".format(urls_file))
        log("  monitoring       : {}".format("OK" if monitoring_ok else "FAILED"))
        log("=" * 62)
        log("Remember to terminate the instance when you are finished:")
        log("  aws ec2 terminate-instances --instance-ids {}".format(instance.id))

        if args.terminate:
            log("--terminate given, shutting the instance down")
            instance.terminate()

        return 0

    except (ClientError, BotoCoreError, RuntimeError) as error:
        log_error("deployment failed: {}".format(error))
        if instance is not None:
            log_error("the instance {} was created and may still be running".format(instance.id))
        return 1
    except KeyboardInterrupt:
        log_error("interrupted by the user")
        if instance is not None:
            log_error("the instance {} may still be running".format(instance.id))
        return 1


if __name__ == "__main__":
    sys.exit(main())
