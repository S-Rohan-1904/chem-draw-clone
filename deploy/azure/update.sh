#!/usr/bin/env bash
# Runs on the VM: move to a commit of main, rebuild, restart. Called by deploy.sh and,
# through a forced command on the GitHub Actions key, by .github/workflows/deploy.yml,
# which passes the commit that passed CI. Never moves backwards (fast-forward only).
#   deploy/azure/update.sh [<commit sha>]
set -euo pipefail

rev="${1:-${SSH_ORIGINAL_COMMAND:-origin/main}}"
if [[ ! "$rev" =~ ^[0-9a-f]{40}$ && "$rev" != origin/main ]]; then
  echo "update.sh: expected a full commit sha, got '$rev'" >&2
  exit 2
fi

cd /opt/chemforge
git fetch -q origin main
git merge -q --ff-only "$rev"
echo "At $(git log --oneline -1)"
cd deploy/azure
docker compose up -d --build
docker image prune -f >/dev/null
