#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# rtesip — SIP Codec Installer for Linux (Raspberry Pi)
# ============================================================
# Installs (or upgrades) the rtesip SIP codec:
#   - FastAPI backend (SIP, audio, system management)
#   - React frontend (static SPA)
#   - systemd service: rtesip
#
# FHS-compliant directory layout:
#   /opt/rtesip/          — application code + venv
#   /etc/rtesip/          — configuration templates
#   /var/lib/rtesip/      — persistent data (config.json, contacts.json)
#   /var/log/rtesip/      — log files
#   /run/rtesip/          — runtime (PID files)
#
# Automatically detects fresh install vs upgrade.
# On upgrade: only code is updated — config, data, logs preserved.
#
# Usage:
#   cd /path/to/rtesip
#   sudo bash deploy/install.sh
#
#   # Or from extracted bundle:
#   sudo bash install.sh --local /path/to/bundle
#
#   # Uninstall:
#   sudo bash deploy/install.sh --uninstall
# ============================================================

# ── FHS directory layout ──────────────────────────────────────
INSTALL_DIR="/opt/rtesip"          # Application code + venv
CONFIG_DIR="/etc/rtesip"           # Configuration templates
DATA_DIR="/var/lib/rtesip"         # Persistent data (config.json, contacts.json)
LOG_DIR="/var/log/rtesip"          # Log files
RUN_DIR="/run/rtesip"              # Runtime (PID files)

LOCAL_DIR=""
SERVICE_USER="rtesip"
SERVICE_NAME="rtesip"
UNINSTALL=false

# ── Colours ─────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
fatal() { err "$@"; exit 1; }

# ── Parse arguments ─────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir)     INSTALL_DIR="$2"; shift 2 ;;
        --local)           LOCAL_DIR="$2"; shift 2 ;;
        --uninstall)       UNINSTALL=true; shift ;;
        --help|-h)
            echo "Usage: sudo bash install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --local <dir>           Source directory (auto-detected if omitted)"
            echo "  --install-dir <path>    Code install location (default: /opt/rtesip)"
            echo "  --uninstall             Remove rtesip from this system"
            echo "  --help                  Show this help"
            echo ""
            echo "Directory layout (FHS-compliant):"
            echo "  Code:     /opt/rtesip/"
            echo "  Config:   /etc/rtesip/"
            echo "  Data:     /var/lib/rtesip/  (config.json, contacts.json)"
            echo "  Logs:     /var/log/rtesip/"
            echo "  Runtime:  /run/rtesip/"
            echo ""
            echo "Automatically detects fresh install vs upgrade."
            echo "On upgrade: config, data, and logs are preserved — only code is updated."
            exit 0
            ;;
        *) fatal "Unknown option: $1" ;;
    esac
done

# ── Must run as root ─────────────────────────────────────────
if [[ "$(id -u)" -ne 0 ]]; then
    fatal "This script must be run as root (sudo)."
fi

