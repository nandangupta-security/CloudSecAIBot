# AWS CLI Cmdlets Reference

---

## Table of Contents

1. [EC2](#ec2)
2. [S3](#s3)
3. [IAM](#iam)

---

## EC2

### Create a security group

```bash
aws ec2 create-security-group \
  --group-name my-open-sg \
  --description "Security group with open access"
```

### Authorize inbound traffic on a security group

```bash
aws ec2 authorize-security-group-ingress \
  --group-name my-open-sg \
  --protocol -1 \
  --port -1 \
  --cidr 0.0.0.0/0
```

### Launch an EC2 instance

```bash
aws ec2 run-instances \
  --image-id ami-040855b0715ee6f0b \
  --instance-type t3.micro \
  --security-groups my-open-sg \
  --count 1 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=my-free-tier-vm}]'
```

---

## S3

### Create a bucket (us-east-1)

```bash
aws s3api create-bucket \
  --bucket bsidestestcmd \
  --region us-east-1
```

### Create a bucket (other regions)

```bash
aws s3api create-bucket \
  --bucket bsidestestcmd \
  --region us-west-2 \
  --create-bucket-configuration LocationConstraint=us-west-2
```

### Disable block public access

```bash
aws s3api put-public-access-block \
  --bucket bsidestestcmd \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

### Create and attach a public bucket policy

```bash
aws s3api put-bucket-policy \
  --bucket bsidestestcmd \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::bsidestestcmd/*"
      }
    ]
  }'
```

---

## IAM

### Update account password policy

```bash
aws iam update-account-password-policy \
  --minimum-password-length 6
```
