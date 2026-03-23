"""Generate SIP Reporter boot splash PNG for framebuffer display.

Run once during build/install to create the splash image.
Requires: pip install pillow
Output: /opt/rtesip/boot/splash/logo.png (800x480 for 7", also works on 3")
"""

import argparse
import math
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Install Pillow: pip install pillow")
    sys.exit(1)

WIDTH, HEIGHT = 800, 480
BG = (10, 10, 15)
ACCENT = (74, 108, 247)
GREY = (136, 136, 160)
WHITE = (232, 232, 240)

img = Image.new("RGB", (WIDTH, HEIGHT), BG)
draw = ImageDraw.Draw(img)

# Try to load a nice font, fall back to default
try:
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    font_light = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf", 72)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except OSError:
    font_large = ImageFont.load_default()
    font_light = font_large
    font_small = font_large

# Draw microphone icon (simplified)
cx, cy = WIDTH // 2, HEIGHT // 2 - 40

# Mic body
mic_w, mic_h = 28, 44
mic_r = mic_w // 2
draw.rounded_rectangle(
    [cx - 50 - mic_w // 2, cy - mic_h // 2, cx - 50 + mic_w // 2, cy + mic_h // 2],
    radius=mic_r, fill=ACCENT
)

# Mic stand arc
for angle_offset in range(-30, 31):
    a = math.radians(angle_offset + 270)
    r = 30
    x = cx - 50 + r * math.cos(a)
    y = cy + mic_h // 2 - 4 + r * math.sin(a) + r
    if y > cy + mic_h // 2:
        draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=GREY)

# Mic stand
draw.line([cx - 50, cy + mic_h // 2 + 26, cx - 50, cy + mic_h // 2 + 42], fill=GREY, width=3)
draw.line([cx - 62, cy + mic_h // 2 + 42, cx - 38, cy + mic_h // 2 + 42], fill=GREY, width=3)

# Signal waves
for i, opacity in enumerate([100, 160, 220]):
    r = 24 + i * 14
    color = (ACCENT[0], ACCENT[1], ACCENT[2], opacity)
    # Draw arc on the right side of mic
    for a_deg in range(-40, 41):
        a = math.radians(a_deg)
        x = cx - 50 + mic_w // 2 + 8 + r * math.cos(a)
        y = cy + r * math.sin(a)
        draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=ACCENT)

# "SIP" text
sip_bbox = draw.textbbox((0, 0), "SIP", font=font_large)
sip_w = sip_bbox[2] - sip_bbox[0]

# "Reporter" text
rep_bbox = draw.textbbox((0, 0), "Reporter", font=font_light)
rep_w = rep_bbox[2] - rep_bbox[0]

total_w = sip_w + 12 + rep_w
text_x = (WIDTH - total_w) // 2 + 20  # offset for mic icon
text_y = cy - 36

draw.text((text_x, text_y), "SIP", fill=ACCENT, font=font_large)
draw.text((text_x + sip_w + 12, text_y), "Reporter", fill=GREY, font=font_light)

# Determine version: CLI arg > VERSION file > fallback
parser = argparse.ArgumentParser(description="Generate boot splash image")
parser.add_argument("output", nargs="?", default="logo.png", help="Output PNG path")
parser.add_argument("--version", default=None, help="Version string (e.g. v1.0.0)")
args = parser.parse_args()

version = args.version
if not version:
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "VERSION")
    if os.path.isfile(version_file):
        version = open(version_file).read().strip()
    else:
        version = "v0.1.0"

# Version text at bottom
draw.text((WIDTH // 2 - 40, HEIGHT - 40), version, fill=(85, 85, 104), font=font_small)

img.save(args.output)
print(f"Splash image saved to {args.output}")
