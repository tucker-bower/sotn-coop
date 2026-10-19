# Research notes

> **2026-10-18 pivot.** The goal is now independent exploration with one game instance per player (D19, D20). The section right below is current. The older sections assume one shared instance, so read them as background.

## Independent exploration (D19–D31)

### Why each player gets their own instance
SOTN keeps exactly one stage resident. Two players in different areas can't share one game:
- **Stage code:** the stage overlay always loads at `0x80180000`.
- **VRAM:** 1MB holds one stage's tiles, the sprites and the framebuffers. There's no room for a second stage or a second view.
- **Sound:** SPU RAM holds per-stage sound banks.
- **Disc loading:** stage loads stream from the CD and pause play.
- **Single world:** the camera, the scrolling tilemap, room-layout entity spawning and the renderer all assume one world and one view.

With one instance per player, all of that stays stock. The work moves to *syncing* the two worlds.

### Pieces
- **In-game module** (8MB area, loaded as an extra DRA section, D29):
  - Reports events and state into an outbox.
  - Applies the inbox at safe points in the frame.
  - Draws the partner puppet.
  - Runs teleports, respawns and pause rules.
- **Mailbox:** fixed-address ring buffers in the 8MB area, one in each direction, with a sequence counter. The host reads and writes it once per frame through the emulator adapter.
- **Host** (Python, one per instance):
  - Merges shared state.
  - Relays presence.
  - Owns the session file (joint save).
  - Talks to the partner's host: a local socket for couch play, the network for online.
- **Emulator adapter:** needs RAM read/write, a per-frame callback and pad input. The harness already does all three for SwanStation (`harness/emu.py`).

### Shared state: where it lives (codebase)

| What | Where | Merge rule |
|---|---|---|
| Castle flags (walls, doors, switches, bosses, pickups, cutscenes) | `g_CastleFlags[0x300]` (`include/castle_flags.h`, `0x8003BDEC`) | Mostly set-only, so merge as a **union**. Any flag that gets cleared or counts has to be found and handled as an exception. |
| Explored map | `g_CastleMap[0x800]` | Bitwise OR |
| Relics | `g_Status.relics[NUM_RELICS]` (`0x80097964`) | "Owned" is shared. Each player's on/off toggle stays their own. |
| Equipment | `g_Status` inventory counts | **Add-on-find events** ("+1 Alucard Sword"), not a state merge, so each player gets their own copy. |
| Max HP/MP/Hearts upgrades | `g_Status` max fields | Events ("+5 max HP") |

Events work better than diffing whole structures. A diff can't tell "P2 found a second potion" from "P1 used one". For flags, the union of both sides is simple and order-independent, so the two worlds always converge.

