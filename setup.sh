#!/usr/bin/env bash
# Install everything needed once: Python deps, Node deps, backend/.env with a secret key.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1. $2" >&2; exit 1; }; }
need uv  "Install from https://docs.astral.sh/uv/"
need npm "Install Node 20+ from https://nodejs.org/"

if [ -z "${JAVA_HOME:-}" ] && [ -d /opt/homebrew/opt/openjdk ]; then
  export JAVA_HOME=/opt/homebrew/opt/openjdk
fi
[ -n "${JAVA_HOME:-}" ] && export PATH="$JAVA_HOME/bin:$PATH"
need java "Install a JDK, e.g. 'brew install openjdk' on macOS"

echo "==> Python deps"
(cd backend && uv sync)
echo "==> Node deps"
npm --prefix frontend install
if [ ! -f backend/.env ]; then
  echo "==> Writing backend/.env with a generated SECRET_KEY"
  printf 'SECRET_KEY=%s\n' "$(openssl rand -base64 48 | tr -d '\n')" > backend/.env
  chmod 600 backend/.env
fi
echo "Done. Start the app with ./start.sh"
