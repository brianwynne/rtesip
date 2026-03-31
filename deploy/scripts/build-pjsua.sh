#!/bin/bash
# Build pjsua 2.14.1 with Opus bitrate support
# Run on the Raspberry Pi: sudo bash build-pjsua.sh
set -e

PJPROJECT_VERSION="2.14.1"
BUILD_DIR="/tmp/pjproject-build"

echo "=== Building pjsua $PJPROJECT_VERSION with Opus bitrate patch ==="

# Install build dependencies
apt-get update
apt-get install -y build-essential libssl-dev libopus-dev libasound2-dev

# Download source
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
wget -q "https://github.com/pjsip/pjproject/archive/refs/tags/$PJPROJECT_VERSION.tar.gz" -O pjproject.tar.gz
tar xzf pjproject.tar.gz
cd "pjproject-$PJPROJECT_VERSION"

# Apply Opus bitrate patch
# This adds --opus-bitrate=N flag to pjsua CLI app
PATCH_FILE="pjsip-apps/src/pjsua/pjsua_app_config.c"
if [ ! -f "$PATCH_FILE" ]; then
    echo "ERROR: $PATCH_FILE not found — source structure may have changed"
    exit 1
fi

# Find the line with OPT_DURATION or similar to add our option nearby
# We'll patch pjsua_app.c instead — it has the post-init hook
APP_FILE="pjsip-apps/src/pjsua/pjsua_app.c"

# Create the patch: read OPUS_BITRATE env var after codec init
# This is simpler and more robust than adding a CLI flag
cat > /tmp/opus-bitrate.patch << 'PATCHEOF'
--- a/pjsip-apps/src/pjsua/pjsua_app.c
+++ b/pjsip-apps/src/pjsua/pjsua_app.c
@@ -26,6 +26,7 @@
 #include <pjlib-util.h>
 #include <pjlib.h>
 #include <pjsua-lib/pjsua.h>
+#include <pjmedia-codec/opus.h>
 #include "pjsua_app_common.h"

 #define THIS_FILE	"pjsua_app.c"
PATCHEOF

# Apply the include patch (may fail if line numbers differ, so do it manually)
if ! grep -q 'pjmedia-codec/opus.h' "$APP_FILE"; then
    sed -i '/#include "pjsua_app_common.h"/i #include <pjmedia-codec/opus.h>' "$APP_FILE"
fi

# Add opus bitrate configuration after pjsua_start() call
# Find "app_config.on_started" or the startup function and add our code after it
# We'll inject after pjsua_start() returns successfully

# Create a helper C file that gets called during pjsua init
cat > pjsip-apps/src/pjsua/opus_bitrate.h << 'HEOF'
#ifndef __OPUS_BITRATE_H__
#define __OPUS_BITRATE_H__

#include <pjmedia-codec/opus.h>
#include <pjmedia/codec.h>
#include <pjlib.h>
#include <stdlib.h>

static void apply_opus_bitrate_from_env(void) {
    const char *env_val = getenv("OPUS_BITRATE");
    if (env_val) {
        unsigned bitrate = (unsigned)atoi(env_val);
        if (bitrate >= 6000 && bitrate <= 510000) {
            pjmedia_codec_opus_config opus_cfg;
            pj_status_t status;

            status = pjmedia_codec_opus_get_config(&opus_cfg);
            if (status == PJ_SUCCESS) {
                opus_cfg.bit_rate = bitrate;
                pjmedia_codec_param param;
                pjmedia_codec_mgr *codec_mgr;
                const pjmedia_codec_info *codec_info;
                unsigned count = 1;

                codec_mgr = pjmedia_endpt_get_codec_mgr(pjsua_get_pjmedia_endpt());
                if (codec_mgr) {
                    pj_str_t codec_id = pj_str("opus/48000/2");
                    status = pjmedia_codec_mgr_find_codecs_by_id(codec_mgr, &codec_id,
                                                                  &count, &codec_info, NULL);
                    if (status == PJ_SUCCESS && count > 0) {
                        status = pjmedia_codec_mgr_get_default_param(codec_mgr, codec_info, &param);
                        if (status == PJ_SUCCESS) {
                            status = pjmedia_codec_opus_set_default_param(&opus_cfg, &param);
                            if (status == PJ_SUCCESS) {
                                PJ_LOG(3, ("opus_bitrate", "Opus bitrate set to %u bps", bitrate));
                            }
                        }
                    }
                }
            }
        }
    }
}

#endif
HEOF

# Inject the call into pjsua_app.c after pjsua_start()
# Find the function that calls pjsua_start and add our hook
if ! grep -q 'apply_opus_bitrate_from_env' "$APP_FILE"; then
    # Add include
    sed -i '/#include "pjsua_app_common.h"/a #include "opus_bitrate.h"' "$APP_FILE"

    # Find pjsua_start() call and add our function after it
    # Pattern: look for "pjsua_start()" and add after the next line
    sed -i '/pjsua_start()/,/^[[:space:]]*}/ {
        /pjsua_start()/ {
            n
            a\    apply_opus_bitrate_from_env();
        }
    }' "$APP_FILE"
fi

echo "=== Opus bitrate patch applied ==="

# Configure
./configure \
    --enable-shared \
    --with-external-opus \
    --disable-video \
    --disable-v4l2 \
    --disable-openh264 \
    --disable-libyuv \
    --disable-libwebrtc \
    CFLAGS="-O2 -fPIC"

# Build
make dep
make -j$(nproc)

# Install pjsua binary
cp pjsip-apps/bin/pjsua-* /usr/local/bin/pjsua
chmod +x /usr/local/bin/pjsua

echo "=== pjsua installed ==="
echo "Opus bitrate is controlled via OPUS_BITRATE environment variable"
echo "Example: OPUS_BITRATE=128000 pjsua ..."

# Cleanup
cd /
rm -rf "$BUILD_DIR"

echo "=== Done ==="
