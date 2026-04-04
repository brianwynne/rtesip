"""Build pjsua.exe for Windows with rtesip Opus patches.

Run from "Developer Command Prompt for VS 2022":
    python deploy/scripts/build-pjsua-win.py

Prerequisites:
    - Visual Studio 2022 with C++ Desktop Development
    - Python 3.10+
    - Internet connection (downloads pjproject source)
"""

import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

PJPROJECT_VERSION = "2.16"
BUILD_DIR = Path(os.environ.get("TEMP", ".")) / "pjproject-build"
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent.parent
OUTPUT_DIR = REPO_DIR / "pjsua"


def check_prerequisites():
    """Verify Visual Studio compiler is available."""
    try:
        subprocess.run(["cl"], capture_output=True, timeout=5)
    except FileNotFoundError:
        print("ERROR: cl.exe not found.")
        print("Run this from 'Developer Command Prompt for VS 2022'")
        print("or 'x64 Native Tools Command Prompt for VS 2022'")
        sys.exit(1)
    print("Visual Studio compiler found")


def download_source():
    """Download and extract pjproject source."""
    src_dir = BUILD_DIR / f"pjproject-{PJPROJECT_VERSION}"
    if src_dir.exists():
        print(f"Source already exists at {src_dir}")
        return src_dir

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tarball = BUILD_DIR / "pjproject.tar.gz"

    if not tarball.exists():
        url = f"https://github.com/pjsip/pjproject/archive/refs/tags/{PJPROJECT_VERSION}.tar.gz"
        print(f"Downloading pjproject {PJPROJECT_VERSION}...")
        urllib.request.urlretrieve(url, tarball)

    print("Extracting...")
    with tarfile.open(tarball) as tf:
        tf.extractall(BUILD_DIR)

    return src_dir


def create_config_site(src_dir: Path):
    """Create config_site.h with Opus/TLS/SRTP enabled."""
    config = src_dir / "pjlib" / "include" / "pj" / "config_site.h"
    config.write_text("""\
/* rtesip config_site.h — enable Opus, TLS, SRTP */
#define PJMEDIA_HAS_OPUS_CODEC 1
#define PJ_HAS_SSL_SOCK 1
#define PJMEDIA_HAS_SRTP 1
#define PJMEDIA_SRTP_HAS_SDES 1
#define PJMEDIA_SRTP_HAS_DTLS 0
#define PJMEDIA_AUDIO_DEV_HAS_WMME 1
""")
    print("config_site.h created")


