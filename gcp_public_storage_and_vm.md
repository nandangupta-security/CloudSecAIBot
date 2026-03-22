# GCP CLI: Public Storage & Internet-Accessible Virtual Machine

> **Note:** This guide uses **password-based / metadata SSH key-free authentication** — no SSH key is generated or required.

---

## Prerequisites

### 0.1 Login to GCP

```bash
# Login and update application default credentials
gcloud auth login --update-adc

# Set application default credentials (required for compute API calls)
gcloud auth application-default login
```

> If you ever get `insufficient authentication scopes` errors, re-run both commands above to refresh your credentials.

### 0.2 Create a New Project

```bash
gcloud projects create my-bsides-gcp-project-123 \
  --name="My GCP Project"

# Set it as the active project
gcloud config set project my-bsides-gcp-project-123
```

> **Project ID** must be globally unique, 6-30 characters, lowercase letters, digits, and hyphens only.

### 0.3 Link a Billing Account

```bash
# List available billing accounts
gcloud billing accounts list
```

This outputs something like:
```
ACCOUNT_ID            NAME                OPEN
XXXXXX-XXXXXX-XXXXXX  My Billing Account  True
```

```bash
# Link the billing account to your project
gcloud billing projects link my-bsides-gcp-project-123 \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

> If you have no billing account yet, create one at https://console.cloud.google.com/billing first. GCP offers $300 free trial credit for new accounts.

### 0.4 Set Default Region and Zone

```bash
gcloud config set compute/region us-central1
gcloud config set compute/zone us-central1-a
```

---

## 1. Enable Required APIs

```bash
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
```

---

## 2. Public Storage (Cloud Storage Bucket)

### 2.1 Create a Storage Bucket

```bash
gcloud storage buckets create gs://my-bsides-public-bucket-123 \
  --location us-central1 \
  --uniform-bucket-level-access \
  --project my-bsides-gcp-project-123
```

> **Bucket names are globally unique** across all GCP users. Use a distinctive name like `<project-name>-<purpose>` to avoid `409 Already exists` errors.

### 2.2 Make the Bucket Publicly Readable

```bash
gcloud storage buckets add-iam-policy-binding gs://my-bsides-public-bucket-123 \
  --member allUsers \
  --role roles/storage.objectViewer
```

### 2.3 Upload a File to the Bucket

```bash
# Create a test file first if you don't have one
echo "Hello from GCP!" > myfile.txt

# Upload it
gcloud storage cp ./myfile.txt gs://my-bsides-public-bucket-123/myfile.txt
```

### 2.4 Get the Public URL of an Object

```bash
gcloud storage objects describe gs://my-bsides-public-bucket-123/myfile.txt
```

> Public URL format: `https://storage.googleapis.com/my-bsides-public-bucket-123/myfile.txt`

---

## 3. Internet-Accessible Virtual Machine

### 3.1 Create a Custom VPC Network

```bash
gcloud compute networks create myvpc \
  --subnet-mode custom
```

### 3.2 Create a Subnet

```bash
gcloud compute networks subnets create mysubnet \
  --network myvpc \
  --region us-central1 \
  --range 10.0.1.0/24
```

### 3.3 Create Firewall Rules to Allow Internet Traffic

```bash
# Allow SSH (port 22)
gcloud compute firewall-rules create allow-ssh \
  --network myvpc \
  --direction INGRESS \
  --action ALLOW \
  --rules tcp:22 \
  --source-ranges 0.0.0.0/0 \
  --target-tags ssh-server
```

### 3.4 Reserve a Static External IP Address

```bash
gcloud compute addresses create my-static-ip \
  --region us-central1
```

```bash
# View the reserved IP
gcloud compute addresses describe my-static-ip \
  --region us-central1 \
  --format "get(address)"
```

### 3.5 Create the VM Instance

```bash
gcloud compute instances create myvm \
  --project my-bsides-gcp-project-123 \
  --zone us-central1-a \
  --machine-type e2-medium \
  --network myvpc \
  --subnet mysubnet \
  --address my-static-ip \
  --tags ssh-server \
  --image-family ubuntu-2204-lts \
  --image-project ubuntu-os-cloud \
  --metadata enable-oslogin=TRUE
```

> `--tags ssh-server` links the VM to the SSH firewall rule created in step 3.3.

---

## 4. Verify Resources

```bash
# List compute instances
gcloud compute instances list

# Describe the VM and get its external IP
gcloud compute instances describe myvm \
  --zone us-central1-a \
  --format "get(networkInterfaces[0].accessConfigs[0].natIP)"

# List storage buckets
gcloud storage buckets list

# List objects in a bucket
gcloud storage ls gs://my-bsides-public-bucket-123
```

---

## 5. Clean Up Resources (Optional)

```bash
# Delete firewall rules
gcloud compute firewall-rules delete allow-ssh --quiet

# Delete subnet
gcloud compute networks subnets delete mysubnet --region us-central1 --quiet

# Delete VPC network
gcloud compute networks delete myvpc --quiet

# Delete static IP
gcloud compute addresses delete my-static-ip --region us-central1 --quiet

# Delete storage bucket and all contents
gcloud storage rm --recursive gs://my-bsides-public-bucket-123

# Delete the entire project (removes all resources)
gcloud projects delete my-bsides-gcp-project-123
```

---

## Summary

| Resource              | Purpose                                        |
|-----------------------|------------------------------------------------|
| Cloud Storage Bucket  | Hosts publicly accessible objects              |
| IAM allUsers binding  | Grants public read access to bucket objects    |
| VPC Network + Subnet  | Isolated network for the VM                    |
| Firewall Rules        | Opens HTTP/HTTPS/RDP ports to the internet     |
| Static External IP    | Stable public IP address for the VM            |
