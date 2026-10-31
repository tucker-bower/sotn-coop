# The co-op link protocol (wire version 10, mailbox version 12)

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
2. **Check the mailbox:** if `magic` isn't `'COOP'` (`0x504F4F43`) or `version` isn't 12, the game is still booting: handle incoming `HELO`s, drop everything else, and stop here.
3. **Rank:** write the host's rank (0 or 1, different for the two players) to `rank`.
4. **Presence:** send `PRES` with the `self` presence (0x2C bytes) and the presence tail (below), whose `pad` is `CoopLink.selfPad`.
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
| `CTRL` | `seq` (u32), `last` (u8), `pad` (u8), `len` (u16), then a ≤ 1000-byte chunk of `zlib.compress(json)` | Reliable online control messages, keyed by `op`: joint saves (`save_req`, `save_done`, `load_save`, `game_over`) and the partner's copies (`weapon`, `familiar`, `status`, below). |
| `CACK` | `delivered` (u32): the highest `CTRL` chunk number received in order | Reliable ack for `CTRL`. |
| `SPRT` | the sender's own attack sprites: N × 20-byte `CoopSprite` (below), N ≤ 24 | Every frame while there are any, then one empty one. Best effort; keep the newest. The receiver writes them to `partnerSprites` (M12). |
| `PRIM` | `zlib` of N × 0x30-byte primitives (the sender's attack primitives, below), N ≤ 32 | As `SPRT`. The receiver writes them, decompressed, to `partnerPrims` (M12). |
| `HITS` | the sender's player's attack hitboxes: N × 12-byte `CoopHit` (below), N ≤ 16 | Every frame while there are any, then one empty one. Best effort; keep the newest. The receiver writes them to `partnerHits` (M15). |
| `HELO` | UTF-8 JSON: `{"link": 10, "patch": <the co-op disc's CRC32 as an integer, or null>, "sid": <8 hex digits, random per host run>, "room": <16 hex digits, online only>, "clock": [clockMs, echoMs, holdMs], "pvp": <the host's PvP setting, online, from the hosting side only>}` | Once a second, from the first frame (also while the game boots, and four times a second in the lobby). `clock` measures the round trip as the presence tail does. `room` is `sha256("sotn-coop-token:" + room code without dashes)[:16]`: a host that has one ignores HELOs without it, and its own (same `sid`). |

**Reliable events:** exactly once, in order.
- **Numbering:** each host numbers its events 1, 2, 3, …
- **Sending:** the sender keeps every event until it's acked. It sends new ones right away, and resends all unacked ones after the retransmission timeout (below).
- **Receiving:** the receiver keeps events that arrive ahead of a gap, delivers in number order, drops what it already delivered, and answers every `EVTS` with an `ACK` carrying its in-order high-water mark.

**Presence tail (16 bytes after the presence):** `snapAck` (u32: the newest `snap_id` this host has decoded, 0 if none), `clockMs` (u32: the sender's clock in ms, wrapping), `echoMs` (u32: the newest `clockMs` heard from the partner, 0 if none), `holdMs` (u16: how long ago, in ms, that was heard), `pad` (u16: the sender's buttons that frame, `CoopLink.selfPad`; 0 from hosts before 0.13, which sent padding there). The receiver writes `pad` to `CoopLink.partnerPad` with the presence it came with (M13: the partner's simulated body runs on it).
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

**Finding the partner (room codes, `link/connect.py`):** the game's socket binds UDP port 47811 when it's free (any port otherwise). While looking, each side sends `HELO` to the partner's candidates from the relay ten times a second, and broadcasts it to `255.255.255.255:47811` and its /24's `.255:47811` twice a second. The broadcast needs no relay, so two games on the same network find each other even when the relay or STUN can't be reached. A host joined by ip:port (no `room`) ignores `HELO`s with a `room` from anyone but its peer.

## Presence (0x2C bytes)
| offset | type | field |
|---|---|---|
| 0x00 | u8 | flags: 1 in play, 2 sprite drawable, 4 paused (menu/map), 8 busy (loading, cutscene, arriving), 16 dead, 32 boss fight, 64 cutscene, 128 in a cutscene it was pulled into (follower) |
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

## The mailbox (`g_CoopLink`, 0x225B8 bytes)
| offset | field | written by |
|---|---|---|
| 0x0000 | magic `'COOP'`, version (12), heartbeat | game |
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
| 0x21448 | `control`: bit 0 mute music, bit 1 no boss aggro, bits 8–15 the aggro chance, bits 16–23 the partner's volume, bit 24 PvP | launcher |
| 0x2144C | `character`: the CHAR_* this game's player plays, from its next load (M8) | launcher |
| 0x21450 | `options`: OPT_* bits, the player's own settings (1 one-button moves, 2 the partner's body; bits 8–23 the spell on each right-stick direction) | launcher |
| 0x21454 | `padExtra`: buttons a PlayStation pad lacks (right stick: 1 up, 2 right, 4 down, 8 left), every frame | launcher |
| 0x21458 | `selfSpriteCount` (u32), `selfSprites` (24 × `CoopSprite`) | game |
| 0x2163C | `partnerSpriteCount` (u32), `partnerSprites` (24 × `CoopSprite`) | host |
| 0x21820 | `selfPrimCount` (u32), `selfPrims` (32 × 0x30) | game |
| 0x21E24 | `partnerPrimCount` (u32), `partnerPrims` (32 × 0x30) | host |
| 0x22428 | `selfPad`: this player's buttons this frame | game |
| 0x2242C | `partnerPad`: the partner's buttons, written with each presence (the partner's body runs on them, M13) | host |
| 0x22430 | `selfHitCount` (u32), `selfHits` (16 × `CoopHit`) | game |
| 0x224F4 | `partnerHitCount` (u32), `partnerHits` (16 × `CoopHit`): the game uses each list for one frame, then zeroes the count | host |

