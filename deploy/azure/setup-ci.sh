#!/usr/bin/env bash
# One-time setup of automatic deploys from GitHub Actions (run locally, after create-vm.sh
# and one ./deploy/azure/deploy.sh, with `gh auth login` done).
# Makes a separate SSH key for GitHub, lets it run only update.sh on the VM, and stores
# the key, the VM's host key and its address in the repository's Actions settings.
#   ./deploy/azure/setup-ci.sh
set -euo pipefail

LOCATION="${LOCATION:-centralindia}"
DNS_LABEL="${DNS_LABEL:-chemillustrator}"
KEY="${KEY:-$HOME/.ssh/chemforge_azure}"
HOST="${HOST:-$DNS_LABEL.$LOCATION.cloudapp.azure.com}"
CI_KEY="${CI_KEY:-$HOME/.ssh/chemforge_github_deploy}"

[ -f "$CI_KEY" ] || ssh-keygen -t ed25519 -N "" -C "chemforge-github-deploy" -f "$CI_KEY"

# restrict: no shell, pty or forwarding; whatever the client asks for, only update.sh runs.
LINE="restrict,command=\"/opt/chemforge/deploy/azure/update.sh\" $(cat "$CI_KEY.pub")"
ssh -i "$KEY" "azureuser@$HOST" "grep -qF '$(cut -d' ' -f2 "$CI_KEY.pub")' ~/.ssh/authorized_keys || echo '$LINE' >> ~/.ssh/authorized_keys"

# Host key as already trusted by this machine, so Actions never trusts a stranger.
KNOWN="$(ssh-keygen -F "$HOST" | grep -v '^#')"
[ -n "$KNOWN" ] || { echo "No known_hosts entry for $HOST; ssh to it once first." >&2; exit 1; }

gh secret set AZURE_SSH_KEY < "$CI_KEY"
gh secret set AZURE_KNOWN_HOSTS --body "$KNOWN"
gh variable set AZURE_HOST --body "$HOST"
echo "Done. Pushes to main now deploy after CI passes."
