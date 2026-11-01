# Research notes

What we've learned that the code and `TECHNICAL_SUMMARY.md` don't say: game internals, tools, and lessons that were expensive to learn. Search it rather than reading it through.

## Lessons
**Testing**
- **Test the path players use.** Android's Python has no CA certificates, so every request to the room-code relay failed silently, and the Android tests never caught it because they joined by `ip:port`. `android/test_pair.py --room` now uses the real relay.
- **A character applies from a game's next load.** The first PvP pairing tests were all two Alucards. Check that a test really runs as its character.
- **A scripted boss kill can skip the death sequence** that writes the time-attack record.
- **UI flows test the last release patch**, which `rebuild_fixtures.sh` now remakes. Before that, they tested a three-day-old build.
- **Frame-drop baselines vary between soak runs:** sessions link over real loopback UDP with wall-clock hosts. Each game stays deterministic; the soak's 0.5% tolerance covers it.
- **Android emulator hosts can't be reached in tests:** two emulators sit behind this PC's NAT, and they lost outside access after a WSL restart. The real Thor isn't affected.
- **Writes through NULL land in BIOS RAM.** Player 1's controller dying for good has been this, three different ways (M13).

**Debugging with real devices**
- **Check installed versions first.** Four rounds of a Thor connection failure came from old builds: the PC still on 0.7.1, then an APK from before the fix. Different versions now say so by name.
- `android/device.py` runs Windows adb on port 5038: the default port reaches WSL's adb server, which can't see USB.
- Logs: `session.log` in the data folder on PC, logcat through `device.py log` on Android. F9 reports include them.
- Windows RedirectionGuard crashed the launcher when the installer started it (fixed in M7b). A saved window position can land on no monitor (fixed in 0.11).

**Release**
- `release.py` uploading to an already-published v0.7.1 replaced the public installer, so it now refuses a published release.

## Where shared state lives
| What | Where | Merge rule |
|---|---|---|
| Castle flags (walls, doors, switches, bosses, pickups, cutscenes) | `g_CastleFlags[0x300]` (`include/castle_flags.h`, `0x8003BDEC`) | Mostly set-only, so merge as a **union**. Any flag that gets cleared or counts has to be found and handled as an exception. |
| Explored map | `g_CastleMap[0x800]` | Bitwise OR |
| Relics | `g_Status.relics[NUM_RELICS]` (`0x80097964`) | "Owned" is shared. Each player's on/off toggle stays their own. |
| Equipment | `g_Status` inventory counts | **Add-on-find events** ("+1 Alucard Sword"), not a state merge, so each player gets their own copy. |
| Max HP/MP/Hearts upgrades | `g_Status` max fields | Events ("+5 max HP") |

## Engine findings
### Engine and disc
- **DRA has zero spare bytes.** Its code and BSS end exactly at `0x8013B6A0`, where the fixed `dra_data` block (the `ARC_F` area) starts. Hooks must retarget existing calls (D33).
- **Retail files must keep their sector positions.** One extra sector in `DRA.BIN` shifted every later file, and boot hung in the intro FMV, which is read from a fixed sector. `lba_us.h` was regenerated correctly, so the fixed position lives somewhere `lba.h` doesn't cover (not tracked down). New content goes in `COOP.BIN` after the retail files (D32, D34).
- **Free VRAM:** the texture page at `(0x1C0, 0x100)`–`(0x1FF, 0x1FF)` is never written in NO3, NZ0, NO0 or NO1 (VRAM sampled every 30 frames while walking). It's at offset 8,920,275 in SwanStation's savestate, right after the BIOS copy.
- **`rand()` is a BIOS call** (A0 table 0x2F), so its seed lives in the kernel area. The BIOS thread context (`[0x80000110]`, the registers saved at each interrupt) shifts with any code change, so state comparisons must exclude it.
- **The map screen opens on Select** whenever pausing is allowed. It's `g_GameEngineStep` 20 (`Engine_Map`), and the cursor is drawn only while `g_canRevealMap` is set.

### Pickups, loads, death
- **US `DebugUpdate` returns nothing** (`jr ra`). The main loop branches on a stale `v0`. See D39.
- **Pickups:** item drops (`E_PERSISTENT_ITEM_DROP`, `0x0C`) and relic orbs (`0x0B`) have the same IDs in every stage. A drop's collectible flag index is at entity offset `0xB4`. `g_ItemIconSlots` is per stage, so a despawned drop keeps its icon slot until the next stage load.
- **Layouts:** `assets/st/<stage>/entity_layouts.json` has `entities` (lists) and `indices` (`objLayoutId` → list). A room's `objLayoutId` is in its `RoomHeader` (`g_api.o.rooms`, 8 bytes each, ending at `left == 0x40`). A standing player's y is about 18 px above an item resting on the same floor.
- **Death:** HP 0 alone doesn't kill. A hit does. The engine goes to `Engine_10` when `g_Player.status` has `0x80000` (death animation over), and `Engine_10` at `MENU_STEP_INIT` is the last frame before Game Over.
- **Loads:** `ApplySaveData` + `D_8003C730 = 1` + `Game_NowLoading`/step 2 is the card-load path, from the title or from play. `InitStatsAndGear` keeps the status when `D_8003C730` is set. Door transitions: `D_8006C374` indexes `D_800A245C` (131 entries, `{x, y, roomId, unk6, stageId}`), and `g_RoomBossTeleports` follows it (M5).
- **Flag-gated objects** (secret walls etc.) apply their flag in their init step, so re-running init with `step = 0` updates them. Breakable walls use the enemy fields (`enemyId` ≠ 0) to be hittable.

