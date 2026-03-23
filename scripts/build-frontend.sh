#!/usr/bin/env bash
# Build the SIP Reporter frontend and place output where FastAPI serves it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "==> Installing dependencies..."
cd "$FRONTEND_DIR"
npm install

echo "==> Building frontend..."
npm run build

# FastAPI serves from frontend/dist/ directly (see src/api/main.py),
# so the build output is already in the right place.
echo "==> Build complete. Output in $FRONTEND_DIR/dist/"
