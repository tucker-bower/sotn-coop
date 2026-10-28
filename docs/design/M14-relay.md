# M14 design: every pair connects (relay fallback)

**Status:** approved by Tucker (2026-10-27). Replaces the "Symmetric NAT" decision in STATUS.

## Goal
Any two players connect with a room code, whatever routers or networks they're on, without knowing or choosing anything. **The mod never requires a hosted server** (D74 stays): every step works with no server of ours, and the last step, a relay, can be run by anyone, including one of the players.

## Today
12 of the 16 kinds of router pairing connect (`link/test_connect.py`). The other 4 involve a symmetric router (phone hotspots, some ISPs): about 5–15% of pairs. Room codes meet on ntfy.sh, a public, open-source service anyone can also host.

## The ladder
The connector tries everything at once and keeps the first path that works. The lobby shows one line ("Connecting…"); the session log says which step won.
| Step | What | Rescues | Server |
|---|---|---|---|
| 1 | LAN broadcast, hole punching (today) | 12 of 16 | none (ntfy.sh to meet) |
| 2 | **IPv6 direct:** both sides post their IPv6 addresses too, and punch through the IPv6 firewall | most phone networks (they're IPv6-first) and many home ISPs | none |
| 3 | **Router port mapping:** UPnP-IGD, NAT-PMP and PCP open a port on the router | symmetric home routers that allow it (most consumer ones do by default) | none |
| 4 | **Port prediction:** the port-restricted side opens 256 ports and the symmetric side probes them (the "birthday" method) | symmetric vs port-restricted, in about 2 s | none |
| 5 | **Relay:** both games send through a relay | everything left | an open relay, anyone's |

## Step 5: who runs the relay
| Option | Idea | Verdict |
|---|---|---|
| **A. Peer and community relays (recommended)** | `link/relay.py`, one small file, open source: any launcher whose own connection is open can relay for others (a setting, on by default, capped at 2 sessions and about 1 Mbit/s), and anyone can run it on a server. Relays announce themselves on an ntfy topic; a stuck pair picks the nearest | ✅ No server of ours. The more people play, the more relays exist. A pair can also name a friend's relay. |
| B. A project relay | We host one (about $5/month) | ❌ A hosted server, against D74 |
| C. Public TURN services | Free TURN from third parties | ❌ Accounts, rate limits, and they can disappear |

- **Safety:** a relay sees only the room's sealed traffic: packets are signed with the room token (already in HELO) and encrypted with a key from the room code, so a relay can't read or change them. Relays rate-limit and drop anything without a room they know.
- **Room-code durability:** the room-code meeting point gets a fallback list (ntfy.sh, then any community ntfy server), so the mod outlives one service.

## Acceptance criteria
1. `link/test_connect.py`: **16 of 16** router pairings connect in `natsim`, each through the cheapest step that works (steps 1–4 for 13+, the relay for the rest), with no user choice.
2. IPv6-only and dual-stack networks connect (new natsim profiles).
3. Router port mapping: a simulated UPnP and NAT-PMP router opens a port; a router without them is skipped in under 1 s.
4. A relayed session plays the full online suite (`online_*`) with under 20 ms added on a local relay; the relay can't decode the packets (test).
5. A launcher relays for another pair while playing, within its cap, with no visible change to its own game.
6. The room-code meeting point falls back to a second ntfy server when the first is down.
7. A real two-home test by Tucker, one side on a phone hotspot.

## Risks
- **Peer relays are few at launch.** Until enough people play, a stuck pair may find none. The fallback is the community list plus the published relay file for anyone who wants to help.
- **Port prediction depends on the router's port allocation**; some routers randomise and defeat it. Measured on real routers in Tucker's test.
- **A relaying player's upload:** capped, and the setting is easy to find.

## Budget
About 3–4 usage windows: IPv6 and port mapping 1, port prediction 1, the relay and its encryption 1–2.

## Build log
- **2026-10-28, step 5 first (the relay), branch `coop-m14-relay`:** `link/relay.py` (anyone runs it: `python -m link.relay`), the transport's sealed relay mode (`use_relay`: `RLY1` + room id + nonce, HMAC tag and SHA-256 keystream from the room token; stdlib only), and the connector's fallback: the host posts the relay it picked with its addresses, and after 6 s of punching without a reply both go through it. `link/test_connect.py`: the 3 pairings punching can't do (port-restricted vs symmetric, both ways; symmetric vs symmetric) connect through a relay, presences flow, and the relay never sees a readable packet; a pair that can punch still connects directly. All online session tests pass.
- **Where relays come from:** `COOP_RELAYS="host:port,..."` for now. Next: the launcher setting (relay for others, on by default, capped), announcing on an ntfy topic, and the stuck pair picking the nearest; then steps 2–4 (IPv6, port mapping, port prediction), which avoid the relay.
- **2026-10-28, step 3 (router port mapping):** `link/portmap.py`: NAT-PMP and UPnP IGD at once, in the background from the connector's start; a mapped port goes first in the candidates and is posted again. `link/test_portmap.py` (fake routers: both protocols, and routers that don't answer) passes. `link/test_connect.py`: a symmetric router that opens the port connects directly in all three hard pairings. The harness sets `COOP_NO_PORTMAP` so tests never touch the real router.
