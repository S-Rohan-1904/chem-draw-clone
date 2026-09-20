#!/usr/bin/env bash
# Start the backend. OPSIN needs a JVM; brew's openjdk is not on PATH by default.
set -euo pipefail
cd "$(dirname "$0")"
export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk}"
export PATH="$JAVA_HOME/bin:$PATH"
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
