# SIP Reporter — UDP Media Relay Design

## Revision History
| Date | Author | Notes |
|------|--------|-------|
| 2026-04-03 | Brian Wynne / Claude | Initial design |

## 1. Problem Statement

Standard rtpengine cannot send RTP to multiple destinations or intelligently
handle RTP arriving from multiple source addresses. We need a lightweight
UDP relay that sits between rtpengine and the Pi, managing dual-path
media delivery.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Raspberry Pi                                                     │
│                                                                   │
│  pjsua ──RTP──► nftables dup ──► eth0 ──┐                       │
│                               └──► wlan0 ─┤                      │
│                                           │                      │
│  pjsua ◄──RTP── kernel ◄── (either) ◄────┤                      │
│                                           │                      │
│  SIP REG #1 via eth0 (reg-id=1)          │                      │
│  SIP REG #2 via wlan0 (reg-id=2)        │                      │
└───────────────────────────────────────────┤──────────────────────┘
                                            │
                              Internet (two paths)
                                            │
┌───────────────────────────────────────────┤──────────────────────┐
│ AWS Server                                │                      │
│                                           │                      │
│  ┌────────────────────────────────────────▼────────────────┐    │
│  │ UDP Media Relay (rtesip-relay)                           │    │
│  │                                                          │    │
│  │  External side:                                          │    │
│  │    Port 20000-20100 ◄──► Pi (eth0 path + wlan0 path)   │    │
│  │    - Receives RTP from both Pi public IPs               │    │
│  │    - Deduplicates (RTP sequence number)                 │    │
│  │    - Sends return RTP to ALL known Pi addresses          │    │
│  │    - Tracks path liveness via packet recency             │    │
│  │                                                          │    │
│  │  Internal side:                                          │    │
│  │    Port 30000-30100 ◄──► rtpengine                      │    │
│  │    - Appears as a single endpoint to rtpengine           │    │
│  │    - Forwards deduplicated RTP to rtpengine              │    │
│  │    - Receives return RTP from rtpengine                  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                         ▲                                        │
│                         │ localhost UDP                           │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ rtpengine                                                │    │
│  │   Sees relay as a single endpoint                        │    │
│  │   Normal operation — no media-handover needed            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                         ▲                                        │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Kamailio                                                  │    │
│  │   RFC 5626 dual registration                              │    │
│  │   SDP rewrite: relay port instead of rtpengine port       │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Relay Design

### 3.1 Core Concept

The relay is a **per-call UDP port pair** that sits between rtpengine and
the Pi. For each active call:

```
Pi (eth0)  ──► relay external port ──► relay internal port ──► rtpengine
Pi (wlan0) ──► relay external port ──┘

rtpengine ──► relay internal port ──► relay external port ──► Pi (eth0)
                                                          └──► Pi (wlan0)
```

### 3.2 External Side (Pi-facing)

**Receives from Pi:**
- Listens on a UDP port (e.g. 20000)
- Accepts RTP packets from ANY source IP (no address filtering)
- Maintains a table of known Pi addresses (learned from incoming packets)
- Deduplicates by RTP sequence number (16-bit, wrapping)
- Forwards unique packets to rtpengine via the internal port

**Sends to Pi:**
- When rtpengine sends return RTP, relay receives on the internal port
- Relay sends a copy to EVERY known Pi address
- Pi receives on whichever interface is up
- Pi's jitter buffer discards duplicates

**Path tracking:**
```python
paths = {
    ("109.78.77.16", 54321): {"last_seen": time.time(), "packets": 1523},
    ("82.12.34.56", 12345):  {"last_seen": time.time(), "packets": 1520},
}
```

- Path added when first packet received from a new source
- Path removed after 30 seconds of silence (source died)
- All active paths receive return RTP

### 3.3 Internal Side (rtpengine-facing)

