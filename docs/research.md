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

## Enemy targeting (codebase), which addresses the biggest risk
The maintainer's view (Discord, below) is that enemies only interact with player 1. Most enemy AI, however, reads the player through **shared helpers in `src/st/st_common.h`**, which are compiled into every stage:

| Helper | Call sites (stages + bosses) |
|---|---|
| `GetSideToPlayer` | 419 |
| `GetDistanceToPlayerX` / `Y` | 350 |
| `GetPlayerCollisionWith` | 111 |
| Direct `PLAYER.posX/posY` / `g_Entities[0]` | about 135 |

If those helpers are made to target "the nearest player" (or a per-enemy chosen target), roughly 85% of the targeting logic gets multi-player awareness from one small change. The remaining ~135 direct reads get fixed case by case, prioritized by the route we test. Damage *to* players and hits *from* player weapons go through engine hit detection in DRA. That needs a separate audit in the M2 design.

## Discord (SOTN Decomp server, read 2026-10-18, read-only)
Channels: #runbook (rules and links), #general, #ps1-sotn, #psp-sotn, #saturn-sotn, #xbla-sotn, #rom-modding (mods built on the decomp), #decompilation, #tooling, #naming, #picci (PC port). Searched for: multiplayer, co-op/coop, "player 2", 8MB, PPF/xdelta, android, release.

**Co-op / multiplayer**
- **Nobody has built this.** No co-op work exists on the decomp. The question comes up every few months: May 2024, Aug 2026 ("Richter and Alucard playing through the castle together?") and Sep 2026.
- xeeynamo (maintainer), May 2024: "Yes we could add a Player 2 with a tiny bit of work, but it wouldn't be able to interact with almost anything in a map." Objects and monsters only interact with P1. That matches the targeting finding above, which is our proposed answer.
- Another member, Aug 2026: they compare it to the Super Mario 64 co-op mod. They warn that bosses would need balance changes for two players, or they'll "implode."
- **Prior art:** "Natan Vishera" made a PS1 SOTN mod, *Modo Multiplayer Co-op com Familiars v1.1* (P2 controls a familiar), plus an experimental "multiplayer with enemies" video. These are worth watching for ideas, but they're not built on the decomp. There's also a Sega Genesis fan port with a 2-player mode (Pigsy).
- Trivia: the Xbox 360 version contains unused player-2 input code.

**8MB RAM mode**
- xeeynamo: "Most of the modern emulators have the 8MB available." It's enabled by writing the RAM_SIZE register at `0x1F801060`. The project's debug module already uses 8MB.
- A rom-modding regular (2024): "Basically everyone uses 8mb mode now."
- Modders already use the trick of putting a jump in the original code and placing new code in the 8MB area. **This supports D7.**

**PC port (#picci)**
- Built on **PsyZ**, xeeynamo's PS1 compatibility framework, which is meant to target Linux, Windows, macOS, Android, iOS and more.
- Android (Aug 2026): "Would take me a day max to port it to Android." The infrastructure is in PsyZ, but it needs a separation between saves and game data first.
- Active right now (Oct 2026): boss-fight replays run in CI as determinism tests, and they're chasing per-OS nondeterminism (OS `rand()` vs Psy-Q's).
- **There is no release date anywhere.** The wiki's FAQ explicitly asks people not to ask.

**Legal / distribution**
- Precedent: the Maria mod ships as a **Docker image that builds the mod from the user's own disc images**. No game data is distributed. Its guide says "Do not redistribute any files," and derivatives must stay open source (AGPL).
- **The Maria mod requires a second disc:** *Dracula X Chronicles (EU, PSP)*, because her graphics and sounds come from the PSP version. Maria as P2 would therefore require the player to own that game too.
- PPF patches are commonly shared in the community for small fixes.
