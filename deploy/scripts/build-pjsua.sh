#!/bin/bash
# Build pjsua 2.14.1 with rtesip Opus bitrate patch
# Run on the Raspberry Pi: sudo bash build-pjsua.sh
set -e

PJPROJECT_VERSION="2.16"
BUILD_DIR="/tmp/pjproject-build"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCH_FILE="$SCRIPT_DIR/../pjsua/pjsua_app.c.patch"

echo "=== Building pjsua $PJPROJECT_VERSION with Opus bitrate patch ==="

# Install build dependencies
apt-get update -qq
apt-get install -y -qq build-essential libssl-dev libopus-dev libasound2-dev wget

# Download source
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
echo "Downloading pjproject $PJPROJECT_VERSION..."
wget -q "https://github.com/pjsip/pjproject/archive/refs/tags/$PJPROJECT_VERSION.tar.gz" -O pjproject.tar.gz
tar xzf pjproject.tar.gz
cd "pjproject-$PJPROJECT_VERSION"

# Apply rtesip patches
echo "Applying pjsua_app.c patch..."
if [ -f "$PATCH_FILE" ]; then
    patch -p1 < "$PATCH_FILE"
else
    echo "ERROR: Patch file not found at $PATCH_FILE"
    exit 1
fi

OPUS_PATCH="$SCRIPT_DIR/../pjsua/opus.c.patch"
if [ -f "$OPUS_PATCH" ]; then
    echo "Applying opus.c bitrate patch..."
    patch -p1 < "$OPUS_PATCH"
fi

# Configure
echo "Configuring..."
./configure \
    --enable-shared \
    --disable-video \
    --disable-v4l2 \
    --disable-openh264 \
    --disable-libyuv \
    --disable-libwebrtc \
    CFLAGS="-O2 -fPIC"

# Build
echo "Building (this takes ~20 min on Pi 3)..."
make dep
make -j$(nproc)

# Find the built binary
PJSUA_BIN=$(find pjsip-apps/bin -name 'pjsua-*' -type f | head -1)
if [ -z "$PJSUA_BIN" ]; then
    echo "ERROR: pjsua binary not found after build"
    exit 1
fi

# Install
cp "$PJSUA_BIN" /usr/local/bin/pjsua
chmod +x /usr/local/bin/pjsua
echo "Installed: $(ls -la /usr/local/bin/pjsua)"

# Verify
echo ""
echo "=== Verifying ==="
OPUS_BITRATE=128000 timeout 3 /usr/local/bin/pjsua --help > /dev/null 2>&1 || true
echo "pjsua version: $(/usr/local/bin/pjsua --version 2>&1 | grep -o 'PJ_VERSION.*' | head -1 || echo 'installed')"

# Cleanup
cd /
rm -rf "$BUILD_DIR"

echo ""
echo "=== Done ==="
echo "Opus bitrate controlled via OPUS_BITRATE env var (set by rtesip)"