# ══════════════════════════════════════════════════════════════
# UNINSTALL
# ══════════════════════════════════════════════════════════════
if [[ "$UNINSTALL" == "true" ]]; then
    echo ""
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "${YELLOW} rtesip — Uninstall${NC}"
    echo -e "${YELLOW}============================================================${NC}"
    echo ""

    # Phase 1: Services and code
    info "Stopping and disabling service..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    ok "Service removed"

    info "Removing application code ($INSTALL_DIR)..."
    rm -rf "$INSTALL_DIR"
    ok "Application code removed"

    info "Removing firewall rules..."
    if command -v ufw &>/dev/null; then
        ufw delete allow 80/tcp > /dev/null 2>&1 || true
        ufw delete allow 52002/udp > /dev/null 2>&1 || true
        ok "Firewall rules removed (SSH rule preserved)"
    fi

    # Remove tmpfiles.d config
    rm -f /etc/tmpfiles.d/rtesip.conf

    # Phase 2: Prompt for data removal
    echo ""
    info "The following data directories may still exist:"
    [[ -d "$CONFIG_DIR" ]] && echo "  Config:  $CONFIG_DIR"
    [[ -d "$DATA_DIR" ]]   && echo "  Data:    $DATA_DIR"
    [[ -d "$LOG_DIR" ]]    && echo "  Logs:    $LOG_DIR"
    echo ""

    if [[ -d "$CONFIG_DIR" ]]; then
        read -p "  Remove configuration? ($CONFIG_DIR) [y/N]: " -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
            ok "Configuration removed"
        else
            info "Configuration preserved"
        fi
    fi

    if [[ -d "$DATA_DIR" ]]; then
        read -p "  Remove data? ($DATA_DIR) [y/N]: " -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            rm -rf "$DATA_DIR"
            ok "Data removed"
        else
            info "Data preserved"
        fi
    fi

    if [[ -d "$LOG_DIR" ]]; then
        read -p "  Remove logs? ($LOG_DIR) [y/N]: " -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            rm -rf "$LOG_DIR"
            ok "Logs removed"
        else
            info "Logs preserved"
        fi
    fi

    if id -u "$SERVICE_USER" &>/dev/null; then
        read -p "  Remove system user '$SERVICE_USER'? [y/N]: " -r
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            userdel "$SERVICE_USER" 2>/dev/null || true
            ok "System user removed"
        else
            info "System user preserved"
        fi
    fi

    echo ""
    echo -e "${GREEN}Uninstall complete.${NC}"
    echo ""
    exit 0
fi

# ══════════════════════════════════════════════════════════════
# INSTALL / UPGRADE
# ══════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN} rtesip — SIP Codec Installer${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

