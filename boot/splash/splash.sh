#!/usr/bin/env bash
# boot/splash/splash.sh — Display boot splash logo on framebuffer(s)
# Called early in boot (e.g. from rc.local or a systemd service).
# Uses fbi (framebuffer imageviewer) to show a PNG on /dev/fb0 and /dev/fb1.

set -euo pipefail

LOGO="/opt/rtesip/boot/splash/logo.png"

if [ ! -f "$LOGO" ]; then
    echo "splash: logo not found at $LOGO" >&2
    exit 0
fi

# Ensure fbi is available
if ! command -v fbi &>/dev/null; then
    echo "splash: fbi not installed, skipping splash" >&2
    exit 0
fi

for fb in /dev/fb0 /dev/fb1; do
    if [ -e "$fb" ]; then
        # -T 1       = use virtual terminal 1
        # -d $fb     = target framebuffer device
        # -noverbose = suppress status bar
        # --once     = display image and exit (no slideshow loop)
        fbi -T 1 -d "$fb" -noverbose --once "$LOGO" 2>/dev/null &
    fi
done

wait
exit 0
