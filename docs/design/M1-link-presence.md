# M1 design: Link + presence

**Status:** approved 2026-10-18; built, all criteria pass (results at the end).
**Budget:** 15% of the month. Target: 2026-10-23.
**Context:** D19–D31, `ROADMAP.md`, and `research.md` → "Independent exploration".

## Goal
Two copies of the game, each with the co-op module loaded from boot, connected by a link. Each game knows where its partner is.
- **Same room:** the partner appears as a tinted Alucard who animates exactly like the real one.
- **Map screen:** the partner shows as a second marker.

M1 delivers nothing else, so no shared progression, teleport, enemies or menus. But M2–M5 all build on this plumbing: the loader, the mailbox, the host, the adapter, and the two-game test harness.

## Part 1: getting co-op code into memory
This is option **B from the withdrawn M1 design** (D29), now verified:
- The module is linked into DRA's build as an extra section with run address `0x80280000` (the 8MB area), stored after DRA's data in `DRA.BIN`.
- `main.exe` loads `DRA.BIN` with a single read of its real size into `0x800A0000` (`src/main/main.c`). Today that read ends at `0x801B9870`, and the next file (`F_MAP.BIN`) loads at `0x801E0000`. That leaves **about 157 KB** for the module payload, which only lives there until it's copied up.
- **Copy step:** at DRA start-up, the hook turns on 8MB, copies the payload up, and calls `FlushCache()` (D17).
- **Disc build:** upstream's disc build already regenerates file positions on the disc (`build_disc.sh` → `sotn.sh disk`), so a larger `DRA.BIN` is fine. The `TT_000.BIN` familiar trick from M0 is retired.

**Upstream hooks:** four, all inside `#ifdef COOP`, plus a build switch. With `COOP` off, the matching build is still 115/115.

| Hook | Where | Calls |
|---|---|---|
| Start-up | DRA initialization | `CoopInstall()`: 8MB, copy, flush |
| Per frame, before the game update | main loop (`src/dra/42398.c`, where M0 patched the `DebugUpdate` call) | `CoopUpdate()`: read inbox, write outbox |
| After `RenderEntities()` | same loop | `CoopRender()`: draw the puppet |
| End of `DrawMapCursor()` | `src/dra/5087C.c` | `CoopDrawPartnerCursor()` |

## Part 2: the game ↔ host mailbox

| Option | Idea | Verdict |
|---|---|---|
| **A. Mailbox in RAM** | A fixed-address `CoopLink` struct in the module. The game writes `self` and the outbox; the host writes `partner` and the inbox. The host touches it only **between frames**, when the emulator is paused, so no locking is needed. | ✅ **Recommended.** It works the same on every emulator that can read and write RAM (R1), and all game knowledge stays in C. |
| B. Host pokes game globals directly | The host writes positions and flags straight into game RAM | ❌ Game internals would leak into Python, and every hook would become emulator-timing-sensitive. |
| C. Emulated link cable (SIO) | Use the PS1 serial port | ❌ Few emulators emulate it, and it would need driver code in the game. |

**Layout (M1 subset):** `magic, version, frame, self: Presence, partner: Presence, partner_age`, plus empty event rings in each direction that M2 will use.

**`Presence`** (about 32 bytes):
- character
- stage, and room (`g_Tilemap.left/top`)
- room position (`g_PlayerX/Y`)
- `animSet`, `animCurFrame`, `facingLeft`, `palette`, `drawFlags`, `zPriority`
- a "visible" bit (off during the menu, a stage load, or a cutscene)

## Part 3: host, adapter, and the two-game harness
New Python package `mods/co-op/link/`:
- **`adapter.py`:** the emulator interface: read/write bytes, step one frame, set pads. It has one implementation now, around the harness's SwanStation `Emu`. R1 swaps or adds another.
- **`host.py`:** one per game. Each frame it reads `self` and sends it to the peer, then writes the latest partner presence into `partner`.
- **`transport.py`:** messages over UDP. On localhost for now; the same code works across a network later (online play is M6/M7).
- **Session harness** (`harness/session.py`):
  - Runs two worker processes (one libretro core per process). Each worker has its own game and host.
  - A driver steps both games frame by frame, sends both pads' inputs, and reads both games' state, so tests can assert across both games.
  - Output is a side-by-side GIF of both screens.

