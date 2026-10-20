# The co-op link protocol (wire version 9, mailbox version 8)

This is everything a **host** needs, so another one can be written without reading our Python: an Android host in Kotlin or C++, or a C++ host inside an emulator.
- **The reference implementation:** `link/host.py`, `link/transport.py` and `link/mailbox.py`.
- **The game side:** `module/link.h`, which defines the layout.
- **The test:** `harness/spec_test.py` (`link_spec_conformance`). It plays the partner with a raw UDP socket, using only this document, against our host and a real game.

## The parts
```
 game (emulator)  ⇄  mailbox in the game's RAM  ⇄  host  ⇄  UDP  ⇄  host  ⇄  mailbox  ⇄  game
```
- **One host per game.** Between two frames, while the emulator is paused, the host reads and writes the game's **mailbox**, `g_CoopLink`, a struct in the 8 MB expansion RAM. It then exchanges **datagrams** with the partner's host.
- **Where the mailbox is:** its address is the `g_CoopLink` symbol in the module's map, `build/coop/coop.map`. It is fixed for a given co-op disc.
- **The game never touches the network, and the host never touches game state outside the mailbox.**
- **Numbers** are little-endian everywhere.

## The host's job, once per frame
0. **Count the frame:** the host's frame counter goes up by one, every frame, whatever happens next. Every datagram carries it.
1. **Hello:** every 60 frames, send `HELO`.
2. **Check the mailbox:** if `magic` isn't `'COOP'` (`0x504F4F43`) or `version` isn't 8, the game is still booting: handle incoming `HELO`s, drop everything else, and stop here.
3. **Rank:** write the host's rank (0 or 1, different for the two players) to `rank`.
4. **Presence:** send `PRES` with the `self` presence (0x2C bytes) and the presence tail (below).
5. **Snapshot:** if `snapOutSeq` changed since last frame, send `snapOut[0:snapOutSize]` as `SNPC` chunks (below).
6. **Events out:** move the game's new events out of the `out` ring, then send them reliably (`EVTS`).
7. **Receive** every datagram waiting:
   - `PRES`: the partner's presence. Write it to `partner` and zero `partnerAge`. Simplest: write the newest (by datagram sequence number). Better online: play presences back at an even pace (below);
   - complete snapshots (`SNPC`): write the payload to `snapIn`, then `snapInSize`, then `snapInSeq + 1`, in that order. Simplest: the newest, as it completes. Better online: on the same schedule as the presences;
   - `EVTS` and `ACK`: the reliable channel (below);
   - `HELO`: the handshake (below).
8. **Events in:** write the partner's events that were delivered in order into the `in` ring, as many as fit. Keep the rest for next frame.

Commands (`cmd`) and saves (`saveOut`/`saveIn`) are written by the **launcher**, not by the link: joint saves, loading a save, and arriving somewhere.

