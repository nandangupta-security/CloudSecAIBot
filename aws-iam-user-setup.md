# AWS IAM User Setup Guide

A step-by-step guide to creating two IAM users — one with read-only access and one with administrator access — and generating CLI access keys for each.

---

## Table of Contents

1. [User 1 — Read-Only IAM User](#user-1--read-only-iam-user)
2. [User 2 — Administrator IAM User](#user-2--administrator-iam-user)
3. [Create Access Keys for CLI Usage](#create-access-keys-for-cli-usage)
4. [Configure the AWS CLI](#configure-the-aws-cli)


---

## User 1 — Read-Only IAM User

1. Sign in to the **AWS Management Console** and navigate to **IAM** (search "IAM" in the top search bar).

2. In the left sidebar, click **Users**, then click **Create user**.

3. Enter a username — for example, `readonly-user`. Leave "Provide user access to the AWS Management Console" unchecked unless console login is also needed. Click **Next**.

4. On the **Set permissions** page, choose **Attach policies directly**.

5. In the search box, type `ReadOnlyAccess` and select the checkbox next to **ReadOnlyAccess** (AWS managed policy). Click **Next**.

6. Review the details and click **Create user**.

> ✅ Your read-only user is now created with view-only access across all AWS services.

---

## User 2 — Administrator IAM User

1. In the IAM console sidebar, click **Users**, then click **Create user**.

2. Enter a username — for example, `admin-user`. Click **Next**.

3. Choose **Attach policies directly**, search for `AdministratorAccess`, and select the checkbox next to **AdministratorAccess** (AWS managed policy). Click **Next**.

4. Review and click **Create user**.

> ✅ Your administrator user is now created with full access to all AWS services and resources.

> ⚠️ **Warning:** The `AdministratorAccess` policy grants unrestricted AWS access. Only assign this to trusted individuals and avoid using it for automated workloads.

---

## Create Access Keys for CLI Usage

Repeat the following steps for **each user**.

1. In the IAM console, go to **Users** and click on the user's name (e.g., `readonly-user`).

2. Click the **Security credentials** tab.

3. Scroll down to the **Access keys** section and click **Create access key**.

4. Select **Command Line Interface (CLI)** as the use case. Check the confirmation checkbox and click **Next**.

5. Optionally add a description tag, then click **Create access key**.

6. You will see your **Access Key ID** and **Secret Access Key**. Click **Download .csv file** to save them immediately.

> 🔑 **Important:** The secret access key is shown **only once**. If you lose it, you must delete the key and create a new one.

---

## Configure the AWS CLI

### Prerequisites

Install the AWS CLI if not already installed:  
👉 [AWS CLI Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)

### Set up named profiles

Use a named profile for each user to keep credentials isolated:

```bash
aws configure --profile readonly-user
```

```bash
aws configure --profile admin-user
```

### Enter credentials when prompted

```
AWS Access Key ID:     
AWS Secret Access Key: 
Default region name:   us-east-1
Default output format: json
```

### Verify the configuration

Test each profile with a simple command:

```bash
# Test read-only user
aws s3 ls --profile readonly-user

# Test admin user
aws iam list-users --profile admin-user
```