## Part 4: drawing the partner (puppet)

| Option | Idea | Verdict |
|---|---|---|
| **A. The module draws it** | `CoopRender()` adds one textured quad, using the same code path `RenderEntities()` uses for Alucard's body: look up the frame in his animation set, upload the sprite frame to VRAM, then draw the polygon. It has its own `PlayerDraw`-style VRAM slot, and a color blend for the tint. | ✅ **Recommended.** It occupies no entity slot, so nothing in the game can spawn over it, update it, or collide with it. About 100 lines, all in the module. |
| B. A puppet entity | Put the partner in a spare slot of `g_Entities` with no update function | Needed later: M4 needs the partner to be hittable. In M1, a slot could be taken by the game's own effects in the meantime (unproven). Deferred to M4. |

**What the code shows** (`src/dra/4B758.c` `RenderEntities`):
- Alucard's frames come from `ARC_F` (always resident in Alucard mode). Each frame is uploaded into a per-slot VRAM rectangle, `g_PlayerDraw[n].rect0`, every time it changes.
- Slot table `D_800A21B8`: slot 0 is Alucard's body, slots 1–3 are his after-images, and slots 4–7 point at the same area as slot 0.
- The puppet needs **its own free VRAM rectangle**: 128×128 at 4bpp, plus a 1-pixel border.
- `PlayerDraw.enableColorBlend` with per-vertex RGB already tints a sprite, so the tint needs no palette work.

**Position:** partner room position − my camera scroll, drawn at the partner's `zPriority`. It's drawn only when stage and room match and `visible` is set.

## Defaults (reversible, logged when built)
- **Tint:** blue-grey (RGB 0x60/0x70/0xA0).
- **M1 draws the body only.** No sword or shield sprite, spell effects, or after-images.
  - Bat form shows if its sprite path (`animSet` 13) is as simple as it looks. Wolf and mist are hidden until M4.
- **Stale partner:** if `partner_age` goes over 30 frames, the puppet fades out, and the map marker blinks slowly.
- **Map marker:** the same cursor graphic as the player's, with a different palette (`g_ClutIds`), drawn after the player's cursor.

## Spikes first (about 0.5 day, before full implementation)
1. **Free VRAM:** dump VRAM across the test route (entrance, Alchemy Lab, Marble Gallery, Outer Wall) and look for a 32×132-halfword rectangle that's never written. If there isn't one: reuse after-image slot 3 and suppress P1's after-images while the partner is visible.
2. **Two-game skeleton:** two worker processes plus a UDP relay, stepping 10,000 frames. Measure frames per second and latency.

## Acceptance criteria (session-harness tests unless noted)
1. **Loader:** on the co-op disc, the module is resident and its heartbeat ticks from boot through the title screen into a new game, with no familiar involved. Checked on SwanStation and PCSX-Redux (headless).
2. **No regression with `COOP` off:** the matching build is still 115/115.
3. **No effect on play:** with the partner absent, `walk_entrance_rooms` gives the same room path and positions on the co-op disc as on retail.
4. **Presence:** both games start from the entrance savestate. Game B's `partner` field matches game A's `self` (stage, room, position, pose) within ≤ 2 frames, through a scripted walk, jump and crouch in game A.
5. **Puppet visible and correct:**
   - In the same room, each game's screenshot shows the tinted partner at the partner's real screen position (pixel check). There's a side-by-side GIF.
   - In different rooms, no puppet is drawn.
6. **Map marker:** on the map screen, game A shows a second cursor at B's room (pixel check).
7. **Stale link:** if game B's process is killed, A keeps running. The puppet disappears within 1 s, with no crash.
8. **Soak:** 10 minutes, both games, random input, rooms shared some of the time. No crash. Game A's game state evolves identically with and without the link running. "Game state" means entities, `g_Player`, `g_Status`, castle flags and the random number generator, but not the GPU buffers or the mailbox. That proves the link only draws, and never changes game state in M1.
9. **Manual (Tucker, about 5 min, optional):** watch the side-by-side GIF. A real-time two-pad launcher is part of M6.

