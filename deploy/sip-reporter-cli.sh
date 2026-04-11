#!/bin/bash
# SIP Reporter CLI — management commands
# Installed to /usr/local/bin/sip-reporter

set -euo pipefail

SERVICE="rtesip"
INSTALL_DIR="/opt/rtesip"
DATA_DIR="/var/lib/rtesip"
LOG_DIR="/var/log/rtesip"
CONFIG_DIR="/etc/rtesip"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

version() {
    if [ -f "$INSTALL_DIR/VERSION" ]; then
        echo "SIP Reporter $(cat "$INSTALL_DIR/VERSION")"
    else
        echo "SIP Reporter (version unknown)"
    fi
}

status() {
    version
    echo ""
    systemctl status "$SERVICE" --no-pager 2>/dev/null || echo -e "${RED}Service not found${NC}"
}

start() {
    echo "Starting SIP Reporter..."
    systemctl start "$SERVICE"
    echo -e "${GREEN}Started${NC}"
}

stop() {
    echo "Stopping SIP Reporter..."
    systemctl stop "$SERVICE"
    echo -e "${YELLOW}Stopped${NC}"
}

restart() {
    echo "Restarting SIP Reporter..."
    systemctl restart "$SERVICE"
    echo -e "${GREEN}Restarted${NC}"
}

logs() {
    journalctl -u "$SERVICE" --no-pager -n "${2:-50}" -f
}

upgrade() {
    if [ -z "${2:-}" ]; then
        echo "Usage: sip-reporter upgrade --tag vX.Y.Z"
        echo "       sip-reporter upgrade --url https://..."
        exit 1
    fi

    case "$2" in
        --tag)
            TAG="${3:?Missing tag}"
            URL="https://github.com/brianwynne/rtesip/releases/download/${TAG}/sip-reporter-${TAG}-noarch.tar.gz"
            ;;
        --url)
            URL="${3:?Missing URL}"
            ;;
        *)
            echo "Unknown option: $2"
            exit 1
            ;;
    esac

    echo -e "${CYAN}Downloading: ${URL}${NC}"
    TMPDIR=$(mktemp -d)
    curl -fsSL -o "$TMPDIR/bundle.tar.gz" "$URL"

    echo "Extracting..."
    tar xzf "$TMPDIR/bundle.tar.gz" -C "$TMPDIR"

    echo "Installing..."
    cd "$TMPDIR"
    bash deploy/install.sh --local "$TMPDIR"

    rm -rf "$TMPDIR"
    echo -e "${GREEN}Upgrade complete${NC}"
    version
}

uninstall() {
    echo -e "${RED}This will uninstall SIP Reporter${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl stop "$SERVICE" 2>/dev/null || true
        systemctl disable "$SERVICE" 2>/dev/null || true
        rm -f "/etc/systemd/system/${SERVICE}.service"
        systemctl daemon-reload

        rm -rf "$INSTALL_DIR"
        echo -e "${YELLOW}Code removed${NC}"

        read -p "Remove config ($CONFIG_DIR)? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && rm -rf "$CONFIG_DIR" && echo "Config removed"

        read -p "Remove data ($DATA_DIR)? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && rm -rf "$DATA_DIR" && echo "Data removed"

        read -p "Remove logs ($LOG_DIR)? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && rm -rf "$LOG_DIR" && echo "Logs removed"

        read -p "Remove system user 'rtesip'? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && userdel rtesip 2>/dev/null && echo "User removed"

        rm -f /usr/local/bin/sip-reporter
        echo -e "${GREEN}Uninstall complete${NC}"
    else
        echo "Cancelled"
    fi
}

set-password() {
    if [ -z "${2:-}" ]; then
        read -sp "New GUI password: " PASS
        echo
    else
        PASS="$2"
    fi
    HASH=$(echo -n "$PASS" | sha256sum | cut -d' ' -f1)
    python3 -c "
import json, os
path = '$DATA_DIR/config.json'
if os.path.exists(path):
    with open(path) as f: cfg = json.load(f)
else:
    cfg = {}
cfg.setdefault('security', {})['gui_password_hash'] = '$HASH'
with open(path + '.tmp', 'w') as f: json.dump(cfg, f, indent=2)
os.replace(path + '.tmp', path)
print('Password updated')
"
}

usage() {
    version
    echo ""
    echo "Usage: sip-reporter <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status              Show service status"
    echo "  start               Start the service"
    echo "  stop                Stop the service"
    echo "  restart             Restart the service"
    echo "  logs [N]            Follow journal logs (last N lines, default 50)"
    echo "  version             Show version"
    echo "  upgrade --tag TAG   Upgrade to a release tag"
    echo "  upgrade --url URL   Upgrade from a bundle URL"
    echo "  set-password [PW]   Set the GUI password"
    echo "  uninstall           Uninstall SIP Reporter"
    echo ""
}

# Require root for most commands
case "${1:-}" in
    version|--version|-v) version ;;
    status) status ;;
    logs) logs "$@" ;;
    --help|-h|"") usage ;;
    *)
        if [ "$(id -u)" -ne 0 ]; then
            echo -e "${RED}Error: 'sip-reporter $1' requires root. Use sudo.${NC}"
            exit 1
        fi
        case "$1" in
            start) start ;;
            stop) stop ;;
            restart) restart ;;
            upgrade) upgrade "$@" ;;
            uninstall) uninstall ;;
            set-password) set-password "$@" ;;
            *) echo "Unknown command: $1"; usage; exit 1 ;;
        esac
        ;;
esac