**To rtpengine:**
- Sends deduplicated RTP to rtpengine's media port
- Uses a fixed source port (relay's internal port)
- rtpengine sees ONE source — no media-handover needed
- rtpengine's endpoint learning locks to the relay's address

**From rtpengine:**
- Receives return RTP from rtpengine
- Forwards to all known Pi paths (via external port)

### 3.4 Deduplication Logic

```python
class RTPDeduplicator:
    def __init__(self, window_size=1000):
        self.seen = collections.OrderedDict()  # seq_num → timestamp
        self.window_size = window_size

    def is_duplicate(self, packet: bytes) -> bool:
        # RTP sequence number is bytes 2-3 (big-endian uint16)
        seq = int.from_bytes(packet[2:4], 'big')

        if seq in self.seen:
            return True  # Already forwarded this packet

        self.seen[seq] = time.time()

        # Trim old entries (sliding window)
        while len(self.seen) > self.window_size:
            self.seen.popitem(last=False)

        return False
```

### 3.5 Call Lifecycle

**Call setup:**
1. Pi sends INVITE → Kamailio receives
2. Kamailio allocates a relay port pair (external + internal)
3. Kamailio rewrites SDP: replaces rtpengine's port with relay's external port
4. Kamailio calls rtpengine_offer with relay's internal port as the endpoint
5. Call established: Pi ↔ relay ↔ rtpengine ↔ remote party

**Mid-call:**
- Relay passively forwards, deduplicates, and multi-sends
- No SIP awareness needed — pure UDP forwarding

**Call teardown:**
- Kamailio receives BYE → releases relay port pair
- Or: relay detects 30 seconds of silence → releases automatically

## 4. Implementation

### 4.1 Relay Process (Python, asyncio)

```python
"""rtesip-relay — UDP media relay for dual-path failover.

Runs on the Kamailio/rtpengine server. Manages per-call UDP port pairs
that bridge between multiple Pi network paths and rtpengine.
"""

import asyncio
import collections
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

EXTERNAL_PORT_BASE = 20000  # Pi-facing ports
INTERNAL_PORT_BASE = 20500  # rtpengine-facing ports
PATH_TIMEOUT = 30           # seconds before declaring path dead
CALL_TIMEOUT = 300          # seconds of silence before releasing call


@dataclass
class Path:
    addr: tuple  # (ip, port)
    last_seen: float = 0
    packet_count: int = 0


@dataclass
class CallRelay:
    call_id: str
    external_port: int
    internal_port: int
    external_transport: asyncio.DatagramTransport | None = None
    internal_transport: asyncio.DatagramTransport | None = None
    rtpengine_addr: tuple | None = None  # (ip, port) — learned from first packet
    paths: dict = field(default_factory=dict)  # addr_tuple → Path
    dedup: collections.OrderedDict = field(default_factory=collections.OrderedDict)
    last_activity: float = 0

    def is_duplicate(self, packet: bytes) -> bool:
        """Check RTP sequence number for deduplication."""
        if len(packet) < 4:
            return False
        seq = int.from_bytes(packet[2:4], 'big')
        if seq in self.dedup:
            return True
        self.dedup[seq] = True
        while len(self.dedup) > 1000:
            self.dedup.popitem(last=False)
        return False

    def active_paths(self) -> list[tuple]:
        """Return addresses of paths seen within PATH_TIMEOUT."""
        now = time.time()
        return [p.addr for p in self.paths.values()
                if now - p.last_seen < PATH_TIMEOUT]


class ExternalProtocol(asyncio.DatagramProtocol):
    """Receives RTP from Pi (multiple paths), forwards to rtpengine."""

    def __init__(self, call: CallRelay):
        self.call = call

    def datagram_received(self, data: bytes, addr: tuple):
        now = time.time()
        self.call.last_activity = now

        # Track this path
        addr_key = addr
        if addr_key not in self.call.paths:
            logger.info("Call %s: new path discovered %s:%d",
                        self.call.call_id, addr[0], addr[1])
            self.call.paths[addr_key] = Path(addr=addr)
        self.call.paths[addr_key].last_seen = now
        self.call.paths[addr_key].packet_count += 1

        # Deduplicate
        if self.call.is_duplicate(data):
            return  # Already forwarded this sequence number

        # Forward to rtpengine
        if self.call.internal_transport and self.call.rtpengine_addr:
            self.call.internal_transport.sendto(data, self.call.rtpengine_addr)


class InternalProtocol(asyncio.DatagramProtocol):
    """Receives RTP from rtpengine, sends to ALL known Pi paths."""

    def __init__(self, call: CallRelay):
        self.call = call

    def datagram_received(self, data: bytes, addr: tuple):
        self.call.last_activity = time.time()

        # Learn rtpengine's address from first packet
        if self.call.rtpengine_addr is None:
            self.call.rtpengine_addr = addr
            logger.info("Call %s: rtpengine at %s:%d",
                        self.call.call_id, addr[0], addr[1])

        # Send to ALL active Pi paths
        paths = self.call.active_paths()
        for path_addr in paths:
            self.call.external_transport.sendto(data, path_addr)


class MediaRelay:
    """Manages per-call relay port pairs."""

    def __init__(self):
        self.calls: dict[str, CallRelay] = {}
        self._next_port = 0

    async def create_call(self, call_id: str) -> tuple[int, int]:
        """Allocate a relay port pair for a new call.

        Returns (external_port, internal_port).
        """
        ext_port = EXTERNAL_PORT_BASE + self._next_port * 2
        int_port = INTERNAL_PORT_BASE + self._next_port * 2
        self._next_port = (self._next_port + 1) % 50  # max 50 concurrent calls

        call = CallRelay(
            call_id=call_id,
            external_port=ext_port,
            internal_port=int_port,
        )

        loop = asyncio.get_event_loop()

        # Create external socket (Pi-facing)
        ext_transport, _ = await loop.create_datagram_endpoint(
            lambda: ExternalProtocol(call),
            local_addr=('0.0.0.0', ext_port),
        )
        call.external_transport = ext_transport

        # Create internal socket (rtpengine-facing)
        int_transport, _ = await loop.create_datagram_endpoint(
            lambda: InternalProtocol(call),
            local_addr=('127.0.0.1', int_port),
        )
        call.internal_transport = int_transport

        self.calls[call_id] = call
        logger.info("Call %s: relay created ext=%d int=%d",
                     call_id, ext_port, int_port)
        return ext_port, int_port

    async def destroy_call(self, call_id: str):
        """Release a relay port pair."""
        call = self.calls.pop(call_id, None)
        if call:
            if call.external_transport:
                call.external_transport.close()
            if call.internal_transport:
                call.internal_transport.close()
            logger.info("Call %s: relay destroyed", call_id)

    async def cleanup_loop(self):
        """Periodically clean up stale calls."""
        while True:
            await asyncio.sleep(60)
            now = time.time()
            stale = [cid for cid, c in self.calls.items()
                     if now - c.last_activity > CALL_TIMEOUT]
            for cid in stale:
                logger.warning("Call %s: stale, cleaning up", cid)
                await self.destroy_call(cid)


# --- HTTP API for Kamailio integration ---

from aiohttp import web

relay = MediaRelay()

async def handle_create(request: web.Request) -> web.Response:
    """POST /relay/create {"call_id": "xxx"}

    Returns {"external_port": N, "internal_port": N}
    """
    data = await request.json()
    call_id = data["call_id"]
    ext_port, int_port = await relay.create_call(call_id)
    return web.json_response({
        "external_port": ext_port,
        "internal_port": int_port,
    })

async def handle_destroy(request: web.Request) -> web.Response:
    """POST /relay/destroy {"call_id": "xxx"}"""
    data = await request.json()
    await relay.destroy_call(data["call_id"])
    return web.json_response({"status": "ok"})

async def handle_status(request: web.Request) -> web.Response:
    """GET /relay/status"""
    calls = {}
    for cid, call in relay.calls.items():
        calls[cid] = {
            "external_port": call.external_port,
            "internal_port": call.internal_port,
            "paths": [
                {"addr": f"{p.addr[0]}:{p.addr[1]}",
                 "last_seen": p.last_seen,
                 "packets": p.packet_count}
                for p in call.paths.values()
            ],
            "rtpengine_addr": f"{call.rtpengine_addr[0]}:{call.rtpengine_addr[1]}"
                              if call.rtpengine_addr else None,
        }
    return web.json_response({"calls": calls})


async def start_relay():
    """Start the relay service."""
    app = web.Application()
    app.router.add_post("/relay/create", handle_create)
    app.router.add_post("/relay/destroy", handle_destroy)
    app.router.add_get("/relay/status", handle_status)

    asyncio.create_task(relay.cleanup_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8090)
    await site.start()
    logger.info("Media relay API listening on 127.0.0.1:8090")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(start_relay())
    loop.run_forever()
```

### 4.2 Kamailio Integration

Kamailio needs to:
1. On INVITE: call relay API to allocate port pair
2. Rewrite SDP to use relay's external port (instead of rtpengine directly)
3. Call rtpengine_offer/answer with relay's internal port
4. On BYE: call relay API to release port pair

**Kamailio route additions:**
```
# On INVITE — allocate relay
route[RELAY_ALLOC] {
    $var(call_id) = $ci;

    # HTTP request to relay API
    http_client_query(
        "http://127.0.0.1:8090/relay/create",
        "{\"call_id\": \"$ci\"}",
        "$var(relay_response)"
    );

    # Parse response for ports
    jansson_get("external_port", $var(relay_response), "$var(ext_port)");
    jansson_get("internal_port", $var(relay_response), "$var(int_port)");

    # Store for SDP rewriting
    $dlg_var(relay_ext_port) = $var(ext_port);
    $dlg_var(relay_int_port) = $var(int_port);
}

# On BYE — release relay
route[RELAY_FREE] {
    http_client_query(
        "http://127.0.0.1:8090/relay/destroy",
        "{\"call_id\": \"$ci\"}",
        "$var(relay_response)"
    );
}
```

### 4.3 SDP Rewriting

The SDP in the INVITE/200OK needs the relay's external IP:port instead
of rtpengine's. This can be done via Kamailio's sdpops module:

```
# After rtpengine_offer, replace media port with relay external port
subst_body("/m=audio [0-9]+ /m=audio $var(ext_port) /");
subst_body("/c=IN IP4 [0-9.]+ /c=IN IP4 54.220.131.205 /");
```

Or better: configure rtpengine to use the relay's internal port range,
and let the relay handle external addressing.

### 4.4 Pi-Side: nftables Duplication

Same as the previous design — duplicate outgoing RTP to both interfaces:
```bash
nft add rule ip rtesip_failover postrouting \
  ip protocol udp \
  ip daddr <server_ip> \
  udp dport { 20000-20100 } \
  oif eth0 \
  dup to <server_ip> device wlan0
```

The destination port range changes to the relay's external ports (20000-20100)
instead of rtpengine's ports (30000-40000).

## 5. Packet Flow — Normal Operation

```
Pi pjsua sends RTP packet (seq=100):
  │
  ├─► eth0 → NAT → 109.78.77.16:X → Relay external port 20000
  │     Relay: new packet seq=100 from 109.78.77.16:X
  │     Relay: forward to rtpengine (127.0.0.1:30000)
  │     Relay: paths = {109.78.77.16:X, 82.12.34.56:Y}
  │
  └─► wlan0 (dup) → NAT → 82.12.34.56:Y → Relay external port 20000
        Relay: duplicate seq=100 from 82.12.34.56:Y
        Relay: DISCARD (already forwarded)

rtpengine sends return RTP:
  │
  └─► 127.0.0.1:30000 → Relay internal port
        Relay: send to ALL active paths:
          → 109.78.77.16:X (eth0 path)
          → 82.12.34.56:Y  (wlan0 path)

Pi receives:
  eth0: return RTP (seq=200) → pjsua
  wlan0: return RTP (seq=200, duplicate) → pjsua DISCARDS
```

## 6. Packet Flow — Eth0 Failover

```
T=0:    eth0 cable pulled
T=0:    Pi pjsua sends RTP (seq=500):
          eth0 → FAILS (interface down, packet dropped)
          wlan0 (dup) → 82.12.34.56:Y → Relay
            Relay: packet seq=500 from 82.12.34.56:Y
            Relay: forward to rtpengine ✓

T=0:    Relay sends return RTP to both paths:
          → 109.78.77.16:X (eth0) — packet reaches router but Pi can't receive
          → 82.12.34.56:Y (wlan0) — Pi receives ✓

T=30s:  Relay: path 109.78.77.16:X not seen for 30s → removed
        Relay now sends return RTP to wlan0 only (saves bandwidth)

Audio gap: ZERO — wlan0 was already carrying traffic in both directions
```

## 7. Packet Flow — Wlan0 Failover

```
T=0:    WiFi disconnects
T=0:    Pi pjsua sends RTP (seq=500):
          eth0 → 109.78.77.16:X → Relay ✓
          wlan0 (dup) → FAILS (interface down)

T=0:    Relay sends return RTP to both paths:
          → 109.78.77.16:X (eth0) — Pi receives ✓
          → 82.12.34.56:Y (wlan0) — packet dropped by ISP/router

T=30s:  Relay: path 82.12.34.56:Y removed

Audio gap: ZERO — eth0 was already carrying traffic in both directions
```

## 8. Technical Analysis

### 8.1 Does the relay solve the return-path oscillation problem?

**YES.** rtpengine only sees the relay (127.0.0.1). It never sees the Pi's
dual addresses. The relay handles the multi-path complexity. rtpengine's
endpoint learning is not involved. No media-handover flag needed.

### 8.2 How does the relay learn Pi's addresses?

**Passively**, from incoming packets. When the Pi sends RTP via eth0, the
relay sees source 109.78.77.16:X. When the duplicate arrives via wlan0,
it sees 82.12.34.56:Y. Both are stored as active paths.

No registration, no API call from the Pi, no configuration. The relay
auto-discovers paths from traffic.

### 8.3 What about NAT pinholes?

The relay sends to both Pi addresses. These outgoing packets keep the NAT
pinholes open on both routers. As long as the relay sends at least one
packet per NAT timeout (typically 30-60 seconds), the pinholes stay open.

Since the relay sends EVERY return RTP packet to both paths (~50 packets/sec),
NAT pinholes are continuously refreshed. ✓

### 8.4 What about RTP SSRC?

The relay doesn't modify packets. The SSRC from pjsua is preserved through
the relay to rtpengine and vice versa. The remote party sees one consistent
SSRC regardless of which Pi path delivered the packet. ✓

### 8.5 What about RTCP?

RTCP packets use RTP port + 1. The relay should handle RTCP the same way —
forward deduplicated, send return to all paths. The dedup uses RTP sequence
numbers which RTCP doesn't have, so RTCP packets are always forwarded
(low volume — ~1 per 5 seconds). ✓

### 8.6 What about SRTP?

SRTP encryption is end-to-end between pjsua and the remote party. The relay
and rtpengine handle encrypted packets opaquely. SRTP keys are negotiated
in the SDP — the relay doesn't need to know them.

However: rtpengine with SRTP (`RTP/SAVP`) decrypts/re-encrypts. The relay
sits between pjsua and rtpengine, so:
- pjsua → relay → rtpengine: SRTP encrypted (pjsua's keys)
- rtpengine → relay → pjsua: SRTP encrypted (pjsua's keys)

The relay never decrypts. It just forwards bytes. ✓

### 8.7 Bandwidth overhead

**Upstream (Pi → Server):** Doubles (sending via both interfaces).
- 64 kbps Opus CBR + headers ≈ 80 kbps × 2 paths = 160 kbps total upload

**Downstream (Server → Pi):** Doubles (relay sends to both Pi addresses).
- 80 kbps × 2 paths = 160 kbps total download across both interfaces
- Each interface receives 80 kbps

**Server bandwidth:** Additional 80 kbps download (duplicate Pi packets,
only one forwarded to rtpengine) + 80 kbps upload (duplicate return to Pi).

**Total overhead:** ~160 kbps additional per call. Negligible. ✓

### 8.8 Latency

**Added latency:** One UDP hop on localhost (relay ↔ rtpengine).
- Localhost UDP: <0.1ms
- Total added: <0.2ms round-trip

Negligible compared to network latency (~20-50ms). ✓

### 8.9 Relay failure

If the relay process crashes:
- All RTP stops (both directions)
- Kamailio/SIP signalling still works
- Calls drop (no media)
- Relay auto-restart via systemd

**Mitigation:** Run relay with `Restart=always` in systemd. Relay restart
takes <1 second. Calls in progress drop, new calls work immediately.

### 8.10 Port allocation and scalability

- 50 port pairs (20000-20099 external, 20500-20599 internal)
- Supports 50 concurrent calls with failover
- Each call uses 2 UDP sockets (4 file descriptors)
- Memory: ~1KB per call
- CPU: negligible (UDP forwarding, no processing)

For a single Pi codec, 50 concurrent calls is far more than needed (max 1).
But the relay can serve multiple Pi devices simultaneously. ✓

## 9. Deployment

### 9.1 Server-side (AWS Kamailio server)

```bash
# Install as systemd service
sudo cp rtesip-relay.py /opt/rtesip-relay/
sudo cp rtesip-relay.service /etc/systemd/system/

# Open firewall for relay external ports
# AWS security group: allow UDP 20000-20100 inbound

# Start
sudo systemctl enable rtesip-relay
sudo systemctl start rtesip-relay
```

### 9.2 Pi-side

- nftables rules to duplicate outgoing RTP (destination port 20000-20100)
- SNAT for wlan0 copies
- Managed by failover_manager.py when dual_path_failover is enabled

### 9.3 Kamailio changes

- Load http_client and jansson modules
- Add relay allocation/deallocation routes
- SDP rewriting to use relay ports

## 10. Comparison with Previous Design

| Aspect | nftables dup + media-handover | UDP relay (this design) |
|--------|------------------------------|------------------------|
| Return path | Oscillates (wrong interface) | Correct (both paths) |
| rtpengine changes | media-handover flag | None |
| Server component | None | Relay process |
| Failover gap | 20-40ms | Zero |
| Complexity | Low | Medium |
| SDP rewriting | None | Required |
| Kamailio changes | Minimal | HTTP API calls + SDP rewrite |
| Scalability | Per-device | Multi-device |

## 11. Open Questions

### 11.1 Kamailio SDP rewriting complexity
How complex is the SDP rewriting in Kamailio to use relay ports instead
of rtpengine ports? Need to verify sdpops module can handle this cleanly.

### 11.2 RTCP handling
RTCP port is conventionally RTP port + 1. The relay needs to allocate
port pairs (even=RTP, odd=RTCP) and handle both. Verify this works with
rtpengine's RTCP handling.

### 11.3 Call-ID correlation
The relay uses Call-ID from SIP to match calls. Kamailio must pass the
correct Call-ID to the relay API. Verify this is consistent through
forking and re-INVITE scenarios.

### 11.4 ICE interaction
If ICE is enabled, ICE candidates may reference rtpengine's ports.
The SDP rewriting must update ICE candidates to use relay ports.
Consider disabling ICE when relay is active.

### 11.5 Integration testing
Full end-to-end test: Pi with dual interfaces → relay → rtpengine →
remote party. Pull ethernet cable during call. Verify zero audio gap.
