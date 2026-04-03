# Kamailio Configuration for SIP Reporter Multi-Path Failover

These patches enable RFC 5626 (SIP Outbound) multi-flow registration on
the Kamailio server at `sip.rtegroup.ie`. This allows SIP Reporter devices
to register from two interfaces simultaneously (e.g. ethernet + WiFi) and
Kamailio will automatically fail over signalling if one path dies.

## Prerequisites

- Kamailio 5.8+ with `outbound` module available
- Existing working config at `/etc/kamailio/kamailio.cfg`
- MariaDB usrloc backend (`db_mode=3`)

## Apply

```bash
# Backup existing config
sudo cp /etc/kamailio/kamailio.cfg /etc/kamailio/kamailio.cfg.bak

# Apply the changes described in kamailio-outbound.conf
# (manual merge — not a drop-in replacement)

# Reload
sudo systemctl reload kamailio
```

## What it does

1. Loads the `outbound` module
2. Enables RFC 5626 in the registrar (`outbound_mode=1`)
3. Sets `flow_timer=30` for NAT keepalive
4. Enables path support for multi-hop routing
5. Adds failure route for serial forking to backup flow on INVITE timeout
