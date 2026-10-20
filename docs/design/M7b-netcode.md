# M7b netcode: review, simulation and fixes

**Status:** done 2026-10-20 (M7b part 6). Tests: `harness/session_net.py` (network profiles), `link/test_connect.py` (home routers), and the online harness scenarios.

## Summary
- **Over the internet, M7 would have failed for most players.**
  - The host advertised its public IP with its *local* port. On this PC's own network the router maps local port 60299 to 63189, so the code it handed out pointed nowhere.
  - Only the joiner learned the other side's address, so the host's router dropped the joiner's packets.
  - Fixed: STUN runs on the game's own socket, both sides post their addresses to the relay, and both send to each other at once. 12 of the 16 combinations of common home routers connect. The other 4 can't work without a relay server, and they fail after 30 s with a reason in plain words.
- **Online play stuttered badly with real-world jitter.** M7 wrote the partner and the shared enemies straight to the game whenever packets arrived, bunched or not. Fixed with a jitter buffer that plays them back one frame per frame and interpolates across lost packets. Partner stutter across an ocean went from 24.7% of frames to 1.7%, and on bad Wi-Fi from 36% to 1.8%.
- **Bandwidth: 841 → 200–300 kbit/s** for the room's authority. Shared-room snapshots are now XOR-delta compressed against one the partner already has, so a phone hotspot isn't saturated any more.
- **Other fixes:**
  - Resend timers come from the measured round trip, instead of a fixed 15 frames.
  - The round trip is measured for free, piggybacked on presence.
  - Only the partner who knows the room code is accepted. Before, anyone could take over the session with one packet.
  - A partner who restarts gets clean state.
  - Room codes went from 10,800 possibilities to 12.6 million.
  - The old harness latency simulation used wall-clock time while the harness runs at about 25× real time, so it never simulated what it claimed.

## How it's tested
- **`link/netsim.py`: a simulated internet on virtual time.** Both games share one virtual timeline (frames / 60), so 75 ms is 4.5 frames however fast the harness runs. Each direction has:
  - a base delay
  - correlated, right-skewed jitter
  - Wi-Fi-style stalls
  - Gilbert-Elliott bursty loss
  - rare reordering and duplication
  - a bandwidth cap with a bounded queue
  - scheduled outages

  The scheduler steps whichever PC's next frame is due first. One PC runs 0.1% fast (clock drift), and it hitches once for 167 ms. It's seeded, so runs are reproducible.
- **Profiles:** one-way delay, jitter, loss.

  | profile | one-way delay | jitter | loss |
  |---|---|---|---|
  | `lan` | 1 ms | — | — |
  | `city` | 10 ms | ±3 | 0.1% |
  | `country` | 30 ms | ±6 | 0.5% |
  | `transatlantic` | 55 ms | ±10 | 1%, short bursts |
  | `wifi` | 15 ms | ±20, plus 150 ms stalls | 3% in bursts |
  | `cellular` | 45 ms | ±25, plus 250 ms stalls | 2%, 1.5 Mbit/s cap |
- **`harness/session_net.py`:** A is the authority in the entrance hall and B the guest. A paces back and forth while B fights, and gold is granted every 45 frames. Then the network blips (0.4 s) and drops out (3 s). Everything is measured on B, the side that feels the network.
- **`link/natsim.py` + `link/test_connect.py`:** a virtual internet with the four kinds of home router (RFC 4787 mapping and filtering), two STUN servers and the relay. It runs the real connector, host and transport code.

## Before / after
Same scenario and same seeds. "Before" is the M7 code, "after" is v9 with playout.

**Columns:**
- **Stutter:** frames where the partner visibly stalls then jumps, beyond the real movement.
- **Enemies fresh:** the share of the authority's snapshots the guest gets to show.
- **Latency:** how old the partner is on screen.
- **Reaction:** about how long an enemy the guest hits takes to react (round trip plus playout delay).

| profile | stutter | enemies fresh | latency | reaction | upload | packets/s |
|---|---|---|---|---|---|---|
| lan | 0.7% → 0.2% | 99.5% → 99.9% | 0 → 17 ms | 34 ms | 841 → 202 kbit/s | 182 → 122 |
| city | 7.1% → 0.5% | 95.5% → 99.9% | 17 → 17 ms | 54 ms | 841 → 226 | 182 → 122 |
| country | 10.3% → 0.7% | 93.1% → 98.3% | 33 → 50 ms | 107 ms | 841 → 251 | 182 → 122 |
| transatlantic | 24.7% → 1.7% | 86.6% → 98.0% | 67 → 67 ms | 162 ms | 841 → 279 | 182 → 122 |
| wifi | 36.1% → 1.8% | 67.9% → 94.2% | 33 → 133 ms | 187 ms | 841 → 257 | 182 → 122 |
| cellular | 41.3% → 2.2% | 64.7% → 93.6% | 67 → 200 ms | 270 ms | 841 → 288 | 182 → 122 |

