#!/usr/bin/env bash
# Deploy the latest main to the Azure VM: pull, rebuild, restart. Accounts and saved
# molecules live on the VM's disk (Docker volume) and survive this.
#   ./deploy/azure/deploy.sh
set -euo pipefail

LOCATION="${LOCATION:-centralindia}"
DNS_LABEL="${DNS_LABEL:-chemillustrator}"
KEY="${KEY:-$HOME/.ssh/chemforge_azure}"
HOST="${HOST:-$DNS_LABEL.$LOCATION.cloudapp.azure.com}"

# Pull first so a VM that predates update.sh gets it.
ssh -i "$KEY" "azureuser@$HOST" 'cd /opt/chemforge && git pull -q --ff-only && deploy/azure/update.sh'
echo "Deployed. Checking health..."
for i in $(seq 1 30); do
  if curl -fsS "https://$HOST/api/health" >/dev/null 2>&1; then echo "Live at https://$HOST"; exit 0; fi
  sleep 10
done
echo "Not answering yet; check: ssh -i $KEY azureuser@$HOST 'cd /opt/chemforge/deploy/azure && docker compose logs --tail 50'"
exit 1
