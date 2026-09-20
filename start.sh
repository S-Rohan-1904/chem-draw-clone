#!/usr/bin/env bash
# Run backend (:8000) and frontend (:5173) together. Ctrl-C stops both.
# Run ./setup.sh first.
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ -z "${JAVA_HOME:-}" ] && [ -d /opt/homebrew/opt/openjdk ]; then
  export JAVA_HOME=/opt/homebrew/opt/openjdk
fi
[ -n "${JAVA_HOME:-}" ] && export PATH="$JAVA_HOME/bin:$PATH"

for d in backend/.venv frontend/node_modules; do
  [ -d "$d" ] || { echo "Missing $d. Run ./setup.sh first." >&2; exit 1; }
done
command -v java >/dev/null 2>&1 || { echo "java not found. Install a JDK or set JAVA_HOME." >&2; exit 1; }

for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $p is already in use." >&2; exit 1
  fi
done

(cd backend && exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
BACK=$!
trap 'kill $BACK 2>/dev/null; wait $BACK 2>/dev/null' EXIT INT TERM

echo "Backend  http://localhost:$BACKEND_PORT"
echo "Frontend http://localhost:$FRONTEND_PORT   <- open this"
npm --prefix frontend run dev -- --port "$FRONTEND_PORT" --strictPort