def apply_opus_patch(src_dir: Path):
    """Apply rtesip Opus patches to pjsua_app.c and opus.c."""

    # Patch pjsua_app.c
    app_file = src_dir / "pjsip-apps" / "src" / "pjsua" / "pjsua_app.c"
    src = app_file.read_text(encoding="utf-8")

    if "OPUS_BITRATE" in src:
        print("pjsua_app.c already patched")
    else:
        # Add includes
        src = src.replace(
            '#include "pjsua_app.h"\n',
            '#include "pjsua_app.h"\n\n#include <pjmedia-codec/opus.h>\n#include <stdlib.h>\n',
            1
        )

        # Add Opus config block after "app_running = PJ_TRUE;"
        opus_block = '''
    /* Apply Opus settings from environment variables (rtesip patch) */
    {
        const char *env_br = getenv("OPUS_BITRATE");
        const char *env_cx = getenv("OPUS_COMPLEXITY");
        const char *env_cbr = getenv("OPUS_CBR");
        const char *env_fec = getenv("OPUS_FEC");
        const char *env_pl = getenv("OPUS_PACKET_LOSS");
        const char *env_stereo = getenv("OPUS_STEREO");

        if (env_br || env_cx || env_cbr || env_fec || env_pl || env_stereo) {
            pjmedia_codec_opus_config opus_cfg;
            pj_status_t opus_st;
            opus_st = pjmedia_codec_opus_get_config(&opus_cfg);
            if (opus_st == PJ_SUCCESS) {
                pjmedia_codec_param param;
                pjmedia_codec_mgr *cmgr;
                const pjmedia_codec_info *ci;
                unsigned cnt = 1;
                unsigned dec_idx = 0;
                unsigned enc_idx = 0;
                static char maxbr_dec_buf[16];
                static char maxbr_enc_buf[16];

                if (env_br) {
                    unsigned v = (unsigned)atoi(env_br);
                    if (v >= 6000 && v <= 510000) opus_cfg.bit_rate = v;
                }
                if (env_cx) {
                    unsigned v = (unsigned)atoi(env_cx);
                    if (v <= 10) opus_cfg.complexity = v;
                }
                if (env_cbr) {
                    opus_cfg.cbr = (atoi(env_cbr) != 0);
                }
                if (env_pl) {
                    unsigned v = (unsigned)atoi(env_pl);
                    if (v <= 100) opus_cfg.packet_loss = v;
                }

                cmgr = pjmedia_endpt_get_codec_mgr(pjsua_get_pjmedia_endpt());
                if (cmgr) {
                    pj_str_t cid = pj_str("opus/48000/2");
                    opus_st = pjmedia_codec_mgr_find_codecs_by_id(cmgr, &cid, &cnt, &ci, NULL);
                    if (opus_st == PJ_SUCCESS && cnt > 0) {
                        opus_st = pjmedia_codec_mgr_get_default_param(cmgr, ci, &param);
                        if (opus_st == PJ_SUCCESS) {
                            if (env_br) {
                                param.info.avg_bps = (unsigned)atoi(env_br);
                            }
                            dec_idx = 0;
                            if (env_br) {
                                snprintf(maxbr_dec_buf, sizeof(maxbr_dec_buf), "%s", env_br);
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].name, "maxaveragebitrate");
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].val, maxbr_dec_buf);
                                dec_idx++;
                            }
                            if (env_cbr && atoi(env_cbr) != 0) {
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].name, "cbr");
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].val, "1");
                                dec_idx++;
                            }
                            if (env_fec && atoi(env_fec) != 0) {
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].name, "useinbandfec");
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].val, "1");
                                dec_idx++;
                            }
                            if (env_stereo && atoi(env_stereo) != 0) {
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].name, "stereo");
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].val, "1");
                                dec_idx++;
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].name, "sprop-stereo");
                                pj_strset2(&param.setting.dec_fmtp.param[dec_idx].val, "1");
                                dec_idx++;
                            }
                            param.setting.dec_fmtp.cnt = dec_idx;
                            enc_idx = 0;
                            if (env_br) {
                                snprintf(maxbr_enc_buf, sizeof(maxbr_enc_buf), "%s", env_br);
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].name, "maxaveragebitrate");
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].val, maxbr_enc_buf);
                                enc_idx++;
                            }
                            if (env_cbr && atoi(env_cbr) != 0) {
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].name, "cbr");
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].val, "1");
                                enc_idx++;
                            }
                            if (env_stereo && atoi(env_stereo) != 0) {
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].name, "stereo");
                                pj_strset2(&param.setting.enc_fmtp.param[enc_idx].val, "1");
                                enc_idx++;
                            }
                            param.setting.enc_fmtp.cnt = enc_idx;
                            opus_st = pjmedia_codec_opus_set_default_param(&opus_cfg, &param);
                            if (opus_st == PJ_SUCCESS) {
                                PJ_LOG(3, (THIS_FILE, "Opus config: br=%u cx=%u cbr=%d pl=%u fec=%s stereo=%s avg_bps=%u",
                                    opus_cfg.bit_rate, opus_cfg.complexity,
                                    opus_cfg.cbr, opus_cfg.packet_loss,
                                    (env_fec && atoi(env_fec)) ? "on" : "off",
                                    (env_stereo && atoi(env_stereo)) ? "on" : "off",
                                    param.info.avg_bps));
                            }
                        }
                    }
                }
            }
        }
    }
'''
        src = src.replace(
            "app_running = PJ_TRUE;\n",
            "app_running = PJ_TRUE;\n" + opus_block,
            1
        )

        app_file.write_text(src, encoding="utf-8")
        print("pjsua_app.c patched")

    # Patch opus.c — force configured bitrate
    opus_file = src_dir / "pjmedia" / "src" / "pjmedia-codec" / "opus.c"
    opus_src = opus_file.read_text(encoding="utf-8")

    if "rtesip: use configured bitrate" in opus_src:
        print("opus.c already patched")
    else:
        old = "    pj_bool_t auto_bit_rate = PJ_TRUE;"
        new = """    pj_bool_t auto_bit_rate = PJ_TRUE;

    /* rtesip: use configured bitrate as baseline, allow SDP to cap lower */
    if (opus_cfg.bit_rate > 0) {
        auto_bit_rate = PJ_FALSE;
        if (attr->info.avg_bps == 0 || attr->info.avg_bps > (unsigned)opus_cfg.bit_rate) {
            attr->info.avg_bps = opus_cfg.bit_rate;
        }
    }"""
        opus_src = opus_src.replace(old, new, 1)
        opus_file.write_text(opus_src, encoding="utf-8")
        print("opus.c patched")


