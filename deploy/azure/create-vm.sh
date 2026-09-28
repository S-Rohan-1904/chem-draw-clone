#!/usr/bin/env bash
# Create the Chem Illustrator VM on Azure (run once, after `az login`).
#   LOCATION=centralindia DNS_LABEL=chemillustrator ./deploy/azure/create-vm.sh
# The site then lives at https://$DNS_LABEL.$LOCATION.cloudapp.azure.com
set -euo pipefail
cd "$(dirname "$0")"

LOCATION="${LOCATION:-centralindia}"
GROUP="${GROUP:-chemillustrator}"
VM="${VM:-chemillustrator}"
SIZE="${SIZE:-Standard_B2pls_v2}"   # Arm, 2 vCPU, 4 GB
DNS_LABEL="${DNS_LABEL:-chemillustrator}"
KEY="${KEY:-$HOME/.ssh/chemforge_azure}"

[ -f "$KEY" ] || ssh-keygen -t ed25519 -N "" -C "chemforge-azure" -f "$KEY"

az group create --name "$GROUP" --location "$LOCATION" -o none
az vm create \
  --resource-group "$GROUP" --name "$VM" --location "$LOCATION" \
  --image Canonical:ubuntu-24_04-lts:server-arm64:latest \
  --size "$SIZE" \
  --storage-sku StandardSSD_LRS --os-disk-size-gb 32 \
  --admin-username azureuser --ssh-key-values "$KEY.pub" \
  --public-ip-sku Standard --public-ip-address-dns-name "$DNS_LABEL" \
  --custom-data cloud-init.yaml \
  -o table
az vm open-port --resource-group "$GROUP" --name "$VM" --port 80,443 --priority 900 -o none

HOST="$DNS_LABEL.$LOCATION.cloudapp.azure.com"
echo "VM ready at $HOST. Waiting for first-boot setup (Docker, repository)..."
until ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "azureuser@$HOST" \
    'cloud-init status --wait >/dev/null 2>&1; test -d /opt/chemforge/.git'; do sleep 10; done

# Settings file on the VM: address and a fresh SECRET_KEY; secrets are added by hand later.
ssh -i "$KEY" "azureuser@$HOST" "cd /opt/chemforge/deploy/azure && [ -f .env ] || \
  sed -e 's|^SITE_ADDRESS=.*|SITE_ADDRESS=$HOST|' -e \"s|^SECRET_KEY=.*|SECRET_KEY=\$(openssl rand -base64 48 | tr -d '\\n')|\" .env.example > .env && chmod 600 .env"
echo "Done. Next: ./deploy/azure/deploy.sh"
