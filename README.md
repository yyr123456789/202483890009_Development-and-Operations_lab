# Development and Operations — Lab 1-6 + Assignment 1

**Fan Chenxuan (202483890009)** — Cloud Computing / Developer Operations, AWS Academy (SETU).

## Contents

| Folder | Lab | Summary |
|---|---|---|
| `202483890009__lab1/` | Lab 1 | AWS setup: EC2 + Apache + custom index page, S3 static website (screenshots in the PDF) |
| `202483890009__lab2/` | Lab 2 | Google Python class: `string1.py` and `list1.py` with run screenshots |
| `202483890009__lab3/` | Lab 3 | `week3.py` — boto3 EC2 waiter plus S3 static website, with terminal output |
| `202483890009__lab4/` | Lab 4 | `week4.py` — `subprocess.run` driving curl, S3 public bucket with correct ContentType |
| `202483890009__lab5/` | Lab 5 | VPC: public/private subnets, NAT gateway, bastion host (4 screenshots) |
| `202483890009__lab6/` | Lab 6 | Application Load Balancer across two availability zones (6 screenshots) |
| `assignment/` | Assignment 1 | `devops_ass1.py` — automated EC2 + S3 deployment with User Data and CloudWatch monitoring, plus the review spreadsheet and screenshots |

## Assignment 1 — `devops_ass1.py`

A single Python program that:

1. looks up the latest Amazon Linux 2023 AMI at runtime
2. launches a `t2.nano` instance with a key pair, security group and tags
3. runs a User Data script that patches the OS, installs Apache and publishes instance metadata (IMDSv2) on the index page
4. creates an S3 bucket with public read access and static website hosting, downloads an image and uploads it with the correct ContentType
5. writes both URLs to `fchenxuan-websites.txt` and opens them in a browser
6. copies `monitoring.sh` to the instance over scp and runs it over ssh
7. reports CloudWatch CPU utilisation for the new instance

## Notes

- AWS credentials are read from `~/.aws/credentials` and are never committed.
- Private keys (`*.pem`) are excluded by `.gitignore`.