### Save rooms, spawning, the camera
- **Save rooms** are marked by a room layer flag (`D_8003C708.flags & 0x20`), not an entity.
  - Alchemy Lab save rooms: room IDs 184, 192, 200. Marble Gallery: 248, 256.
  - In the coffin, Up heals and saves with no further input. The card save is the static state machine at `0x80103ED4` (reset `0x80103EAC`), with state 6 = saved and 7–11 = card errors.
  - The title's Load path: Start → ✕ (File select) → ✕ on the save.
  - SwanStation exposes memory card 1 as libretro save RAM (128 KB).
- **The stage's layout spawner** is `g_api.o.UpdateRoomPosition` (offset 8). It only creates entities in a window from 64 px left of the camera to 320 px right of the camera's left edge as the camera scrolls.
- **Entities and primitives are camera-relative.** The engine shifts `FLAG_POS_CAMERA_LOCKED` entities (and parallax ones by `unk68`) by the scroll delta every frame.
- **Targeting helpers** `GetSideToPlayer` and `GetDistanceToPlayerX/Y` are in all 52 stage and boss overlays (addresses in their maps). `GetPlayerCollisionWith` is platform collision, not targeting.
- **The castle entrance hall** (NO3 14,40) has zombies and a Warg idling just left of the entrance. The Warg wakes on player distance.

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

Richter mode replaces `ARC_F` + servant + weapons (`8013C000–8017FFFF`) with `RIC.BIN`.

## Player and enemies
- `PLAYER` is a macro for `g_Entities[0]`. `g_Player` is a single global `PlayerState` (0x3D0 bytes). DRA references `PLAYER.` about 1,700 times and `g_Player.` about 900 times.
- There are 256 entity slots. Slots 0–63 are for the player and its effects, and stage entities start at 64.
- `g_pads[PAD_COUNT]` already reads both controller ports.
- Slot 1's `entityId` is DRA's afterimage counter (`alu_anim.c`), so it can't mean "this slot is empty".
- Enemy targeting call sites (stages and bosses): `GetSideToPlayer` 419, `GetDistanceToPlayerX`/`Y` 350, `GetPlayerCollisionWith` 111 (platform collision, not targeting), direct `PLAYER.posX/posY` or `g_Entities[0]` about 135.

## 8 MB RAM
Enabled by writing the RAM_SIZE register at `0x1F801060`. Most modern emulators offer it, and modders commonly put a jump in the original code and new code in the 8 MB area.

## The decomp's PC port
Work in progress on PsyZ, with no release date. It can jump into a stage (`--stage`), run boss demos (`--demo N`), and `src/pc/replay.c` records inputs with a periodic state check. Our code is shared C, so it can move over when a true port exists (D8).

## Dracula X Chronicles
- Tucker's copy is the USA release, **ULUS-10277**; the decomp extracts from the EU release, ULES-00841. See D15.
- USA `maria.bin` is `0x33F80` bytes against EU's `0x3F700`: it omits 5 European HUD textures (`font_eu`, `hud_sp`, `hud_it`, `hud_ge`, `hud_fr`). Every Maria asset from `subweapons` to `crash_cardinal_pal` sits at a constant `-0xB780` offset from EU's.
- **Maria's sound:** `PSP_GAME/USRDIR/res/ps/snd_e/SE/sd_mar2.spk` (English), `sound/SE/sd_mar2.spk` (Japanese), built with `tools/maria-sfx`.
- **DXC dialogue:** cutscene scripts in `PSPBIN/{st0,cen,dai,dre,lib,no3,no4,sel}.bin`; voices in `snd_e/XA/*.at3` (English) and `sound/XA/*.at3` (Japanese).

## Emulator automation (checked 2026-10-18)
- **PCSX-Redux** (Windows, nightly 608 = the same commit as our OpenBIOS) runs headless with `-cli -8mb -fastboot -bios … -iso … -run -dofile x.lua`. The Lua API gives `PCSX.getMemPtr()` (RAM via ffi), `GPU::Vsync` events, `SIO0.slots[n].pads[1].setOverride(button)` and `PCSX.quit(code)`. Its stdout doesn't reach WSL, so results go to a file. A full route takes about 5 min (real time).
- **DuckStation** has no scripting or headless mode. It's portable when `portable.txt` sits next to the exe, and `settings.ini` takes the same option names as SwanStation's (`Console/Enable8MBRAM`, `BIOS/PathNTSCU`).
- **SwanStation** detects self-modifying code by itself. PCSX-Redux's dynarec doesn't: code written by the CPU only runs after `FlushCache()`. That's real-hardware behavior too.
- Libretro: a core can only be loaded once per process, so the lockstep check uses two processes.