### Live room refresh (D22)
- Flags set elsewhere affect only entities spawned *after* the change, because entities read their flag when they spawn.
- To make a change show up in the room the partner is already in, the module needs a per-entity-type refresh. Each flag-gated entity type is mapped to one of:
  - despawn it (a pickup that's now taken)
  - put it in its "already done" state (a wall that's now broken)
  - rerun its init
- The list of entity types that check `g_CastleFlags` comes from the codebase (grep the stage sources). This is the bulk of M2.

### Shared rooms: the same enemies (D23), to be decided in the M4 design
- **A. Room authority (leading candidate).**
  - The first player in the room becomes the room's **authority**. That game runs the enemies as normal.
  - The other game stops updating its own stage entities and **mirrors** the authority's entity slots 64–255 each frame. The rendering state those slots point to (primitives) has to be mirrored too.
  - This works because both games run the same binary and the same stage overlay, so function pointers and data addresses are identical. Raw entity copying is plausible.
  - Hits on mirrored enemies go to the authority as damage events.
  - The authority's game has the partner as a puppet with a hurtbox. Enemy hits on it go back as damage events.
  - Enemy targeting uses the `st_common.h` helpers (see "Enemy targeting" below), changed to pick the nearest player, which includes the puppet.
  - It tolerates latency: the guest's enemies lag by one round trip, and that's acceptable online.
  - Each player still runs only their own character, so mixed characters keep working.
- **B. Lockstep merge.**
  - When both players are in one room, both games simulate *both* players in lockstep. The second player runs through the context swap (withdrawn M1 design, D29).
  - Needs exact state equality on room entry, and rollback or input delay online.
  - Every game must be able to run every character's code, which brings Richter's relocation back.
  - It's the most faithful option, and the most costly.
- **The biggest risk either way:** hand-over when the authority player leaves the room or dies, and enemies that read the player directly (about 135 places).

### Bosses and cutscenes (D25, D26)
- **Boss-room entry:** the boss rooms are known from the stage room tables. On entry, the module sends a "join me" event, and the partner's host triggers a teleport.
- **2× boss HP:** boss HP comes from the enemy definitions (`EnemyDef.hitPoints`). The module doubles it for boss IDs when the boss spawns while co-op is active. Bosses made of several parts need checking boss by boss.
- **Cutscenes:**
  - The trigger player's game sends "cutscene X in room R". The partner is teleported in, and the cutscene's own trigger then runs in both games.
  - Credit comes from the flag union.
  - Open question: cutscenes that move or lock "the player" while a second player is around. Lean: the puppet hides during cutscenes.

### Teleport and respawn (D24, D30)
- The game already loads a stage and room at a given position in two places: warp rooms, and loading a save. The harness uses the debug module's stage load (`savestates.warp`). Teleport reuses that path.
- A safe landing spot near the partner = the partner's position. If that's mid-air or inside a wall, use the partner's last grounded position.
- Inverted castle stages are separate stage IDs, so the teleport has to pick the right one.

### Mixed characters (D27), open until M7
Richter mode (`g_PlayableCharacter`) changes the world: candle drops, some cutscenes, and whether items and relics exist. The unanswered question is which mode the world runs in when Alucard and Richter share a save, and what shared relics or equipment mean to Richter. The puppet needs the partner's sprite sheet in the 8MB area: `ARC_F.BIN` is 208KB, and Richter's sprites live in `RIC.BIN`.

### Product emulator (R1, decided with Tucker separately)
Requirements:
- 8MB mode.
- RAM read/write from outside, every frame, with low latency.
- Two instances at once.
- Pad routing (pad 1 → instance 1, pad 2 → instance 2 on one PC).
- Savestates.
- Windows, ideally Linux. Android (Thor) is a nice-to-have.

Candidates to evaluate:
- **Our own libretro frontend** around SwanStation. The harness already is one. We get full control, and both screens in one window is possible.
- **RetroArch** network commands (`READ_CORE_MEMORY`/`WRITE_CORE_MEMORY`): Android-capable, but polling over UDP may be too slow.
- **PCSX-Redux** (Lua plus a web server).
- **BizHawk** (Lua; the SOTN randomizer community uses it).
- DuckStation has no scripting, so it's out unless that changes.

### Findings from building M1 (2026-10-18)
- **DRA has zero spare bytes.** Its code and BSS end exactly at `0x8013B6A0`, where the fixed `dra_data` block (the `ARC_F` area) starts. Hooks must retarget existing calls (D33).
- **Retail files must keep their sector positions.** One extra sector in `DRA.BIN` shifted every later file, and boot hung in the intro FMV, which is read from a fixed sector. `lba_us.h` was regenerated correctly, so the fixed position lives somewhere `lba.h` doesn't cover (not tracked down). New content goes in `COOP.BIN` after the retail files (D32, D34).
- **Free VRAM:** the texture page at `(0x1C0, 0x100)`–`(0x1FF, 0x1FF)` is never written in NO3, NZ0, NO0 or NO1 (VRAM sampled every 30 frames while walking). It's at offset 8,920,275 in SwanStation's savestate, right after the BIOS copy.
- **`rand()` is a BIOS call** (A0 table 0x2F), so its seed lives in the kernel area. The BIOS thread context (`[0x80000110]`, the registers saved at each interrupt) shifts with any code change, so state comparisons must exclude it.
- **The map screen opens on Select** whenever pausing is allowed. It's `g_GameEngineStep` 20 (`Engine_Map`), and the cursor is drawn only while `g_canRevealMap` is set.

### Findings from building M2 and M3 (2026-10-19)
- **US `DebugUpdate` returns nothing** (`jr ra`). The main loop branches on a stale `v0`. See D39.
- **Pickups:** item drops (`E_PERSISTENT_ITEM_DROP`, `0x0C`) and relic orbs (`0x0B`) have the same IDs in every stage. A drop's collectible flag index is at entity offset `0xB4`. `g_ItemIconSlots` is per stage, so a despawned drop keeps its icon slot until the next stage load.
- **Layouts:** `assets/st/<stage>/entity_layouts.json` has `entities` (lists) and `indices` (`objLayoutId` → list). A room's `objLayoutId` is in its `RoomHeader` (`g_api.o.rooms`, 8 bytes each, ending at `left == 0x40`). A standing player's y is about 18 px above an item resting on the same floor.
- **Death:** HP 0 alone doesn't kill. A hit does. The engine goes to `Engine_10` when `g_Player.status` has `0x80000` (death animation over), and `Engine_10` at `MENU_STEP_INIT` is the last frame before Game Over.
- **Loads:** `ApplySaveData` + `D_8003C730 = 1` + `Game_NowLoading`/step 2 is the card-load path, from the title or from play. `InitStatsAndGear` keeps the status when `D_8003C730` is set. Door transitions: `D_8006C374` indexes `D_800A245C` (131 entries, `{x, y, roomId, unk6, stageId}`), and `g_RoomBossTeleports` follows it (M5).
- **Flag-gated objects** (secret walls etc.) apply their flag in their init step, so re-running init with `step = 0` updates them. Breakable walls use the enemy fields (`enemyId` ≠ 0) to be hittable.

### Findings from building M3b and M4 (2026-10-19)
- **Save rooms** are marked by a room layer flag (`D_8003C708.flags & 0x20`), not an entity.
  - Alchemy Lab save rooms: room IDs 184, 192, 200. Marble Gallery: 248, 256.
  - In the coffin, Up heals and saves with no further input. The card save is the static state machine at `0x80103ED4` (reset `0x80103EAC`), with state 6 = saved and 7–11 = card errors.
  - The title's Load path: Start → ✕ (File select) → ✕ on the save.
  - SwanStation exposes memory card 1 as libretro save RAM (128 KB).
- **The stage's layout spawner** is `g_api.o.UpdateRoomPosition` (offset 8). It only creates entities in a window from 64 px left of the camera to 320 px right of the camera's left edge as the camera scrolls.
- **Entities and primitives are camera-relative.** The engine shifts `FLAG_POS_CAMERA_LOCKED` entities (and parallax ones by `unk68`) by the scroll delta every frame.
- **Targeting helpers** `GetSideToPlayer` and `GetDistanceToPlayerX/Y` are in all 52 stage and boss overlays (addresses in their maps). `GetPlayerCollisionWith` is platform collision, not targeting.
- **The castle entrance hall** (NO3 14,40) has zombies and a Warg idling just left of the entrance. The Warg wakes on player distance.

### Prior art lead (unverified)
TalicZealot's **SotnRandoTools** (BizHawk external tool, now maintained as `SotnRandoTools_C4B`) is believed to have had an online co-op mode that shares relics, items and warps between separate games. A web search on 2026-10-18 didn't confirm it. If it's real, its RAM-address list and merge rules are worth reading before M2.


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

**Implication for P2 = Alucard (from the old one-instance plan, before D20):** a second Alucard can share all of the engine code and the spritesheet. The new memory cost is mostly *state* (one more `PlayerState` plus entity slots), not code or graphics. That's the cheapest possible case.

## Player architecture (codebase)
- `PLAYER` is a macro for `g_Entities[0]`. `g_Player` is a single global `PlayerState` (0x3D0 bytes, about 1 KB).
- DRA references `PLAYER.` about 1,700 times and `g_Player.` about 900 times. Player logic is hard-wired to a single player. Parameterizing it would be a huge diff.
- Entities: there are 256 slots in total. Slots 0–63 are reserved for the player and its effects, and stage entities start at 64. Alucard's weapons, subweapons and effects spawn in the player range.
- **Candidate approach ("context swap"), withdrawn as the P2 plan by D29 and kept as an option for shared rooms:** run the player update twice per frame. Before the second pass, swap in P2's saved `g_Player`, entity 0, the pad state, and P2's sub-entity range, then swap back afterwards. This touches very little upstream code. The unknowns are the globals that player code writes besides `g_Player` (camera, map position, room-transition triggers) and how enemies pick a target (they read `PLAYER` directly). This is the leading candidate for the M1 design doc.
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

## SwanStation on Android (checked 2026-10-18)
- The libretro buildbot ships a nightly `swanstation_libretro_android.so` for arm64-v8a (latest build 2026-10-18). It installs from RetroArch's built-in core downloader, with no sideloading.
- The upstream repo (libretro/swanstation) is active, with commits as recent as 2026-10-15, including savestate-correctness fixes that matter for netplay rollback.
- It's a libretro fork of DuckStation from before DuckStation's licence change, so it shares the 8MB support and the accuracy lineage.
- Risk: commit notes say frame replay is identical "on the interpreter". Whether the recompiler is identical too is unverified. RetroArch netplay rollback needs deterministic replay, so M5 has to test netplay with the default (recompiler) CPU mode, and fall back to the interpreter if needed. The Thor has enough CPU headroom for that.
- The only Android cost: ReARMed is RetroArch's default PS1 core, so users have to pick SwanStation once. The M5 instructions will cover that.

## Dracula X Chronicles USA vs EU (checked 2026-10-18)
- Tucker's copy is **ULUS-10277**, from `UMD_DATA.BIN`. The decomp builds and extracts from the EU release, ULES-00841.
- Hashing `PSP_GAME/USRDIR/res/ps/PSPBIN/*.bin` against `config/check.pspeu.sha`: 0 of 65 are identical. They're the same `MWo3` overlay format at the same paths, but a different build (the USA files are dated Sep 2007).
- `maria.bin`: the USA file is 212,864 bytes, against roughly 259,840 for the EU one (from the splat segment end 0x3F700). The EU file has font_eu and HUD graphics in 5 languages, so every asset offset in `config/assets.pspeu.yaml` shifts.
- `res/ps/hdbin/*`: all 14 match `config/check.hd.sha`.
- Conclusion → D15.

## Emulator automation (checked 2026-10-18)
- **PCSX-Redux** (Windows, nightly 608 = the same commit as our OpenBIOS) runs headless with `-cli -8mb -fastboot -bios … -iso … -run -dofile x.lua`. The Lua API gives `PCSX.getMemPtr()` (RAM via ffi), `GPU::Vsync` events, `SIO0.slots[n].pads[1].setOverride(button)` and `PCSX.quit(code)`. Its stdout doesn't reach WSL, so results go to a file. A full route takes about 5 min (real time).
- **DuckStation** has no scripting or headless mode. It's portable when `portable.txt` sits next to the exe, and `settings.ini` takes the same option names as SwanStation's (`Console/Enable8MBRAM`, `BIOS/PathNTSCU`).
- **SwanStation** detects self-modifying code by itself. PCSX-Redux's dynarec doesn't: code written by the CPU only runs after `FlushCache()`. That's real-hardware behavior too.
- Libretro: a core can only be loaded once per process, so the lockstep check uses two processes.