def retarget_solution(src_dir: Path):
    """Upgrade .vcxproj files to use the installed VS platform toolset."""
    import re
    import glob

    # Detect installed toolset version
    result = subprocess.run(["msbuild", "-version"], capture_output=True, text=True)
    msbuild_ver = result.stdout.strip().splitlines()[-1] if result.returncode == 0 else ""
    print(f"MSBuild version: {msbuild_ver}")

    # Map MSBuild major version to platform toolset (vXY0 format)
    major = msbuild_ver.split(".")[0] if msbuild_ver else "17"
    toolset = f"v{major}0"  # MSBuild 17 → v170, 18 → v180
    print(f"Retargeting to platform toolset: {toolset}")

    # Update all .vcxproj and .props files
    count = 0
    for pattern in ("**/*.vcxproj", "**/*.props"):
        for filepath in glob.glob(str(src_dir / pattern), recursive=True):
            text = Path(filepath).read_text(encoding="utf-8")
            new_text = re.sub(
                r"<PlatformToolset>v\d+</PlatformToolset>",
                f"<PlatformToolset>{toolset}</PlatformToolset>",
                text
            )
            new_text = re.sub(
                r"<BuildToolset>v\d+</BuildToolset>",
                f"<BuildToolset>{toolset}</BuildToolset>",
                new_text
            )
            if new_text != text:
                Path(filepath).write_text(new_text, encoding="utf-8")
                count += 1
    print(f"Retargeted {count} project/props files")


def build(src_dir: Path):
    """Build pjsua using MSBuild."""
    sln = src_dir / "pjproject-vs14.sln"
    if not sln.exists():
        print(f"ERROR: Solution file not found: {sln}")
        sys.exit(1)

    # Retarget to installed VS version
    retarget_solution(src_dir)

    print("Building pjsua (this may take several minutes)...")
    result = subprocess.run(
        ["msbuild", str(sln),
         "/t:pjsua", "/p:Configuration=Release", "/p:Platform=Win32",
         "/m", "/v:m"],
        cwd=str(src_dir),
    )
    if result.returncode != 0:
        print("ERROR: Build failed!")
        sys.exit(1)

    # Find the binary
    for f in (src_dir / "pjsip-apps" / "bin").rglob("pjsua*.exe"):
        return f

    print("ERROR: pjsua.exe not found after build")
    sys.exit(1)


def install(pjsua_exe: Path):
    """Copy pjsua.exe to the project."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUTPUT_DIR / "pjsua.exe"

    import shutil
    shutil.copy2(pjsua_exe, dest)
    print(f"\nInstalled: {dest}")
    print(f"Test: {dest} --help")


def main():
    print("=" * 60)
    print(f" Building pjsua {PJPROJECT_VERSION} for Windows")
    print("=" * 60)

    check_prerequisites()
    src_dir = download_source()
    create_config_site(src_dir)
    apply_opus_patch(src_dir)
    pjsua_exe = build(src_dir)
    install(pjsua_exe)

    print("\n" + "=" * 60)
    print(" Build complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
