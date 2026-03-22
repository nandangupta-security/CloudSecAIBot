# GCP CLI: Public Storage & Internet-Accessible Virtual Machine

> **Note:** This guide uses **password-based / metadata SSH key-free authentication** — no SSH key is generated or required.

---

## Prerequisites

### 0.1 Login to GCP

```bash
gcloud auth login
```

### 0.2 Create a New Project

```bash
gcloud projects create my-gcp-project-123 \
  --name="My GCP Project"

# Set it as the active project
gcloud config set project my-gcp-project-123
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
gcloud billing projects link my-gcp-project-123 \
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
gcloud storage buckets create gs://my-public-bucket-123 \
  --location us-central1 \
  --uniform-bucket-level-access
```

### 2.2 Make the Bucket Publicly Readable

```bash
gcloud storage buckets add-iam-policy-binding gs://my-public-bucket-123 \
  --member allUsers \
  --role roles/storage.objectViewer
```

### 2.3 Upload a File to the Bucket

```bash
gcloud storage cp ./myfile.txt gs://my-public-bucket-123/myfile.txt
```

### 2.4 Get the Public URL of an Object

```bash
gcloud storage objects describe gs://my-public-bucket-123/myfile.txt
```

> Public URL format: `https://storage.googleapis.com/my-public-bucket-123/myfile.txt`

---

## 3. Internet-Accessible Virtual Machine

### 3.1 Create a Custom VPC Network

```bash
gcloud compute networks create myVPC \
  --subnet-mode custom
```

### 3.2 Create a Subnet

```bash
gcloud compute networks subnets create mySubnet \
  --network myVPC \
  --region us-central1 \
  --range 10.0.1.0/24
```

### 3.3 Create Firewall Rules to Allow Internet Traffic

```bash
# Allow HTTP (port 80)
gcloud compute firewall-rules create allow-http \
  --network myVPC \
  --direction INGRESS \
  --action ALLOW \
  --rules tcp:80 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server

# Allow HTTPS (port 443)
gcloud compute firewall-rules create allow-https \
  --network myVPC \
  --direction INGRESS \
  --action ALLOW \
  --rules tcp:443 \
  --source-ranges 0.0.0.0/0 \
  --target-tags https-server

# Allow RDP (port 3389) — for Windows VMs
gcloud compute firewall-rules create allow-rdp \
  --network myVPC \
  --direction INGRESS \
  --action ALLOW \
  --rules tcp:3389 \
  --source-ranges 0.0.0.0/0 \
  --target-tags rdp-server
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

### 3.5 Create a Network Interface with the Static IP

The static IP is attached directly during VM creation in the next step via `--address`.

---

## 4. Verify Resources

```bash
# List compute instances
gcloud compute instances list

# Describe the VM and get its external IP
gcloud compute instances describe myVM \
  --zone us-central1-a \
  --format "get(networkInterfaces[0].accessConfigs[0].natIP)"

# List storage buckets
gcloud storage buckets list

# List objects in a bucket
gcloud storage ls gs://my-public-bucket-123
```

---

## 5. Clean Up Resources (Optional)

```bash
# Delete firewall rules
gcloud compute firewall-rules delete allow-http allow-https allow-rdp --quiet

# Delete subnet
gcloud compute networks subnets delete mySubnet --region us-central1 --quiet

# Delete VPC network
gcloud compute networks delete myVPC --quiet

# Delete static IP
gcloud compute addresses delete my-static-ip --region us-central1 --quiet

# Delete storage bucket and all contents
gcloud storage rm --recursive gs://my-public-bucket-123

# Delete the entire project (removes all resources)
gcloud projects delete my-gcp-project-123
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
