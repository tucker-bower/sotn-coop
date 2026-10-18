# Research notes

Sources: the sotn-decomp codebase, the project wiki, and the related repos below. Discord notes are pending until a login is available.

## Memory layout (wiki: Internals)
Alucard mode:

| Range | Contents |
|---|---|
| `80010000–8009FFFF` | `main.exe`: SDK and shared memory |
| `800A0000–8013BFFF` | `DRA.BIN`: engine, including all of Alucard's player logic |
| `8013C000–8016FFFF` | `ARC_F.BIN`: Alucard spritesheet (208 KB) |
| `80170000–80179FFF` | Familiar program (`SERVANT/TT_*`) |
| `8017A000–8017FFFF` | `WEAPON0` / `WEAPON1`: right- and left-hand equipment code |
| `80180000–801DFFFF` | Stage overlay |
| `801F0000–801F7800` | Heap |

Richter mode replaces `ARC_F` + servant + weapons (`8013C000–8017FFFF`) with `RIC.BIN`. That confirms D3: Alucard + Richter at the same time means relocating Richter.

**Implication for P2 = Alucard:** a second Alucard can share all of the engine code and the spritesheet. The new memory cost is mostly *state* (one more `PlayerState` plus entity slots), not code or graphics. That's the cheapest possible case.

## Player architecture (codebase)
- `PLAYER` is a macro for `g_Entities[0]`. `g_Player` is a single global `PlayerState` (0x3D0 bytes, about 1 KB).
- DRA references `PLAYER.` about 1,700 times and `g_Player.` about 900 times. Player logic is hard-wired to a single player. Parameterizing it would be a huge diff.
- Entities: there are 256 slots in total. Slots 0–63 are reserved for the player and its effects, and stage entities start at 64. Alucard's weapons, subweapons and effects spawn in the player range.
- **Candidate approach ("context swap"):** run the player update twice per frame. Before the second pass, swap in P2's saved `g_Player`, entity 0, the pad state, and P2's sub-entity range, then swap back afterwards. This touches very little upstream code. The unknowns are the globals that player code writes besides `g_Player` (camera, map position, room-transition triggers) and how enemies pick a target (they read `PLAYER` directly). This is the leading candidate for the M1 design doc.
- `g_pads[PAD_COUNT]` already reads both controller ports.
- The PS1 build has an existing debug header that refers to pad 2: `src/st/pad2_anim_debug.h`. Worth checking for how the developers used port 2.

## PC port (wiki: PC-Port, `src/pc`)
- It's work-in-progress, not end-to-end. It builds with CMake: `./build/pc/sotn --disk disks/sotn.us.cue --stage nz0 --player 2`.
- It can jump directly into a stage (`--stage`) and run boss demos (`--demo N`, 0–28), which are ready-made test scenarios.
- `src/pc/replay.c` records inputs plus a periodic "drift check" of state. That's essentially a determinism harness already.
- **Harness implication:** the PC port is a strong candidate for fast iteration in M0–M2, but it isn't proof that the PS1 build works. Final validation must run on a real PS1 emulator. The M0 design should compare the two options.

## Prior art
- **Maria PSP→PSX mod** (`mods/mariapsp-forpsx`): the in-tree example of how a mod is structured, built and patched.
- **sotn-player-mmx** (github.com/Xeeynamo/sotn-player-mmx): a custom player character (Mega Man X). It shows palette injection into `g_Clut` and per-frame palette uploads. Relevant to tinting P2.
- No existing co-op or multiplayer work was found in the repo or wiki.

## Discord
_Pending: needs a Discord login in Claude's browser pane._ Plan: read pins and resources channels, and search for: multiplayer, co-op, "player 2", pad2, netplay, "second player", "pc port", replay, determinism.