## AYN Thor (for the dual-screen backlog item)
Android 13 clamshell. Top: 6.0" AMOLED, 1920×1080, 120 Hz. Bottom: 3.92" AMOLED, 1080×1240, 60 Hz. `DisplayManager` + `Presentation`, or a second `Activity` with `setLaunchDisplayId`, lets one process draw on the bottom screen.

## First-castle route and bosses (checked 2026-10-20, for the boss debug starts, D83)
- **Typical critical path** (Gamer Corner walkthrough, guides.gamercorner.net/sotn/walkthrough):
  1. Entrance (Cube of Zoe)
  2. Alchemy Lab: **Slogra & Gaibon**
  3. Marble Gallery (Spirit Orb)
  4. Outer Wall: **Doppleganger10**
  5. Long Library (Faerie Scroll, Jewel of Open), then Outer Wall (Soul of Wolf)
  6. Royal Chapel: **Hippogryph**
  7. Castle Keep (Leap Stone)
  8. Colosseum: **Minotaur & Werewolf** (Form of Mist)
  9. Long Library: **Lesser Demon** (Soul of Bat)
  10. Clock Tower: **Karasuman** (Fire of Bat); Castle Keep (Ghost Card, Power of Mist)
  11. Olrox's Quarters: **Olrox** (Echo of Bat); Sword Card, Holy Sword, Gravity Boots
  12. Underground Caverns: **Succubus** (Gold Ring), Merman Statue, then **Scylla Wyrm** and **Scylla** (Holy Symbol)
  13. Abandoned Mine: **Cerberus** (Demon Card)
  14. Catacombs (Spike Breaker): **Granfaloon**
  15. Silver Ring, Holy Glasses, then Castle Keep: **Richter** (or Shaft's orb with the glasses)
- **Where the game keeps it (decomp):**
  - boss rooms: `g_RoomBossTeleports`, plus the stage teleports in and out of each boss overlay (`src/dra/5087C.c`)
  - in-stage bosses: Slogra & Gaibon in NZ0 room 16, Karasuman in NZ1 room 0, Lesser Demon in LIB room 0 (spawned by entity 0x41), Succubus in DRE
  - defeated bosses: `g_Settings.timeAttackRecords`
  - story flags: `include/castle_flags.h`
  - the explored map: `g_CastleMap`, 2 bits per cell
  - level ups: `CheckAndDoLevelUp`, `g_ExpNext`, `g_LevelHPIncrease`

## sotn-online-coop (jweyden; checked 2026-10-27, for D109)
`github.com/jweyden/sotn-online-coop`: a co-op mod with the same goal, first published 2026-10-26 (4 commits, AGPL-3.0). Read, not built or run.
- **Engine:** SymphonyRecomp (a static recompilation of the PS1 game into .NET), not an emulator. The mod is about 10k lines of C# inside the game's process, plus a 729-line patch to the engine (GPU, VRAM, sound, disc reading, recompiler), pinned to three upstream commits.
- **The partner is a real second player:** each frame they swap the partner's player state into RAM and run `EntityAlucard` again with the partner's input, with rollback (up to 8 frames) and a snapshot pull past 48 px. The engine's VRAM is 1024 lines: lines 512+ are a private texture and palette bank per partner. This is the basis of M13.
- **Same shared-room design as ours (D50/D51/D57):** the first in the room runs it, the stream is entity slots 64–255 plus primitives, hits and pickups go back to it. Their stream is a full deflated copy each frame with no jitter buffer, and packets over about 1200 bytes rely on IP fragmentation: our M7 design before M7b's playout and deltas.
- **Features we lacked:** up to 3 players (6 internally), PvP (the victim's game decides), Saturn Maria and the long-coat Richter (PS1 overlays in C, `decomp-mods/*-forpsx`, AGPL: the base of M16), the PSP recast Alucard voice, fairy and Life Apple revives, per-character respawn effects, Mac support, a relay fallback.
- **Weaknesses:** players need Docker Desktop, the .NET SDK, about 15 GB and all three discs (US PS1, EU PSP, JP Saturn); setup recompiles the game on the player's machine (30–60 min). No Android. A lobby server at a fixed IP whose source isn't published. No tests or CI in the repository.
- **Why Docker:** only the extra characters need it (a MIPS compiler, sotn-decomp's Go and Rust asset tools); their overlays have disc art compiled in, so they can't ship prebuilt. Our Maria avoids this with patches of code only (`characters/maria-dx/make_patches.py`).
