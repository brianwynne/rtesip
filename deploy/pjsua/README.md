# pjsua 2.14.1 (patched for rtesip)

Custom pjsua build with Opus bitrate support via `OPUS_BITRATE` environment variable.

## Patch

`pjsua_app.c.patch` adds code after `pjsua_start()` that reads the `OPUS_BITRATE`
environment variable (in bps, e.g. `64000`) and calls
`pjmedia_codec_opus_set_default_param()` to configure the Opus encoder.

## Building

```bash
# On the Raspberry Pi:
sudo bash build-pjsua.sh
```

The script downloads pjproject 2.14.1 source, applies the patch, compiles,
and installs the binary to `/usr/local/bin/pjsua`.

## Pre-built binary

`pjsua-armhf` is a pre-built binary for Raspberry Pi (armhf/armv7l).
Copy to `/usr/local/bin/pjsua` and `chmod +x`.
