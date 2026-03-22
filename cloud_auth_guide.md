# Cloud CLI Authentication Guide

GCP · AWS · Azure — Terminal Authentication Steps

---

## Table of Contents

1. [Google Cloud Platform (GCP)](#1-google-cloud-platform-gcp)
2. [Amazon Web Services (AWS)](#2-amazon-web-services-aws)
3. [Microsoft Azure](#3-microsoft-azure)
4. [Quick Reference Summary](#quick-reference-summary)

---

## 1. Google Cloud Platform (GCP)

### Prerequisites

Install the Google Cloud CLI (`gcloud`) before starting.

**macOS (Homebrew)**

```bash
brew install --cask google-cloud-sdk
```

**Linux**

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows (PowerShell)**

```powershell
(New-Object Net.WebClient).DownloadFile(
  'https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe',
  'GoogleCloudSDKInstaller.exe')
.\GoogleCloudSDKInstaller.exe
```

### Authentication Steps

Step 1 — Initialize and log in with your Google account:

```bash
gcloud init
```

Step 2 — Alternatively, log in directly without running init:

```bash
gcloud auth login
```

---

## 2. Amazon Web Services (AWS)

### Prerequisites

Install the AWS CLI v2 before starting.

**macOS**

```bash
brew install awscli
```

**Linux**

```bash
curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip'
unzip awscliv2.zip
sudo ./aws/install
```

**Windows**

```powershell
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

### Authentication Steps — IAM User (Access Keys)

Step 1 — Configure credentials interactively:

```bash
aws configure
```

You will be prompted for:

- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g. `us-east-1`)
- Default output format (`json` / `table` / `text`)

---

## 3. Microsoft Azure

### Prerequisites

Install the Azure CLI (`az`) before starting.

**macOS**

```bash
brew install azure-cli
```

**Linux (Ubuntu/Debian)**

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**Windows**

```powershell
winget install Microsoft.AzureCLI
```

### Authentication Steps — Interactive Login

Step 1 — Log in (opens browser for authentication):

```bash
az login
```

---

## Quick Reference Summary

| Provider | Primary Command    | Verify Identity              |
|----------|--------------------|------------------------------|
| GCP      | `gcloud auth login` | `gcloud auth list`          |
| AWS      | `aws configure`     | `aws sts get-caller-identity`|
| Azure    | `az login`          | `az account show`            |