# ── Auto-detect source directory ─────────────────────────────
if [[ -z "$LOCAL_DIR" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    # Check if run from deploy/ inside the repo
    if [[ -f "$SCRIPT_DIR/../run.py" && -d "$SCRIPT_DIR/../src" ]]; then
        LOCAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
        info "Auto-detected source directory: $LOCAL_DIR"
    # Check if run from the repo root
    elif [[ -f "$SCRIPT_DIR/run.py" && -d "$SCRIPT_DIR/src" ]]; then
        LOCAL_DIR="$SCRIPT_DIR"
        info "Auto-detected source directory: $LOCAL_DIR"
    else
        fatal "Source not found. Run from the project directory or use --local <directory>."
    fi
fi

# ── Detect install vs upgrade ────────────────────────────────
UPGRADE=false
BACKUP_DIR=""
if [[ -f "$DATA_DIR/config.json" ]]; then
    UPGRADE=true
    info "Existing installation detected — performing upgrade."
else
    info "No existing installation — performing fresh install."
fi

# ── Check prerequisites ─────────────────────────────────────
info "Checking prerequisites..."

# Python 3.10+
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=${ver%%.*}
        minor=${ver##*.}
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON="$cmd"
            break
        fi
    fi
done
[[ -n "$PYTHON" ]] || fatal "Python 3.10+ is required. Install it and try again."
ok "Python: $($PYTHON --version)"

# Ensure python3-venv is available
if ! $PYTHON -m venv --help &>/dev/null; then
    info "Installing python3-venv..."
    apt-get update -qq
    apt-get install -y -qq python3-venv > /dev/null 2>&1 \
        || apt-get install -y -qq python3.12-venv > /dev/null 2>&1 \
        || apt-get install -y -qq python3.11-venv > /dev/null 2>&1 \
        || fatal "Could not install python3-venv. Install it manually and retry."
    ok "python3-venv installed"
fi

# ── Verify source structure ──────────────────────────────────
info "Using source from: $LOCAL_DIR"
[[ -d "$LOCAL_DIR" ]] || fatal "Directory not found: $LOCAL_DIR"

[[ -f "$LOCAL_DIR/run.py" ]]            || fatal "Source missing: run.py"
[[ -d "$LOCAL_DIR/src" ]]               || fatal "Source missing: src/"
[[ -f "$LOCAL_DIR/requirements.txt" ]]  || fatal "Source missing: requirements.txt"
ok "Source structure verified."

# ── Create system user ──────────────────────────────────────
if ! id -u "$SERVICE_USER" &>/dev/null; then
    info "Creating system user: $SERVICE_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    ok "System user created: $SERVICE_USER"
else
    ok "System user exists: $SERVICE_USER"
fi

# ── Stop service (upgrade) ──────────────────────────────────
if [[ "$UPGRADE" == "true" ]]; then
    info "Stopping service for upgrade..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    ok "Service stopped"

    # Backup config and data
    BACKUP_DIR="$INSTALL_DIR/.backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    for f in "$DATA_DIR/config.json" "$DATA_DIR/contacts.json"; do
        [[ -f "$f" ]] && cp "$f" "$BACKUP_DIR/"
    done

    ok "Backup saved to $BACKUP_DIR"
fi

# ── Create FHS directories ──────────────────────────────────
info "Creating directory layout..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$RUN_DIR"

# tmpfiles.d entry so /run/rtesip survives reboot
cat > /etc/tmpfiles.d/rtesip.conf <<TMPEOF
d /run/rtesip 0755 root root -
TMPEOF

ok "FHS directories created"

# ── Set FHS directory ownership ─────────────────────────────
chown root:root "$CONFIG_DIR"
chown root:root "$DATA_DIR"
chown root:root "$LOG_DIR"
chown root:root "$RUN_DIR"
chmod 755 "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$RUN_DIR"

# ── Copy application code ───────────────────────────────────
info "Installing application code..."

# On upgrade: clean old code but preserve venv
if [[ "$UPGRADE" == "true" ]]; then
    # Remove old source files (not venv, not frontend dist if we fail to rebuild)
    rm -rf "$INSTALL_DIR/src"
    rm -f "$INSTALL_DIR/run.py"
    rm -f "$INSTALL_DIR/requirements.txt"
fi

# Copy source code
cp -r "$LOCAL_DIR/src" "$INSTALL_DIR/"
cp "$LOCAL_DIR/run.py" "$INSTALL_DIR/"
cp "$LOCAL_DIR/requirements.txt" "$INSTALL_DIR/"

# Copy boot assets if present
if [[ -d "$LOCAL_DIR/boot" ]]; then
    cp -r "$LOCAL_DIR/boot" "$INSTALL_DIR/"
fi

# Copy conf templates if present
if [[ -d "$LOCAL_DIR/conf" ]]; then
    cp -r "$LOCAL_DIR/conf" "$INSTALL_DIR/"
fi

ok "Application code installed"

# ── Install Python venv and dependencies ─────────────────────
info "Setting up Python virtual environment..."

if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    $PYTHON -m venv "$INSTALL_DIR/.venv"
    ok "Virtual environment created"
else
    ok "Virtual environment exists (reusing)"
fi

info "Installing Python dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Python dependencies installed"

# ── Build or copy frontend ───────────────────────────────────
info "Setting up frontend..."

FRONTEND_SRC="$LOCAL_DIR/frontend"
FRONTEND_DEST="$INSTALL_DIR/frontend/dist"

if [[ -d "$FRONTEND_SRC" ]]; then
    # Option 1: Pre-built dist exists in source
    if [[ -d "$FRONTEND_SRC/dist" && -f "$FRONTEND_SRC/dist/index.html" ]]; then
        mkdir -p "$INSTALL_DIR/frontend"
        rm -rf "$FRONTEND_DEST"
        cp -r "$FRONTEND_SRC/dist" "$FRONTEND_DEST"
        ok "Frontend installed (pre-built dist)"

    # Option 2: Build from source if node/npm available
    elif command -v node &>/dev/null && command -v npm &>/dev/null; then
        info "Building frontend from source..."
        cd "$FRONTEND_SRC"

        # Install dependencies if needed
        if [[ ! -d "$FRONTEND_SRC/node_modules" ]]; then
            npm ci --quiet 2>/dev/null || npm install --quiet
        fi

        npm run build
        cd - > /dev/null

        mkdir -p "$INSTALL_DIR/frontend"
        rm -rf "$FRONTEND_DEST"
        cp -r "$FRONTEND_SRC/dist" "$FRONTEND_DEST"
        ok "Frontend built and installed"
    else
        warn "No pre-built frontend and node/npm not available — skipping frontend."
        warn "The API will run without a web interface."
    fi
else
    warn "Frontend source directory not found — skipping."
fi

# ── Install VERSION file ────────────────────────────────────
if [[ -f "$LOCAL_DIR/VERSION" ]]; then
    cp "$LOCAL_DIR/VERSION" "$INSTALL_DIR/VERSION"
    ok "Version: $(cat "$INSTALL_DIR/VERSION")"
fi

# ── Install systemd service ─────────────────────────────────
info "Installing systemd service..."

SYSTEMD_SRC="$LOCAL_DIR/deploy/systemd/rtesip.service"
if [[ ! -f "$SYSTEMD_SRC" ]]; then
    # Fallback: look relative to script location
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    SYSTEMD_SRC="$SCRIPT_DIR/systemd/rtesip.service"
fi

if [[ -f "$SYSTEMD_SRC" ]]; then
    cp "$SYSTEMD_SRC" /etc/systemd/system/rtesip.service
else
    # Generate a service file if none found
    cat > /etc/systemd/system/rtesip.service <<SVCEOF
[Unit]
Description=rtesip SIP Codec
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python run.py
Restart=always
RestartSec=3

# Hardening
ProtectSystem=strict
ReadWritePaths=$DATA_DIR $RUN_DIR /boot
NoNewPrivileges=true
ProtectHome=true
PrivateTmp=true

# RT priority for audio subprocess
LimitRTPRIO=99
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
SVCEOF
    ok "Generated systemd service file"
fi

systemctl daemon-reload
ok "Systemd service installed"

# ── Install CLI ──────────────────────────────────────────────
info "Installing CLI..."
if [ -f "$LOCAL_DIR/deploy/sip-reporter-cli.sh" ]; then
    cp "$LOCAL_DIR/deploy/sip-reporter-cli.sh" /usr/local/bin/sip-reporter
    chmod +x /usr/local/bin/sip-reporter
    ok "CLI installed at /usr/local/bin/sip-reporter"
elif [ -f "$INSTALL_DIR/deploy/sip-reporter-cli.sh" ]; then
    cp "$INSTALL_DIR/deploy/sip-reporter-cli.sh" /usr/local/bin/sip-reporter
    chmod +x /usr/local/bin/sip-reporter
    ok "CLI installed at /usr/local/bin/sip-reporter"
else
    warn "CLI script not found, skipping"
fi

# ── Install pjsua binary ─────────────────────────────────────
info "Installing pjsua..."
ARCH=$(dpkg --print-architecture)
PJSUA_SRC=""
if [ "$ARCH" = "armhf" ] && [ -f "$LOCAL_DIR/deploy/bin/pjsua-armhf" ]; then
    PJSUA_SRC="$LOCAL_DIR/deploy/bin/pjsua-armhf"
elif [ -f "$INSTALL_DIR/deploy/bin/pjsua-armhf" ] && [ "$ARCH" = "armhf" ]; then
    PJSUA_SRC="$INSTALL_DIR/deploy/bin/pjsua-armhf"
fi

if [ -n "$PJSUA_SRC" ]; then
    cp "$PJSUA_SRC" /usr/local/bin/pjsua
    chmod +x /usr/local/bin/pjsua

    # Install pjsua runtime dependencies
    info "Installing pjsua dependencies..."
    apt-get -qq install -y libasound2 libopus0 uuid-runtime 2>/dev/null || true

    # libssl1.1 needed but not in Bookworm — install from Bullseye if missing
    if ! ldconfig -p | grep -q "libssl.so.1.1"; then
        info "Installing libssl1.1 compatibility..."
        if [ "$ARCH" = "armhf" ]; then
            curl -fsSL -o /tmp/libssl1.1.deb "http://archive.raspberrypi.com/debian/pool/main/o/openssl/libssl1.1_1.1.1w-0+deb11u2_armhf.deb" 2>/dev/null && \
            dpkg -i /tmp/libssl1.1.deb 2>/dev/null && rm -f /tmp/libssl1.1.deb && \
            ok "libssl1.1 installed" || warn "Could not install libssl1.1 — pjsua may not start"
        fi
    fi

    ok "pjsua installed at /usr/local/bin/pjsua"
else
    warn "No pjsua binary found for architecture $ARCH — SIP calls will not work until pjsua is installed"
fi

# ── Set code directory ownership ─────────────────────────────
info "Setting file ownership..."
chown -R root:root "$INSTALL_DIR"
ok "Ownership set"

# ── Set CPU performance governor ─────────────────────────────
info "Setting CPU performance governor..."
GOVERNOR_PATH="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
if [[ -f "$GOVERNOR_PATH" ]]; then
    # Set performance governor on all CPUs
    for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo "performance" > "$gov" 2>/dev/null || true
    done

    # Make it persistent via /etc/rc.local if not already there
    if [[ -f /etc/rc.local ]]; then
        if ! grep -q "scaling_governor" /etc/rc.local; then
            sed -i '/^exit 0/i for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$gov" 2>/dev/null || true; done' /etc/rc.local
        fi
    fi
    ok "CPU governor set to performance (all CPUs)"
else
    info "CPU frequency scaling not available (VM or container) — skipping."
fi

# ── Configure firewall ──────────────────────────────────────
info "Configuring firewall..."
if command -v ufw &>/dev/null; then
    # Ensure SSH is allowed before enabling
    ufw allow 22/tcp > /dev/null 2>&1 || true

    # HTTP for web interface
    ufw allow 80/tcp > /dev/null 2>&1 || true

    # AES67 multicast
    ufw allow 52002/udp > /dev/null 2>&1 || true

    # Enable if not already
    if ! ufw status | grep -q "Status: active"; then
        echo "y" | ufw enable > /dev/null 2>&1 || true
    fi

    ok "Firewall configured (SSH, HTTP, AES67 multicast)"
else
    warn "ufw not found — skipping firewall configuration."
    warn "Install ufw and re-run, or manually configure your firewall."
fi

# ── Enable and start service ─────────────────────────────────
info "Enabling and starting rtesip service..."
systemctl enable "$SERVICE_NAME" > /dev/null 2>&1
systemctl start "$SERVICE_NAME"
ok "Service started"

# ── Print status ────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN} rtesip — Installation Complete${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

if [[ "$UPGRADE" == "true" ]]; then
    echo -e "  Mode:       ${YELLOW}Upgrade${NC} (config and data preserved)"
    [[ -n "$BACKUP_DIR" ]] && echo -e "  Backup:     $BACKUP_DIR"
else
    echo -e "  Mode:       ${GREEN}Fresh install${NC}"
fi
echo ""
echo "  Directory layout:"
echo "    Code:     $INSTALL_DIR/"
echo "    Config:   $CONFIG_DIR/"
echo "    Data:     $DATA_DIR/"
echo "    Logs:     $LOG_DIR/"
echo "    Runtime:  $RUN_DIR/"
echo ""
echo "  Service:    systemctl status $SERVICE_NAME"
echo "  Logs:       journalctl -u $SERVICE_NAME -f"
echo ""

# Show service status
systemctl --no-pager status "$SERVICE_NAME" 2>/dev/null || true

echo ""