**The partner's copies (CTRL, M12–M13):** each is JSON `{"op": …, "data": base64(zlib(blob))}`, sent when the sender's copy changes. The receiver writes the blob, magic last, to the partner's address in expansion RAM.
- `weapon` (plus `"hand"`: 0 or 1): the `CoopWeapon` (0x7320 bytes: magic `'WPNS'`, seq, item, then the hand's overlay, 256×128 tile sheet and 24 palettes) from `0x80710000 + hand × 0x8000`, to `0x80720000 + hand × 0x8000`. Sent when its seq changes (the game copies a weapon when it loads). The partner draws the swing from it (`weapons.c`).
- `familiar`: the `CoopFamiliar` (0x10420 bytes: magic `'FAML'`, seq, servant, sprite bank, then its overlay, tile sheet and palettes 0x140–0x15F) from `0x807C0000`, to `0x807E0000` (`familiar.c`).
- `status`: the sender's `g_Status` from `hp` (0x48 bytes) and from `subWeapon` (0x34 bytes), at most every 10 frames and only when changed, to a `CoopStatus` (magic `'STAT'`) at `0x80730000`. The partner's body runs with these stats, level and equipment (`partner.c`).

**`CoopSprite` (20 bytes, M12):** `animSet` (s16), `animCurFrame` (u16), `x`, `y` (s16, in the room), `palette` (u16), `facingLeft`, `blendMode` (u8), `zPriority`, `drawFlags`, `unk5A` (u16), `weapon` (u16: `0x100 | hand` for a hand weapon's sprite, whose `animSet` is then its bank, 0x10–0x13; else 0).

**Primitives (0x30 bytes each, M12):** a `Primitive` as the game keeps it, with its `next` pointer left out and positions in the room. Byte 0x27 (a pad byte) is `0xFA` for a familiar's primitive (M13).

**Presence `flipX`, high bits (M13):** bit 7, this player just came in by teleport (a revive): the partner's copy plays its character's teleport-in; bit 6, this player's one-button moves are on.

**`CoopHit` (12 bytes, M15):** `x`, `y` (s16: the hitbox's centre in the room, in pixels), `w`, `h` (u8: half its width and height), `hitboxState` (u8), `facingLeft` (u8), `attack` (s16), `element` (u16).

**The rings:** an entry's slot is `count % 256`. The writer adds at `head` and then bumps it; the reader takes at `tail` and then bumps it. Full means `head - tail == 256`.
