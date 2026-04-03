#!/bin/bash
# Apply RFC 5626 outbound support to Kamailio config
# Run on the Kamailio server: sudo bash apply-outbound.sh
set -euo pipefail

CFG="/etc/kamailio/kamailio.cfg"
BACKUP="$CFG.bak.$(date +%Y%m%d-%H%M%S)"

if [[ ! -f "$CFG" ]]; then
    echo "ERROR: $CFG not found"
    exit 1
fi

echo "Backing up to $BACKUP"
cp "$CFG" "$BACKUP"

# Check if outbound is already configured
if grep -q "outbound.so" "$CFG"; then
    echo "outbound.so already loaded — skipping module load"
else
    echo "Adding outbound.so and path.so modules..."
    # Insert after the last loadmodule line
    LAST_LOADMODULE=$(grep -n "^loadmodule" "$CFG" | tail -1 | cut -d: -f1)
    sed -i "${LAST_LOADMODULE}a\\
loadmodule \"outbound.so\"\\
loadmodule \"path.so\"" "$CFG"
fi

# Add/update registrar parameters
echo "Updating registrar parameters..."

# outbound_mode
if grep -q 'modparam("registrar", "outbound_mode"' "$CFG"; then
    sed -i 's/modparam("registrar", "outbound_mode".*$/modparam("registrar", "outbound_mode", 1)/' "$CFG"
else
    sed -i '/modparam("registrar", "max_contacts"/a modparam("registrar", "outbound_mode", 1)' "$CFG"
fi

# flow_timer
if grep -q 'modparam("registrar", "flow_timer"' "$CFG"; then
    sed -i 's/modparam("registrar", "flow_timer".*$/modparam("registrar", "flow_timer", 30)/' "$CFG"
else
    sed -i '/modparam("registrar", "outbound_mode"/a modparam("registrar", "flow_timer", 30)' "$CFG"
fi

# max_contacts — increase to 4 for 2 devices × 2 flows
if grep -q 'modparam("registrar", "max_contacts"' "$CFG"; then
    sed -i 's/modparam("registrar", "max_contacts".*$/modparam("registrar", "max_contacts", 4)/' "$CFG"
fi

# use_path
if ! grep -q 'modparam("registrar", "use_path"' "$CFG"; then
    sed -i '/modparam("registrar", "flow_timer"/a modparam("registrar", "use_path", 1)' "$CFG"
fi

# gruu
if ! grep -q 'modparam("registrar", "gruu_enabled"' "$CFG"; then
    sed -i '/modparam("registrar", "use_path"/a modparam("registrar", "gruu_enabled", 1)' "$CFG"
fi

# path module param
if ! grep -q 'modparam("path"' "$CFG"; then
    sed -i '/modparam("registrar", "gruu_enabled"/a modparam("path", "use_received", 1)' "$CFG"
fi

# usrloc desc_time_order
if ! grep -q 'desc_time_order' "$CFG"; then
    sed -i '/modparam("usrloc", "db_mode"/a modparam("usrloc", "desc_time_order", 1)' "$CFG"
fi

echo ""
echo "Validating config..."
if kamailio -c "$CFG" 2>&1 | grep -q "config file ok"; then
    echo "Config validation: OK"
    echo ""
    echo "Ready to apply. Run:"
    echo "  sudo systemctl reload kamailio"
    echo ""
    echo "Then verify with:"
    echo "  mysql -u kamailio -p877807 kamailio -e \"SELECT username, contact, reg_id, instance FROM location WHERE username='tieline1'\""
else
    echo "ERROR: Config validation failed!"
    echo "Restoring backup..."
    cp "$BACKUP" "$CFG"
    echo "Original config restored."
    exit 1
fi
