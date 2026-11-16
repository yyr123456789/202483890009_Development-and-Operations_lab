# DevOps Coursework — Fan Chenxuan

Cloud Computing / Developer Operations coursework (AWS Academy, SETU).

## Contents

| Folder | Lab | What it is |
|---|---|---|
| `202483890009__lab1.pdf` | Lab 1 | AWS setup: EC2 + Apache + S3 static site (3 screenshots) |
| `202483890009__lab2/` | Lab 2 | Google Python class: string1.py and list1.py |
| `Week3/` | Lab 3 | boto3 EC2 waiter + S3 static website (week3.py) |
| `Week4/` | Lab 4 | subprocess.run + curl + S3 static website |
| `lab5/` | Lab 5 | VPC with public/private subnets, NAT gateway, bastion host |
| `lab6/` | Lab 6 | Application Load Balancer across two availability zones |
| `assignment/` | Assignment 1 | devops_ass1.py: automated EC2 + S3 deployment with CloudWatch monitoring |
| `google-python-exercises/` | Lab 2 | The nine Google Python class exercises |
| `screenshots/` | Lab 2 | Run screenshots for each exercise |

## Assignment 1

`assignment/devops_ass1.py` automates:

1. launching an EC2 t2.nano from the latest Amazon Linux 2023 AMI
2. a User Data script that patches the OS, installs Apache and publishes instance metadata
3. an S3 bucket serving a static website with the downloaded image
4. writing both URLs to a file and opening them in a browser
5. copying monitoring.sh to the instance with scp and running it over ssh
6. a CloudWatch CPU utilisation report

## Notes

- AWS credentials are read from `~/.aws/credentials`, never committed.
- Private keys (`*.pem`) are excluded by `.gitignore`.