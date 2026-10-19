# M2 design: Shared progression (live)

**Status:** built, all criteria pass (results at the end). Approved 2026-10-18 with two changes: every find is shared, consumables included (D37), and gold is pooled (D38).
**Budget:** 12% of the month (the joint save moves to M3, see "Scope change"). Target: 2026-10-26.
**Context:** D21 (what's shared), D22 (live), `research.md` → "Independent exploration".

## Goal
Whatever one player unlocks counts for both, within a few frames:
- relics, max-HP and max-Hearts upgrades, and equipment (each player gets a copy);
- opened walls, doors and switches, beaten bosses, items taken, and the explored map.

A change shows up even in the room the partner is standing in. Levels, XP, gold, consumables and what each player has equipped stay separate.

**Scope change:** the joint save moves to M3. Resuming a save means loading a player into a stage and room, which is the same mechanism as teleport and respawn, so it belongs with them. ROADMAP updated (M2 15% → 12%, M3 8% → 11%).

## Part 1: what's shared, and how (from the code)

| What | Where in RAM | Detected by | Applied on the partner by |
|---|---|---|---|
| Castle flags: walls, doors, switches, elevators, bosses, cutscenes, items taken (`0x100…`), bestiary (`0x190…`), rare drops (`0x1B0…`) | `g_CastleFlags[0x300]` | the module diffing a shadow copy each frame | merge per byte: **OR** for bit-field bytes, **max** for counter bytes (`NO4_WATER_BLOCKED++` and similar), **skip** for excluded bytes; then live refresh (part 3) |
| Explored map | `g_CastleMap[0x800]`, 2 bits per cell | shadow diff | OR, then the game's own reveal steps: `g_RoomCount++` per new cell and `func_800F1B08` to draw the cell into the map image |
| Items found (equipment **and consumables**, D37) | `equipHandCount`/`equipBodyCount` (+ order lists) | **wrapping `g_api.AddToInventory`** | DRA's `AddToInventory(id, kind)`, called directly (so it isn't echoed back) |
| **Gold, pooled (D38)** | `g_Status.gold` | shadow diff, sent as a delta | add the delta, never below 0 |
| Relics | `g_Status.relics[]` | wrapping `g_api.func_800FE044`, type `0x2000` | the same function, so it sets found + active exactly like a pickup |
| Life / Heart Max Up | `hpMax`, `heartsMax` | wrapping `func_800FE044`, types `0x8000` / `0x4000` | the same function (+5, with the pickup's refill) |

**Why wrap `g_api` entries:**
- Stage overlays (pickups, enemy drops, shops, NPC gifts) reach these functions only through the `g_api` table.
- DRA's own menu code (equip and unequip move items in and out of inventory) calls them directly.

So wrapping the table entries catches exactly "found something in the world" and nothing else. It also needs no new DRA hook: `g_api` is RAM, and the module patches two pointers after `MainGame` fills it.

**SOTN has no MP Max Up.** Max MP only grows with level, which is separate.

**Not shared (D21):**
- level, XP, gold, consumables, equipped items, current HP/MP/Hearts;
- spells learnt, familiar levels, the carried subweapon.

**Excluded castle flags** (state that isn't progress): `NO1_BIRD_CYCLE` (cosmetic cycle), and `PROLOGUE_COMPLETE` and other resets. A script (part 3) lists every flag written by anything other than `= true`, `|=` or `++`, for review. The reviewed list lives in the module.

## Part 2: the event channel

| Option | Idea | Verdict |
|---|---|---|
| **A. The module detects and applies; the host relays events** | Detection (shadow diffs, `g_api` wrappers) and application (the game's own functions) both run in C. The mailbox gets two event rings, out and in. Hosts forward events over a reliable, ordered channel. | ✅ **Recommended.** It uses the game's own functions, so inventory order lists, map drawing and refills stay correct. It runs the same on any emulator (R1). |
| B. The host diffs and pokes RAM | The host reads and writes the flag, map and status bytes directly | ❌ It can't call game functions (map image, order lists), and it races the game. |

- **Events:** 8 bytes each, `{type, a, b}`. The types are FLAG, MAP_CELL, ITEM, MAXUP and RELIC.
- **Transport:** presence stays on UDP. Events go over TCP between the hosts (localhost or internet), each tagged `(origin, seq)` so it applies **exactly once**, even across a reconnect.
- **Session state:** each host also keeps the merged shared state. M3 saves it with the joint save, and a reconnecting game gets a snapshot (flags and map are a union, so a snapshot is safe to apply twice).
- **Picking up the same collectible at once:** if both players pick up the same collectible in the same moment (each in their own world), the ITEM event carries that collectible's flag. A game that took the same collectible itself ignores the partner's copy, so nobody gets two.

## Part 3: live refresh in the partner's current room
Entities read their flag when they spawn. Changing a flag doesn't affect one that's already on screen.

| Option | Idea | Verdict |
|---|---|---|
| **A. Per-kind handling, using a generated table** | **Collectibles** (item drops, relic orbs, Life/Heart Max Up; common entity types shared by every stage) get **despawned**, with no reward. **Flag-gated objects** (secret walls, doors, switches, bridges, elevators) get **re-initialized**: free their primitives, then set `step = 0`, so their own init code re-reads the flag. A script scans the decomp for entity functions that read `g_CastleFlags` and writes `{stage: entity IDs}` into the module. Anything it can't classify falls back to "applies on the next room entry" and goes in a report. | ✅ **Recommended.** It's small and generic, and the report shows exactly what is and isn't live. |
| B. Reload the room | Re-enter the room silently when a flag changes | ❌ It resets enemies and the camera, and the screen flashes. |
| C. Hand-write each case | Patch entity by entity | ❌ There are hundreds across 40+ stages. |

Enemies are never re-initialized, which would reset their HP. Bosses beaten by the partner while I'm fighting the same boss in my own world are M5 (bosses are fought together).

## Defaults (reversible, logged when built)
- **Shop purchases of equipment count as found,** so the partner gets a copy. Gold stays separate.
- **A short notice for the partner's finds** ("Partner found: Alucard Sword") in the game's debug font for 2 s. It gets polished later.
- **A new relic arrives switched on,** as it does when you pick one up.
- **When two games link, castle flags and map merge right away.** Items move only as events. Sessions start from a new game or a joint save (M3), so there's nothing to backfill.

## Acceptance criteria (two-game harness tests)
The harness walks A to real pickups near the test route, using savestate warps plus short walks.
1. **Relic:** A picks one up. B has it (found + active) within 3 frames.
2. **Equipment vs consumable:** A picks up a weapon or armour piece, and B's count goes up by 1. A picks up a potion, and B's inventory doesn't change. In both cases the pickup is gone from B's world.
3. **Max-ups:** A takes a Life Max Up and a Heart Max Up. B's `hpMax` and `heartsMax` each go up by 5.
4. **Map:** A explores new rooms. B's map bits and `g_RoomCount` equal the union of both, and B's map screen shows A's rooms (pixel check).
5. **Live refresh, same room:** B stands in the room (in its own world) while A takes that room's pickup and opens its flag-gated object (a breakable wall or switch on the test route). On B's screen, the pickup vanishes and the object opens within 5 frames, without leaving the room. The generator's report lists every flag-gated entity and how it's handled.
6. **Separate stays separate:** across all of the above, B's level, XP, gold, consumables, HP, equipped items and spells don't change.
7. **Exactly once, and converges:** a 30-minute soak in which both games explore and pick things up. The link drops for 10 s twice. At the end, flags and map are identical, and each inventory equals its own pickups plus the partner's non-consumable ones, with no duplicates.
8. **No regressions:** the M1 suite passes. With no partner, the co-op disc still plays exactly like retail.

## Risks
- **Coverage of live refresh:** some flag-gated objects may misbehave when re-initialized (multi-part, scripted). Mitigation: the generator report plus a per-entity "next entry only" override. The M2 test route covers a few kinds, and later milestones widen it.
- **Flags that aren't progress:** a byte used as live state could cause odd behaviour if merged. Mitigation: the audit script, and the exclusion list.
- **Duplicate equipment:** both players finding the same collectible at once is handled, but an enemy rare drop isn't a collectible, so both get a copy. Accepted.
- **Pickups granted inside DRA:** none to worry about. DRA calls `AddToInventory` directly only in `InitStatsAndGear` (starting loadouts and name codes), which shouldn't be shared. Every in-world grant (pickups, drops, shops, the Librarian, collision rewards) goes through `g_api` (checked in the source).

## Results (2026-10-19)
All tests are two-game harness tests with **real pickups**. Arrive (from M3) puts game A on the item, and the game's own pickup code runs.

| # | Criterion | Result |
|---|---|---|
| 1 | Relic | ✅ `relic_shared`: A picks up the Cube of Zoe in the castle entrance. B has it (found + active) within 3 frames. |
| 2 | Items | ✅ `items_and_maxups_shared`: Holy Mail (armour) and Life Apple (consumable, shared too, D37). B gains exactly the items A found, and both pickups are marked taken in B's world. |
| 3 | Max-ups | ✅ Same test: Life Vessel +5 max HP and Heart Vessel +5 max hearts, in both games. |
| 4 | Map | ✅ `map_shared`: B's map equals A's, and both room counts equal the explored cells. |
| 5 | Live refresh | ✅ `live_despawn`: B stands in the Cube of Zoe's room. A takes the orb and the Shield Potion in its own world. Both vanish from B's world, B stays in the room, and gets each once. ✅ `live_object_refresh`: the Alchemy Lab's secret wall opens in B's world within 5 frames of A opening it (a flag poke stands in for A breaking it), with the tiles rewritten as open and B still in the room. The generated table covers 145 entities on 33 stages. `docs/flag-gated-entities.md` lists them, plus the 51 scripted ones left to room entry. |
| 6 | Separate stays separate | ✅ Level, XP, spells, subweapon and equipped items unchanged in B. Gold is pooled now (D38): ✅ `gold_pooled`, +400 in A shows in B, −150 in B shows in A. |
| 7 | Exactly once, converges | ✅ `exactly_once_partition`: the network drops everything while A takes two pickups, and B gets each exactly once afterwards. ✅ `soak_30min`: 30 minutes of random play in both games, no event dropped, and flags, map and gold identical at the end. |
| 8 | No regressions | ✅ Every M1 test, including frame-for-frame parity with retail (`no_effect_on_play`). |

**Found while building (logged in D39–D41):**
- **US `DebugUpdate` is an empty function**, and DRA runs `UpdateGame` only if its (unset) return value is nonzero. Our hook was returning whatever our own code left in `v0`. Depending on code layout, that froze the game at its first frame of play, on SwanStation and PCSX-Redux alike. The hook now always returns true (D39). M1 only worked by luck.
- **CPU cost matters:** scanning 0xB00 bytes byte by byte every frame dropped a frame in a busy scene, so the scans now compare words (D40).
- **Restored retail's 150 blank sectors after the XA music stream** (`COOPPAD.`), so `COOP.BIN` sits where retail's data track ends (D41). It didn't cause the freeze, but now the end of the disc matches retail.
- **Not built:** the 2 s "Partner found: …" notice (D42).
