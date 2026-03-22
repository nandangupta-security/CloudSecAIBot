# Azure CLI: Public Storage & Internet-Accessible Virtual Machine

> **Note:** This guide uses **password-based authentication** for the VM — no SSH key is generated or required.

---

## Prerequisites

```bash
# Login to Azure
az login

# Set your subscription (optional)
az account set --subscription "<your-subscription-id>"
```

---

## 1. Create a Resource Group

```bash
az group create \
  --name myResourceGroup \
  --location eastus
```

---

## 2. Public Storage Account

### 2.1 Create a Storage Account (Public Access)

```bash
az storage account create \
  --name mystorageaccount123 \
  --resource-group myResourceGroup \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access true
```

### 2.2 Create a Blob Container with Public Access

```bash
az storage container create \
  --name mypubliccontainer \
  --account-name mystorageaccount123 \
  --public-access blob
```

> **Public access levels:**
> - `blob` — anonymous read access for blobs only
> - `container` — anonymous read access for the container and all blobs
> - `off` — no public access (private)

### 2.3 Upload a File to the Public Container

```bash
az storage blob upload \
  --account-name mystorageaccount123 \
  --container-name mypubliccontainer \
  --name myfile.txt \
  --file ./myfile.txt
```

### 2.4 Get the Public URL of a Blob

```bash
az storage blob url \
  --account-name mystorageaccount123 \
  --container-name mypubliccontainer \
  --name myfile.txt
```

---

## 3. Internet-Accessible Virtual Machine (No SSH Key)

### 3.1 Create a Virtual Network and Subnet

```bash
az network vnet create \
  --resource-group myResourceGroup \
  --name myVNet \
  --address-prefix 10.0.0.0/16 \
  --subnet-name mySubnet \
  --subnet-prefix 10.0.1.0/24
```

### 3.2 Create a Public IP Address

```bash
az network public-ip create \
  --resource-group myResourceGroup \
  --name myPublicIP \
  --sku Basic \
  --allocation-method Dynamic
```

### 3.3 Create a Network Security Group (NSG)

```bash
az network nsg create \
  --resource-group myResourceGroup \
  --name myNSG
```

### 3.4 Add Inbound Rules to Allow Internet Traffic

```bash
# Allow HTTP (port 80)
az network nsg rule create \
  --resource-group myResourceGroup \
  --nsg-name myNSG \
  --name AllowHTTP \
  --protocol Tcp \
  --direction Inbound \
  --priority 1000 \
  --source-address-prefix Internet \
  --source-port-range "*" \
  --destination-address-prefix "*" \
  --destination-port-range 80 \
  --access Allow

# Allow HTTPS (port 443)
az network nsg rule create \
  --resource-group myResourceGroup \
  --nsg-name myNSG \
  --name AllowHTTPS \
  --protocol Tcp \
  --direction Inbound \
  --priority 1010 \
  --source-address-prefix Internet \
  --source-port-range "*" \
  --destination-address-prefix "*" \
  --destination-port-range 443 \
  --access Allow

# Allow RDP (port 3389) — for Windows VMs
az network nsg rule create \
  --resource-group myResourceGroup \
  --nsg-name myNSG \
  --name AllowRDP \
  --protocol Tcp \
  --direction Inbound \
  --priority 1020 \
  --source-address-prefix Internet \
  --source-port-range "*" \
  --destination-address-prefix "*" \
  --destination-port-range 3389 \
  --access Allow
```

### 3.5 Create a Network Interface Card (NIC)

```bash
az network nic create \
  --resource-group myResourceGroup \
  --name myNIC \
  --vnet-name myVNet \
  --subnet mySubnet \
  --public-ip-address myPublicIP \
  --network-security-group myNSG
```

---

## 4. Verify Resources

```bash
# List VMs
az vm list --resource-group myResourceGroup --output table

# Get the public IP of the VM
az vm show \
  --resource-group myResourceGroup \
  --name myVM \
  --show-details \
  --query publicIps \
  --output tsv

# List storage accounts
az storage account list --resource-group myResourceGroup --output table
```

---

## 5. Clean Up Resources (Optional)

```bash
az group delete --name myResourceGroup --yes --no-wait
```

---

## Summary

| Resource              | Purpose                                      |
|-----------------------|----------------------------------------------|
| Storage Account       | Hosts publicly accessible blobs              |
| Blob Container        | Stores files with public read access         |
| Public IP             | Exposes the VM to the internet               |
| NSG Rules             | Opens HTTP/HTTPS/RDP ports to the internet   |
| VM (password auth)    | Internet-accessible, no SSH key required     |
