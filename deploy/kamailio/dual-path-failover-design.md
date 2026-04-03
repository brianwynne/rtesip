# SIP Reporter — Dual-Path Seamless Failover Design

## Revision History
| Date | Author | Notes |
|------|--------|-------|
| 2026-04-03 | Brian Wynne / Claude | Initial design |

## 1. Problem Statement

A broadcast SIP codec deployed in the field needs seamless audio failover
between ethernet and WiFi interfaces. The interfaces may be on different
subnets with different public IPs. Any audio interruption during failover
must be minimised to zero or near-zero.

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│ Raspberry Pi (SIP Reporter)                                   │
│                                                                │
│  pjsua ──RTP──► kernel ──► nftables dup ──► eth0 ──► Internet │
│                                         └──► wlan0 ──► Internet│
│                                               (duplicate)      │
│                                                                │
│  pjsua ◄──RTP── kernel ◄── (either interface) ◄── Internet    │
│                                                                │
│  SIP REGISTER #1 via eth0  (reg-id=1, +sip.instance=X)       │
│  SIP REGISTER #2 via wlan0 (reg-id=2, +sip.instance=X)       │
└──────────────────────────────────────────────────────────────┘
                           │                │
                     eth0 path         wlan0 path
                     (primary)         (backup)
                           │                │
                           ▼                ▼
┌──────────────────────────────────────────────────────────────┐
│ Kamailio + rtpengine (AWS)                                    │
│                                                                │
│  Kamailio:                                                     │
│    - RFC 5626 outbound: stores both flows for same user       │
│    - INVITE routing: try flow 1, failover to flow 2           │
│                                                                │
│  rtpengine:                                                    │
│    - media-handover flag: accepts RTP source address changes  │
│    - Receives RTP from EITHER Pi IP, forwards to remote party │
│    - Sends return RTP to whichever Pi IP sent most recently   │
└──────────────────────────────────────────────────────────────┘
```

## 3. Component Design

### 3.1 Outgoing RTP (Pi → Server): nftables Packet Duplication

**Mechanism:** The Linux kernel's nftables `dup` statement duplicates every
outgoing RTP packet and sends a copy via the secondary interface. The
original packet exits via the primary interface's normal routing.

**Rules:**
```bash
# Table for RTP duplication
nft add table ip rtesip_failover
nft add chain ip rtesip_failover postrouting { type filter hook postrouting priority mangle \; }

# Duplicate outgoing RTP (port range 30000-40000 = rtpengine range) to wlan0
nft add rule ip rtesip_failover postrouting \
  ip protocol udp \
  udp dport { 30000-40000 } \
  oif eth0 \
  dup to <server_ip> device wlan0

# SNAT the wlan0 copy to use wlan0's source IP
nft add table ip rtesip_nat
nft add chain ip rtesip_nat postrouting { type nat hook postrouting priority srcnat \; }
nft add rule ip rtesip_nat postrouting \
  oif wlan0 \
  ip protocol udp \
  udp dport { 30000-40000 } \
  snat to <wlan0_ip>