## Risks
- **Free VRAM** varies by stage. The spike settles it, and the fallback is above.
- **Pose fidelity:** some Alucard moves draw extra parts as separate entities (weapon arc, cape pieces?). The body-only puppet may look incomplete in some poses. That's acceptable for M1, and the full part list is an M4 item.
- **Upstream build plumbing:** adding a section to DRA touches `tools/builds/gen.py`. Keep the change flag-gated and small. Fallback: a separate `COOP.BIN` loaded from DRA start-up (option C in the old doc).
- **Harness speed:** two cores at about 25× each should be fine. The spike confirms it.

## Decision for Tucker
Approve the loader, the mailbox (A), the module-drawn puppet (A) and the defaults above, or redirect.

## Results (2026-10-18)
| # | Criterion | Result |
|---|---|---|
| 1 | Loader | ✅ SwanStation: `loader_from_boot` (module resident at the title, heartbeat = `g_Timer` = every frame since boot) and `loader_in_game` (600 beats per 600 frames at the castle entrance, after a full new game and prologue). ✅ PCSX-Redux, headless (`redux_check.sh`): resident at the title (heartbeat 312 = `g_Timer` 312), then +587 beats over 587 game frames at the entrance. No familiar involved. |
| 2 | `COOP` off still matches | ✅ `build_disc.sh` ends by rebuilding the plain build: `✅ us`, and `doctor.py` is all green. |
| 3 | No effect on play | ✅ `no_effect_on_play`: game B (co-op disc) first takes game A's (retail) main RAM, keeping only its 4 hook calls, then both walk the `walk_entrance_rooms` route. Identical stage, room, position and HP on all 3,800 frames, through 20,39 → 14,40 → 11,40. |
| 4 | Presence, ≤ 2 frames | ✅ `presence_follows`: through walk, jump, crouch and turn (220 frames, 10+ poses, both facings), B's partner equals A's presence after every frame. A gets B's one frame later. The puppet is drawn on the next frame: 1 frame behind for B, 2 for A. |
| 5 | Puppet visible, tinted, same room only | ✅ `puppet_same_room_only`: in each game, a with/without render shows the partner's pixels at the partner's real screen position, tinted blue. After A walks to another room, B draws nothing. Side-by-side GIF in `.env/out/puppet_same_room_only/clip.gif`. |
| 6 | Map marker | ✅ `map_marker`: on B's map screen (Marble Gallery), a second cursor appears on A's map cell. |
| 7 | Stale link | ✅ `stale_link`: B's process is killed. A keeps playing, its partner goes stale, and it stops drawing B within 1 s. |
| 8 | Soak, and the link never changes game state | ✅ `soak_10min`: 36,000 frames per game of random input, sharing a room part of the time, in 90 s. Then A's inputs are replayed alone, with no link. All 60 checks of entities, player, status, castle flags, RNG and the BIOS kernel area match. |
| 9 | Manual | Optional: watch the side-by-side GIF. |

All 10 scenarios: `harness/run.py` (the 10-minute soak runs by name: `run.py soak_10min`).

**What changed from the design (all logged in `DECISIONS.md`):**
- **The loader is option C, not B (D32).**
  - DRA has **no spare room**: its code and BSS end exactly where its fixed-address data block begins (`0x8013B6A0`). So the hooks can't add code. Each hook retargets an existing call instead, which is size-neutral (D33).
  - Making `DRA.BIN` bigger than its last CD sector **shifts every later file on the disc**. The FMVs are then read from their old sector positions and boot hangs.
  - So `DRA.BIN` only gains a 184-byte boot stub, inside its last sector. The stub loads `COOP.BIN`, a new file placed after every retail file. `check_disc_layout.py` now fails the build if any retail file moves (D34).
- **Puppet VRAM:** a VRAM scan across 4 stages found a texture page that's never used, at `(0x1C0, 0x100)`, so the fallback wasn't needed. Other stages aren't scanned yet (risk below).

**New risks:**
- The puppet's VRAM page is only proven free on the 4 test stages. A stage that uses it would show a corrupted partner sprite (cosmetic only). Cheap fix: extend the scan to every stage when the route grows (M2/M3).
- The module now has a size budget of 8MB minus the base, and the boot stub has about 1.7 KB left. Neither is a constraint in practice.
