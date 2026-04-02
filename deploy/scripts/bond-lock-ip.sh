#!/bin/bash
# Lock the DHCP-assigned IP as static on bond0.
# Run after bond0 gets its DHCP lease so the IP persists through failover
# (fail_over_mac=active changes MAC, which would get a new DHCP lease).

BOND="bond0"

# Only run if bond exists
if ! ip link show "$BOND" &>/dev/null; then
    exit 0
fi

# Wait for DHCP lease (up to 30s)
for i in $(seq 1 30); do
    IP=$(ip -4 addr show "$BOND" | grep -oP 'inet \K[\d.]+/\d+')
    if [ -n "$IP" ]; then
        break
    fi
    sleep 1
done

if [ -z "$IP" ]; then
    echo "bond-lock-ip: No IP on $BOND after 30s, skipping"
    exit 0
fi

# Get gateway
GW=$(ip route show dev "$BOND" | grep default | awk '{print $3}')
if [ -z "$GW" ]; then
    GW="192.168.1.1"
fi

# Check if already static
METHOD=$(nmcli -t -f ipv4.method connection show "$BOND" | cut -d: -f2)
if [ "$METHOD" = "manual" ]; then
    echo "bond-lock-ip: Already static ($IP), skipping"
    exit 0
fi

# Lock as static
nmcli connection modify "$BOND" \
    ipv4.method manual \
    ipv4.addresses "$IP" \
    ipv4.gateway "$GW" \
    ipv4.dns "8.8.8.8 8.8.4.4"

# Apply without recycling bond
ip addr flush dev "$BOND"
ip addr add "$IP" dev "$BOND"
ip route add default via "$GW" dev "$BOND" 2>/dev/null

echo "bond-lock-ip: Locked $IP (gw $GW) as static on $BOND"