```

**Packet flow:**
```
pjsua sends RTP packet (src=eth0_ip, dst=server_ip, dport=rtpengine_port)
  │
  ├─► Original: exits via eth0 (normal routing) → Server
  │     src = eth0_ip (NAT'd to eth0_public_ip by router)
  │
  └─► Duplicate: nftables dup → exits via wlan0 → SNAT to wlan0_ip → Server
        src = wlan0_ip (NAT'd to wlan0_public_ip by router)

Server (rtpengine) receives BOTH packets:
  - Same RTP payload, sequence number, SSRC
  - Different source IPs
  - With media-handover: accepts both, uses most recent for return path
```

### 3.2 Incoming RTP (Server → Pi): Source Address Tracking

**Mechanism:** rtpengine sends return RTP to whichever source IP it most
recently received a packet from. Since the Pi sends via both interfaces,
rtpengine always has an up-to-date source address.

**Normal operation (both interfaces up):**
```
rtpengine receives RTP from eth0_public_ip (packet N)
rtpengine receives RTP from wlan0_public_ip (packet N, duplicate)
rtpengine sends return RTP to wlan0_public_ip (most recent)
  → arrives at Pi via wlan0
```

**After eth0 failure:**
```
rtpengine receives RTP from wlan0_public_ip ONLY
rtpengine sends return RTP to wlan0_public_ip
  → arrives at Pi via wlan0 (no change)
```

**After wlan0 failure:**
```
rtpengine receives RTP from eth0_public_ip ONLY
rtpengine sends return RTP to eth0_public_ip
  → arrives at Pi via eth0 (no change)
```

### 3.3 SIP Signalling: RFC 5626 Dual Flows

**Mechanism:** pjsua registers the same account twice — once per interface —
with the same `+sip.instance` but different `reg-id` values. Kamailio
stores both flows and uses serial forking for incoming INVITEs.

**Already implemented** in `feature/wireguard-failover` branch:
- pjsua_app.c patch creates second TLS transport + cloned account
- Kamailio config enables outbound_mode=1, max_contacts=4

### 3.4 Failover Manager (Python, integrated in rtesip service)

**Responsibilities:**
- Detect available interfaces and their IPs on startup
- Apply nftables rules when dual-path failover is enabled
- Remove nftables rules when disabled
- Update rules if interface IPs change (DHCP renewal)
- Report interface status to UI via WebSocket

**No detection/switching logic needed** — the duplication is always active.

## 4. Detailed Technical Analysis

### 4.1 ANALYSIS: Will rtpengine accept RTP from two different source IPs?

**Concern:** rtpengine's endpoint learning locks to one source address after
~3 seconds. Will it drop packets from the second interface?

**Answer:** With `media-handover` flag, rtpengine re-learns the source address
on every received packet. It will accept packets from both IPs and use the
most recent for return traffic.

**Risk:** The `media-handover` flag is documented as a security concern because
it allows RTP stream hijacking. However:
- Our calls use SRTP encryption — hijacked packets would fail SRTP authentication
- The flag is per-call, set during rtpengine_offer/answer in Kamailio
- Only our authenticated SIP users can establish calls

**Verdict:** Acceptable risk for broadcast use case. ✓

### 4.2 ANALYSIS: Will rtpengine handle duplicate packets correctly?

**Concern:** rtpengine receives the same RTP packet (same sequence number,
same SSRC) from two different source IPs within milliseconds. How does it
handle this?

**Answer:** rtpengine is a **media relay** — it forwards packets, it doesn't
decode them. It will forward BOTH copies to the remote party. The remote
party's jitter buffer (pjsua/Linphone/etc.) will receive duplicates and
discard them based on RTP sequence numbers.

**Potential issue:** The remote party's `dump_q` stats will show `dup=N`
(duplicate packets received). This is cosmetic — the audio is unaffected.
However, it doubles the bandwidth from rtpengine to the remote party.

**Mitigation:** rtpengine may have internal duplicate detection. If not,
the remote party handles it. Standard RTP behaviour per RFC 3550.

**Verdict:** Works, but doubles downstream bandwidth. ✓ with caveat.

### 4.3 ANALYSIS: Will nftables dup work with NAT?

**Concern:** The Pi is behind NAT on both interfaces. The `dup` statement
creates a copy with the original source IP (eth0's private IP). After SNAT
to wlan0's IP, will the packet be routable?

**Packet transformation:**
```
1. pjsua creates: src=192.168.1.30:port, dst=54.220.131.205:rtpport
2. nftables dup: creates copy, marks for wlan0
3. SNAT: changes src to 10.0.0.50:port (wlan0's IP)
4. wlan0 router NATs: changes src to 82.x.x.x:port (wlan0's public IP)
5. Server receives: src=82.x.x.x:port, dst=54.220.131.205:rtpport
```

**Critical question:** Does the Pi's wlan0 router accept and NAT outgoing
packets with source IP 10.0.0.50 (wlan0's IP) that didn't originate from
wlan0's socket?

**Answer:** Yes — the router performs source NAT based on the outgoing
interface, not the originating socket. The SNAT rule ensures the packet
has wlan0's private IP before it reaches the router, so the router treats
it as normal outgoing traffic.

**Verdict:** Works. ✓

### 4.4 ANALYSIS: Will pjsua's RTP socket conflict with the duplicated packets?

**Concern:** pjsua binds its RTP socket to a specific IP (eth0's IP). The
nftables `dup` creates a copy that goes via wlan0. Does this interfere
with pjsua's socket?

**Answer:** No. The dup happens AFTER pjsua has sent the packet. pjsua's
socket sends one packet via normal routing (eth0). nftables intercepts it
in the POSTROUTING chain, makes a copy, and sends the copy via wlan0.
pjsua never knows about the duplication. The original packet is unmodified.

**Verdict:** No conflict. ✓

### 4.5 ANALYSIS: What happens to return RTP when both interfaces are up?

**Concern:** rtpengine sends return RTP to whichever source it saw last.
With both interfaces sending simultaneously, rtpengine alternates between
them. Return RTP oscillates between eth0 and wlan0.

**Detailed scenario:**
```
T=0ms:   Pi sends via eth0 (arrives at server at T=20ms)
T=0ms:   Pi sends via wlan0 (arrives at server at T=25ms, 5ms slower)
         Server return RTP goes to wlan0_ip (most recent)

T=20ms:  Pi sends via eth0 (arrives at T=40ms)
T=20ms:  Pi sends via wlan0 (arrives at T=45ms)
         Server return RTP goes to wlan0_ip (most recent again)
```

**Observation:** Since wlan0 typically has higher latency than eth0, the
wlan0 packet arrives LATER and is always "most recent". Return RTP would
predominantly go to wlan0, not eth0.

**Is this a problem?** The return RTP arrives on wlan0 which may have
higher jitter than eth0. This is suboptimal — we'd prefer return traffic
on eth0 (lower latency, more stable).

**Mitigation options:**
1. Accept wlan0 return path — audio quality depends on WiFi quality
2. Add a small delay to the wlan0 duplicate (nftables doesn't support this natively)
3. Only send duplicates via wlan0 every Nth packet (reduces wlan0 "freshness")
4. Use rtpengine's learning behaviour — during the initial 3-second learning
   phase, only send via eth0. After learning locks to eth0, start duplicating
   via wlan0. Return traffic stays on eth0. When eth0 fails, wlan0 packets
   trigger media-handover.

**Option 4 is the cleanest.** During normal operation, return RTP flows via
eth0 (optimal path). The wlan0 duplicates keep the wlan0 NAT pinhole open
but arrive "late" so rtpengine doesn't switch to them.

**Actually, this depends on rtpengine's behaviour with media-handover:**
- Does it switch on EVERY packet from a new source? → return path oscillates (bad)
- Does it switch only when the current source goes silent? → return path stays stable (good)

**This needs empirical testing.** The rtpengine documentation doesn't specify
the exact media-handover behaviour with simultaneous dual sources.

**Verdict:** UNCERTAIN — needs testing. ⚠️

### 4.6 ANALYSIS: What about incoming RTP when eth0 fails?

**Scenario:** Return RTP was going to eth0_public_ip. Eth0 dies.

**With media-handover:**
```
T=0:     eth0 dies. Pi stops sending via eth0.
T=0:     Pi continues sending via wlan0 (dup rule still active, original fails silently)
T=20ms:  Server receives RTP from wlan0_ip only
T=20ms:  media-handover: server switches return RTP to wlan0_ip
T=40ms:  Return RTP arrives at Pi via wlan0
```

**Gap:** 20-40ms (1-2 RTP packets). Opus PLC covers this transparently.

**Verdict:** Near-seamless. ✓

### 4.7 ANALYSIS: What about SIP re-INVITE?

**Concern:** After failover, pjsua's SDP still contains the old IP. The SIP
session has the wrong Contact address. Does this matter?

**Answer:** For RTP: No. rtpengine handles media independently of SIP signalling.
The `media-handover` flag means rtpengine follows the actual packet source,
not the SDP.

For SIP: The SIP dialog (INVITE, BYE) uses the transport it was established on.
If eth0 dies, pjsua can't send BYE via eth0. This is where RFC 5626 helps —
Kamailio can reach the Pi via the wlan0 flow for in-dialog requests.

However, pjsua's SIP transport for the call is bound to eth0. If eth0 dies,
pjsua can't send any SIP messages for that call (hold, transfer, BYE).
The hangup timeout (5 seconds) would force-reset the call state.

**For a new call after failover:** RFC 5626 routes the INVITE via wlan0 flow.
pjsua answers on wlan0. New SDP has wlan0's IP. Everything works.

**Verdict:** Existing calls lose SIP control (can't hang up gracefully) but
audio continues. New calls work normally. Acceptable for broadcast. ✓

### 4.8 ANALYSIS: nftables rule management — what RTP ports to duplicate?

**Concern:** rtpengine uses ports 30000-40000. But pjsua's local RTP port
is allocated dynamically. We need to match the right packets.

**pjsua's RTP ports:** Configured via `rtp_cfg.port` (default 4000) with
range `rtp_cfg.port_range`. pjsua sends TO rtpengine's port range
(30000-40000 as destination port).

**Matching rule:** Match on destination port range 30000-40000 (rtpengine's
media ports) and outgoing interface eth0. This catches all RTP going to
rtpengine regardless of pjsua's local port.

**False positives:** Any UDP traffic to ports 30000-40000 would be duplicated.
In practice, only RTP goes to these ports on the rtpengine server. Non-RTP
traffic to other servers on these ports would also be duplicated — wasteful
but harmless.

**Better match:** Add destination IP match for the rtpengine server:
```
nft add rule ... ip daddr <server_ip> udp dport { 30000-40000 } ...
```

**Verdict:** Use destination IP + port range for precise matching. ✓

### 4.9 ANALYSIS: Bandwidth overhead

**Per-call bandwidth:**
| Direction | Without dup | With dup | Overhead |
|-----------|------------|---------|---------|
| Pi → Server (eth0) | 80 kbps | 80 kbps | 0% |
| Pi → Server (wlan0, dup) | 0 | 80 kbps | +80 kbps |
| Server → Pi | 80 kbps | 80 kbps | 0% |
| **Total upload** | **80 kbps** | **160 kbps** | **+100%** |

Upload bandwidth doubles. At 64 kbps Opus CBR + headers = ~80 kbps per
direction. Total upload becomes ~160 kbps. Trivial for any broadband
connection but worth noting for cellular/metered connections.

**Verdict:** Acceptable overhead. ✓

### 4.10 ANALYSIS: What if only one interface is available?

**Scenario:** Pi boots with only WiFi (no ethernet cable).

**Behaviour:**
- nftables dup rule references eth0 as match (`oif eth0`) — no packets match
- All RTP goes out wlan0 via normal routing
- No duplication, no overhead
- Single registration via wlan0

**When ethernet is later plugged in:**
- nftables rules need to be updated (failover manager detects new interface)
- Second registration sent via eth0
- Duplication begins

**Verdict:** Graceful degradation. ✓

## 5. Open Questions Requiring Empirical Testing

### 5.1 rtpengine dual-source behaviour with media-handover
Does rtpengine switch return RTP destination on EVERY packet from a different
source, or only when the current source goes silent?

**Test:** Enable media-handover, send from two IPs simultaneously, observe
where return RTP goes. Use tcpdump on the server.

### 5.2 rtpengine duplicate forwarding
Does rtpengine forward both copies of a duplicated packet to the remote
party, or does it have internal dedup?

**Test:** Send duplicate RTP to rtpengine, capture what the remote party
receives. Check dup count in dump_q.

### 5.3 SNAT interaction with nftables dup
Does the SNAT rule correctly apply to dup'd packets exiting via wlan0?
Or does the dup bypass the nat chain?

**Test:** Set up rules, send packets, capture with tcpdump on wlan0 to
verify source IP is wlan0's IP (not eth0's).

### 5.4 NAT pinhole maintenance
Do the wlan0 duplicate packets keep the wlan0 NAT pinhole open for
return traffic? Or does the router close the pinhole because no
application socket is bound to it?

**Test:** Send duplicates via wlan0 for 5 minutes, then fail eth0, check
if return RTP arrives via wlan0 immediately.

## 6. Implementation Plan

### Phase 1: Kamailio Configuration
- Add `media-handover` flag to rtpengine_offer/answer calls
- Already have RFC 5626 outbound config ready (apply-outbound.sh)

### Phase 2: nftables Rules
- Build failover_manager.py to manage nftables rules
- Apply rules when dual_path_failover enabled + both interfaces up
- Remove rules when disabled or interface lost

### Phase 3: Empirical Testing
- Test items from Section 5
- Verify zero-gap failover with audio

### Phase 4: Production Hardening
- Handle DHCP IP changes (rules reference specific IPs)
- Handle interface flapping (debounce)
- Status reporting to UI
- Install script integration

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| rtpengine oscillates return path | Medium | Audio jitter | Test and adjust timing |
| SNAT doesn't apply to dup'd packets | Low | wlan0 packets dropped | Test with tcpdump |
| Doubled bandwidth causes congestion | Low | Audio quality | Only on metered connections |
| media-handover security (RTP hijack) | Very Low | Stream hijacked | SRTP encryption prevents |
| NAT pinhole closes for wlan0 | Medium | Failover delayed | Regular dup keeps pinhole open |
| pjsua can't send BYE after failover | High | Can't hang up gracefully | 5s hangup timeout resets state |

## 8. Comparison with Alternatives

| Approach | Failover Gap | Complexity | Server Changes |
|----------|-------------|-----------|---------------|
| **nftables dup (this design)** | **~20-40ms** | **Medium** | **media-handover flag only** |
| WireGuard tunnel | 1-2 seconds | Low | None |
| Re-INVITE on failover | ~1 second | Medium | None |
| Server-side relay | ~0ms | High | Custom relay process |
| Same-subnet bonding | ~100ms | Low | None |
| Custom UDP proxy on Pi | ~0ms | High | None |
