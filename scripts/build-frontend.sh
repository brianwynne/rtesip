#!/usr/bin/env bash
# Build the SIP Reporter frontend and place output where FastAPI serves it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Check for node and npm
for cmd in node npm; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd is required but not found. Install Node.js 20+ and try again." >&2
        exit 1
    fi
done
echo "==> Using node $(node --version), npm $(npm --version)"

echo "==> Installing dependencies..."
cd "$FRONTEND_DIR"
npm ci

echo "==> Building frontend..."
npm run build

# FastAPI serves from frontend/dist/ directly (see src/api/main.py),
# so the build output is already in the right place.
echo "==> Build complete. Output in $FRONTEND_DIR/dist/"
