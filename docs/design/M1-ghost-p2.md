# M1 design: Ghost P2 (Alucard) and a real module loader

**Status:** ⛔ **withdrawn 2026-10-18** (D29). The goal changed to independent exploration with one game per player (D19, D20). Part 1, option B (the extra DRA section loader), carries over into the new M1. Part 2 (the context swap) is kept only as option B for shared rooms in M4. This document is kept for the record.
**Budget:** 13% of the month. Target: 2026-10-26.

## Goal
Pad 2 controls a second, tinted Alucard who walks, jumps, crouches and turns alongside P1. He's a "ghost": no combat yet, and the world interacts only with P1. Co-op code loads on every new game with no familiar trick, and it stays netplay-deterministic.

## Part 1: how co-op code gets into memory
M0 found that the familiar slot only loads while a familiar is active, so it can't carry co-op code.

| Option | How | Verdict |
|---|---|---|
| A. Familiar slot (M0) | Ship as `TT_000.BIN` | ❌ Needs the Bat familiar active, and it loses the Bat. |
| **B. Extra DRA section** | Link the module *into* DRA's build as a section with run address `0x80280000`, stored after DRA's data in `DRA.BIN`. `main.exe` loads `DRA.BIN` by its real size, so the payload lands in the stage-overlay area (unused at boot: `0x801B9870–0x801E0000`, about 157 KB). A few lines at DRA start-up enable 8MB, copy it up, and call `FlushCache()`. | ✅ **Recommended.** One link, so DRA hooks call module functions by name (type-checked, no hand-patched `jal`). No new disc file, no CD code. |
| C. Separate `COOP.BIN` | DRA start-up reads a new disc file into 8MB (like `main.exe` reads `DRA.BIN`) | Fallback if B's 157 KB runs out (e.g. M2's Richter relocation). More code, plus CD timing at start-up. |

**Why B is safe:** DRA's own layout isn't fixed from outside. Other overlays hardcode only 2 DRA addresses (its header at `0x800A0000` and `g_SfxScripts` in early data), and neither moves. Everything else reaches DRA through runtime tables (`g_api`).

**Upstream diff:** about 2 small hooks in `src/dra` (start-up copy, per-frame call) behind `#ifdef COOP`, plus a build-script switch. With `COOP` off, the matching build stays 115/115 (CI-style check in the harness).

## Part 2: how P2 works

| Option | Idea | Verdict |
|---|---|---|
| **A. Context swap** | Each frame, after P1's `EntityAlucard()`: save P1's player entity, `g_Player` and a short list of player globals, load P2's, point the pad at port 2, run the **real** `EntityAlucard()`, then swap back. | ✅ **Recommended.** Real Alucard physics and animations for free. It's the same mechanism M2 needs for Richter (who must run his real code). Small upstream footprint. |
| B. Puppet entity | P2 is a custom stage entity with simple hand-written movement and Alucard sprites | Cheap, but fake movement, and thrown away in M2. |
| C. Parameterize DRA's player code | Turn `PLAYER`/`g_Player` into per-player pointers | ❌ About 2,600 references, so a huge diff that's painful to rebase. |

**What the code showed** (`src/dra/5087C.c`, `4B758.c`):
- **Frame order:** `HitDetection` → `EntityAlucard` → `UpdatePlayerEntities` (slots 4–63) → `UpdateRoomPosition` (camera and room from slot 0) → stage entities.
  - The swap slots in right after P1's `EntityAlucard`.
  - Because P2 is swapped out whenever hit detection, the camera and stage entities run, the world ignores P2 by construction. That's exactly the "ghost" behavior, with no extra code.
- **Rendering:** P2 must sit in `g_Entities` when the frame is drawn. Between frames P2 lives in a spare entity slot, with a no-op update function so nothing else runs him.
- **Sprites:** the player's current frame is uploaded into VRAM each frame through `g_PlayerDraw[entity->unk5A]` (16 slots). P2 gets his own slot and VRAM area, so the two Alucards don't overwrite each other.
- **Tint:** P2 gets his own palette (CLUT), the technique `sotn-player-mmx` uses.

**Defaults (reversible, logged when built):**
- The camera follows P1.
- If P2 is off-screen for 1 s or P1 changes rooms, P2 respawns next to P1.
- P2 joins by pressing Start on pad 2 and drops out by holding Select.
- P2's dust and after-image effects are suppressed in M1, because they attach to slot 0. Fixing that properly belongs with combat in M3.

## Acceptance criteria (all harness tests unless noted)
1. **Loader:** on the co-op disc, the module is resident and its heartbeat ticks from the title screen through a new game, with no familiar involved. That holds on SwanStation and PCSX-Redux (headless).
2. **No regression with `COOP` off:** the matching build is still 115/115.
3. **P1 unaffected while P2 is absent:** the `walk_entrance_rooms` inputs give P1 the same room path and positions on the co-op disc as on retail.
4. **P2 controls:** from the entrance savestate, pad 2 scripts walk left and right, jump, crouch and turn. P2's position, facing and pose change as expected (RAM assertions), and P1 doesn't move.
5. **Visible and tinted:** a screenshot shows two Alucards, one tinted (pixel check plus GIF).
6. **Leash:** P2 respawns next to P1 after 1 s off-screen and after a P1 room transition.
7. **Determinism:** 10-minute lockstep with random input on both pads and P2 active: 0 desyncs, no crash.
8. **Manual (Tucker, about 5 min):** a two-pad session on DuckStation feels sane (P2 moves, no flicker or crash).

## Risks
- **Hidden player globals:** `EntityAlucard` may write state outside the swap list (statics, timers, `g_PlayerX/Y`). Mitigation: a harness "swap-purity" test diffs RAM around P2's update, then grows the list until P1's behavior with P2 present matches P1 alone.
- **Shared random numbers:** P2's update may consume random numbers and change enemy behavior. That's acceptable (still deterministic), but criterion 3 is only checked with P2 absent.
- **Build plumbing:** adding a section to DRA touches upstream's build generator (`tools/builds/gen.py`). Mitigation: keep it to a small, flag-gated block. Fallback C if it gets ugly.
- **CPU cost:** a second `EntityAlucard` per frame. That's fine in emulators, and it can be measured with the harness. Real hardware isn't a target (D5).

## Decision for Tucker
Approve loader **B** plus P2 approach **A** and the defaults above, or redirect.