## Datagrams
Every datagram starts with a 12-byte header: `tag` (4 ASCII bytes), `seq` (u32, a per-sender counter that goes up by one with each datagram) and `frame` (u32, the sender host's frame counter, step 0). The payload follows. No datagram is bigger than 1200 bytes.

| tag | payload | delivery |
|---|---|---|
| `PRES` | the sender's presence, 0x2C bytes (below), then the 16-byte presence tail | Every frame. Best effort. |
| `SNPC` | `snap_id` (u32, 1, 2, 3…), `base_id` (u32, 0 = none), `chunk_idx` (u8), `chunk_cnt` (u8), then a ≤ 1150-byte chunk of the compressed snapshot | A shared-room snapshot (up to 0xF000 bytes, opaque to hosts) in chunks. Best effort: a snapshot is complete when all `chunk_cnt` chunks of one `snap_id` are in; ignore ids at or below the newest complete one. |
| `EVTS` | `first` (u32, the first record's number), then N × 8-byte events | Reliable (below). At most 128 events per datagram. |
| `ACK ` | `delivered` (u32): the highest event number received in order | Reliable (below). |
| `CTRL` | `seq` (u32), `last` (u8), `pad` (u8), `len` (u16), then a ≤ 1000-byte chunk of `zlib.compress(json)` | Reliable online control/save messages (`save_req`, `save_done`, `load_save`, `game_over`). |
| `CACK` | `delivered` (u32): the highest `CTRL` chunk number received in order | Reliable ack for `CTRL`. |
| `HELO` | UTF-8 JSON: `{"link": 9, "patch": <the co-op disc's CRC32 as an integer, or null>, "sid": <8 hex digits, random per host run>, "room": <16 hex digits, online only>, "clock": [clockMs, echoMs, holdMs]}` | Once a second, from the first frame (also while the game boots, and four times a second in the lobby). `clock` measures the round trip as the presence tail does. `room` is `sha256("sotn-coop-token:" + room code without dashes)[:16]`: a host that has one ignores HELOs without it, and its own (same `sid`). |

**Reliable events:** exactly once, in order.
- **Numbering:** each host numbers its events 1, 2, 3, …
- **Sending:** the sender keeps every event until it's acked. It sends new ones right away, and resends all unacked ones after the retransmission timeout (below).
- **Receiving:** the receiver keeps events that arrive ahead of a gap, delivers in number order, drops what it already delivered, and answers every `EVTS` with an `ACK` carrying its in-order high-water mark.

**Presence tail (16 bytes after the presence):** `snapAck` (u32: the newest `snap_id` this host has decoded, 0 if none), `clockMs` (u32: the sender's clock in ms, wrapping), `echoMs` (u32: the newest `clockMs` heard from the partner, 0 if none), `holdMs` (u16: how long ago, in ms, that was heard), 2 bytes of padding.
- **Round trip:** on receiving a tail with `echoMs` set, `rtt = now - echoMs - holdMs` (ms, wrapping). Smooth it as TCP does (RFC 6298).
- **Snapshot acks:** the newest `snapAck` the partner has sent is the base for the next delta.

**Snapshot compression:** with `base_id` 0, the chunks join to `zlib(snapshot)`. Otherwise to `zlib(snapshot XOR base)`, where `base` is snapshot `base_id` (cut or zero-padded to this snapshot's length). The sender uses the newest snapshot the partner acked, if it still has it (it keeps the last 64), else none. The receiver keeps the last 64 snapshots it decoded, and drops a snapshot whose base it doesn't have.

**Playback (recommended online, `link/playout.py`):** the partner's presences and snapshots arrive bunched up. Hold them and hand the game one sender frame per frame:
- `offset = arrival time - frame / 60`. Its minimum over the last 3 s is the fastest path; restart that minimum when every offset of the last 0.3 s is more than 2 frames above it.
- Play sender frame `(now - minimum - delay) * 60`, where `delay` covers the 95th percentile of `offset - minimum` (at least a frame while presences go missing; at most 250 ms; falling back by at most 20 ms per second).
- Between two presences less than 6 frames apart in the same room, interpolate x, y and the camera.

**Retransmission:** reliable channels (`EVTS`, `CTRL`) resend what's unacked after `srtt + max(4 × rttvar, 1 frame) + 2 frames` (between 50 ms and 1 s; 250 ms before any round trip is measured).

**Restarts:** when the partner's `sid` changes, it started again: reset everything numbered (reliable channels both ways, snapshot ids and bases, playback).

**Handshake:** if the partner's `link` differs, or both `patch` values are set and differ, the host refuses the partner.
- It relays nothing more (the games play on alone), keeps sending `HELO`, and reports why ("Your partner's co-op version is different…").
- A later matching `HELO` lifts the refusal.

## Presence (0x2C bytes)
| offset | type | field |
|---|---|---|
| 0x00 | u8 | flags: 1 in play, 2 sprite drawable, 4 paused (menu/map), 8 busy (loading, cutscene, arriving), 16 dead, 32 boss fight, 64 cutscene |
| 0x01 | u8 | character (0 Alucard) |
| 0x02 | u8 | flipX (bit 1) |
| 0x03 | u8 | blend mode |
| 0x04 | u16 | stage |
| 0x06 | u16 | z priority |
| 0x08 | s16 ×2 | room cell (left, top) |
| 0x0C | s16 ×2 | x, y in the room (pixels) |
| 0x10 | s16 | animSet |
| 0x12 | u16 | animation frame |
| 0x14 | u16 | palette |
| 0x16 | u16 | draw flags |
| 0x18 | u32 | the sender's frame counter |
| 0x1C | u16 | room id (offset in the stage's room table) |
| 0x1E | s16 ×2 | last x, y on the ground |
| 0x22 | u16 | frames in this room |
| 0x24 | s16 ×2 | camera x, y |
| 0x28 | u16 | shared-room role: 0 none, 1 authority, 2 guest |
| 0x2A | u16 | the boss target-switch count (tests) |

## Events (8 bytes: u8 type, u8 pad, u16 a, u32 b)
| type | name | a | b |
|---|---|---|---|
| 1 | FLAG | castle flag index | the value to merge (OR; max for counters) |
| 2 | MAP | castle map index | newly set bits |
| 3 | ITEM | item id | equip kind |
| 4 | GRANT | 0x8000 life, 0x4000 heart, 0x2000 relic | the amount, or the relic id |
| 5 | GOLD | — | the gold delta (s32) |
| 6, 7 | HIT, HIT2 | a shared-room hit (`module/link.h`) | |
| 8, 9, 10 | SPAWN ×3 | an entity the guest's hit detection made | |
| 11 | RECORD | time attack event (0xFFFF: visited bits) | the record |
| 12 | TAKEN | slot \| entityId << 8: a drop the guest took | — |

Hosts don't interpret events: they move them between rings.

## The mailbox (`g_CoopLink`, 0x2144C bytes)
| offset | field | written by |
|---|---|---|
| 0x0000 | magic `'COOP'`, version (8), heartbeat | game |
| 0x000C | `self`: presence | game |
| 0x0038 | `partner`: presence | host |
| 0x0064 | `partnerAge` (u32, frames since `partner` was written) | game counts, host zeroes |
| 0x0068 | `out` ring: u32 head (game), u32 tail (host), 256 × 8-byte events | |
| 0x0870 | `in` ring: u32 head (host), u32 tail (game), 256 × 8-byte events | |
| 0x1078 | events dropped, because the out ring was full | game |
| 0x107C | `cmd`: seq, type, stage, room, x, y | launcher |
| 0x108C | `cmdDone` | game |
| 0x1090 | `saveSeq`, `saveOut` (0x11CC bytes) | game |
| 0x2260 | `saveIn` (0x11CC bytes) | launcher |
| 0x342C | `saveBlock`, `cardResult` | game |
| 0x3434 | `rank` | host |
| 0x3438 | `snapOutSeq`, `snapOutSize`, `snapOut` (0xF000) | game |
| 0x12440 | `snapInSeq`, `snapInSize`, `snapIn` (0xF000) | host |
| 0x21448 | `control`: bit 0 mute music, bit 1 no boss aggro, bits 8–15 the aggro chance | launcher |

**The rings:** an entry's slot is `count % 256`. The writer adds at `head` and then bumps it; the reader takes at `tail` and then bumps it. Full means `head - tail == 256`.