**Unchanged, and fine in every profile:**
- Find/grant delivery: median one-way plus a frame; worst case 350 ms on cellular.
- No shared-room hand-overs during play.
- None on a 0.4 s blip.
- After a 3 s outage, the room is shared again within 83–267 ms. That outage costs two hand-overs: the guest takes over its own world while cut off, then rejoins. That's intended.
- The host's work per frame stays under 0.4 ms (p99), and nothing in it ever waits for the network.

Raw tables: `.env/out/net_profiles/table.md` (after), `net_profiles_base` (before).

## What changed (wire version 9, `docs/link-protocol.md`)
1. **Frame stamps.** Every datagram carries the sender's host frame, so the receiver can tell bunching from real timing.
2. **Playout (`link/playout.py`).** The partner's presences and snapshots are held for an adaptive delay and handed to the game one sender frame per frame, in order.
   - The delay covers the 95th percentile of jitter seen in the last 3 s. It's at least a frame while packets go missing, at most 250 ms, and falls back slowly.
   - The puppet's position and camera are interpolated across a missing presence.
   - When the path's delay changes for good (a slower route, or the partner's PC hitched), the buffer re-bases within 0.3 s instead of treating it as jitter for seconds.
   - Couch play (two games, one PC) doesn't use it.
3. **Delta snapshots.** Each snapshot is XOR'ed with the newest one the partner has acked (the ack rides on presence), then zlib'd. That's about 120 bytes on a LAN and 430 bytes at transatlantic distances, instead of about 1.6 KB in two packets.
   - Measured on real fight snapshots: XOR beats zlib with a preset dictionary 2–5×, because changes are a few scattered bytes per entity.
   - A lost snapshot never breaks the chain: the base is always one the receiver confirmed.
4. **Round trip and loss for free.** Presence carries the sender's clock and an echo of the partner's, NTP-style, so there's a round-trip sample every frame with no extra packets. Loss is the share of the partner's per-frame presences that never arrived.
5. **Resends on a measured timeout** (RFC 6298: srtt + 4·rttvar + 2 frames, 50 ms–1 s), instead of every 15 frames.
6. **Connecting (`link/connect.py`):** candidates (LAN, and STUN from the game's own socket), then rendezvous, then hole punching.
   - **Rendezvous:** both sides post to the room's ntfy.sh topic over one streaming request each (ntfy limits request rates), and both read the other's post.
   - **Hole punching:** both send HELO to every candidate of the other, ten times a second.
   - **Room token:** HELO carries a token derived from the room code. Only a matching HELO can become the partner, and from then on everything from other addresses is ignored. A HELO from a new address with the right token is accepted, so a router that remaps mid-session doesn't drop the game.
   - **Diagnosis:** asking two STUN servers shows whether a router is symmetric, which names the cause when connecting fails.
7. **Restarts:** HELO carries a per-run `sid`. When the partner's changes, all numbering resets both ways. Before, a partner who restarted the launcher would have had every event and snapshot ignored.
8. **Removed** the old one-way room lookup (LAN broadcast plus host-only relay post), and the separate-socket STUN.

## Router results (`link/test_connect.py`)
| host ↓ / joiner → | full cone | restricted | port restricted | symmetric |
|---|---|---|---|---|
| full cone | ✅ | ✅ | ✅ | ✅ |
| restricted | ✅ | ✅ | ✅ | ✅ |
| port restricted (most home routers) | ✅ | ✅ | ✅ | ❌ with reason |
| symmetric (phone networks, some ISPs) | ✅ | ✅ | ❌ with reason | ❌ with reason |

Also tested:
- Two players in the same house connect directly across their LAN.
- A symmetric router with a forwarded port connects.
- Someone with a different room code is never accepted, even when they punch our address.

Real-network check: STUN through the game socket from this PC returns the same mapping from Google and Cloudflare, so this connection's NAT is cone-type.

## Defaults I chose (reversible)
- **Playout on for online, off for couch.** Smoothness of shared enemies matters for fairness: the guest's own hit detection runs against the copies it sees, so an enemy that jumps can hit you from a place you never saw it. The cost is latency on jittery links (Wi-Fi 33 → 133 ms on the partner). The guest's own actions stay instant: attacks and getting hit are computed locally.
- **Max playout delay 250 ms; target 95th-percentile jitter.** Lower means more stutter on bad Wi-Fi, higher means more lag.
- **Snapshot history 64** (about 1 s) at each end, as delta bases.
- **Room codes like `BAT-7K2Q`.**

## Not done / risks
- **Symmetric routers on both sides, or symmetric against port-restricted, can't connect without a relay server (TURN).** That's a server we'd host and pay for, which goes against D74's zero-infrastructure rule. Estimated at 5–15% of pairs; phone hotspots are the usual case. *Decision for Tucker* (STATUS).
- **UPnP port mapping isn't implemented.** It would rescue some symmetric-router cases. Small and self-contained, so it's a candidate follow-up.
- **Real two-home internet test:** the simulated routers follow RFC 4787, but only a real session proves it. That's Tucker's playtest.
- **Shared-room drops (`TAKEN_FRAMES`, 0.5 s):** the guest keeps a drop it took hidden until the authority confirms. On a phone hotspot the round trip plus playout can approach that, and a taken drop could flash back. The module change to raise it is queued with the next disc build.
