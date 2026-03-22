# Azure CLI: Public Storage

---

## Prerequisites

```bash
# Clear any cached accounts to avoid stale session issues
az account clear

# Login to Azure
az login

# List available subscriptions
az account list --output table
```

---

## 1. Register Required Resource Providers

```bash
# Register required providers
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Network
az provider register --namespace Microsoft.Compute

# Verify registration status (wait until all show "Registered")
az provider show --namespace Microsoft.Storage --query "registrationState" --output tsv
az provider show --namespace Microsoft.Network --query "registrationState" --output tsv
az provider show --namespace Microsoft.Compute --query "registrationState" --output tsv
```

> Registration can take 1-2 minutes. Re-run the verify commands until all three return `Registered` before proceeding.

---

## 2. Create a Resource Group

```bash
az group create \
  --name myResourceGroup \
  --location eastus
```

---

## 3. Public Storage Account

### 3.1 Create a Storage Account (Public Access)

```bash
az storage account create \
  --name mybsidesstorage123 \
  --resource-group myResourceGroup \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access true
```

> Storage account names must be **3-24 characters**, lowercase letters and numbers only — no hyphens. Must be globally unique across all Azure users.

### 3.2 Create a Blob Container with Public Access

```bash
az storage container create \
  --name mypubliccontainer \
  --account-name mybsidesstorage123 \
  --public-access blob \
  --auth-mode key
```

> **Public access levels:**
> - `blob` — anonymous read access for blobs only
> - `container` — anonymous read access for the container and all blobs
> - `off` — no public access (private)

### 3.3 Upload a File to the Public Container

```bash
# Create a test file first if you don't have one
echo "Hello from Azure!" > myfile.txt

# Upload it
az storage blob upload \
  --account-name mybsidesstorage123 \
  --container-name mypubliccontainer \
  --name myfile.txt \
  --file ./myfile.txt \
  --auth-mode key
```

---

## 4. Verify Resources

```bash
# List storage accounts
az storage account list --resource-group myResourceGroup --output table

# List blobs in the container
az storage blob list \
  --account-name mybsidesstorage123 \
  --container-name mypubliccontainer \
  --auth-mode key \
  --output table
```

> Public URL format: `https://mybsidesstorage123.blob.core.windows.net/mypubliccontainer/myfile.txt`

---

## 5. Clean Up Resources (Optional)

```bash
az group delete --name myResourceGroup --yes --no-wait
```

---

## Summary

| Resource          | Purpose                                   |
|-------------------|-------------------------------------------|
| Resource Group    | Logical container for all resources       |
| Storage Account   | Hosts publicly accessible blobs           |
| Blob Container    | Stores files with public read access      |
