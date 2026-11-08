# Research notes

What we've learned that the code and `TECHNICAL_SUMMARY.md` don't say: game internals, tools, and lessons that were expensive to learn. Search it rather than reading it through.

## Lessons
**Testing**
- **Test the path players use.** Android's Python has no CA certificates, so every request to the room-code relay failed silently, and the Android tests never caught it because they joined by `ip:port`. `android/test_pair.py --room` now uses the real relay.
- **A character applies from a game's next load.** The first PvP pairing tests were all two Alucards. Check that a test really runs as its character.
- **`set_player` writes into the game at once.** It used to wait for the host's next frame, and Continue sends the joint save's load right after it: solo and online castles continued as Alucard in 0.16.0. Couch never showed it, because its session is created with the characters (`castle_continue_keeps_character`).
- **A scripted boss kill can skip the death sequence** that writes the time-attack record.
- **UI flows test the last release patch**, which `rebuild_fixtures.sh` now remakes. Before that, they tested a three-day-old build.
- **Frame-drop baselines vary between soak runs:** sessions link over real loopback UDP with wall-clock hosts. Each game stays deterministic; the soak's 0.5% tolerance covers it.
- **Android emulator hosts can't be reached in tests:** two emulators sit behind the PC's NAT, and they can lose outside access after a WSL restart. Real devices aren't affected.
- **Writes through NULL land in BIOS RAM.** Player 1's controller dying for good has been this, three different ways (M13).

- **An attack hits an entity once through `unk6D[attack's enemyId]`**, a per-attacker cooldown the stage's hit detection counts down (`src/st/collision.h`), not through `nFramesInvincibility`. A guest's mirrored copy keeps its own cooldowns over each snapshot (`shared.c`): the authority's snapshot, from before it heard of the hit, had them at 0, and Richter's whip landed on every frame of the round trip (issues 157, 158).
- **The game's timer stops in the pause and equip menus.** A hang is the module's heartbeat stopping (it ticks every main-loop frame), not the timer: 10 s in a menu used to count as a hang (issues 150, 152).
- **Mirrored copies never run their update,** so whatever a stage's manager entity does at the end of a fight (NZ0's music, steps 5 and 6) doesn't happen in a guest's game. The module puts the music back (`boss.c`, issue 175).
- **A guest's copied scenery runs its setup again.** It's copied from the authority already set up, then started at step 0. A setup that moves the entity moves it twice: the red door's (`posX += 4`, `posY += 0x1F`) left it 4 px right of where it opens from, out of reach (#163). The module takes the red door's move back first; another scenery entity with a moving setup would need the same.
- **Placed collectibles are castle-flag bits.** `EntityPersistentItemDrop`'s params are an index into the stage's `PrizeDrops[]`, and its flag is bit `HEART_DROP_CASTLE_FLAG + index` of `g_CastleFlags[0x100...]`. `include/items.h`'s `ItemDrops` enum has gaps: read its values from the `/* 0x... */` comments, not by counting (`gen_collectibles.py` first gave the wrong items that way).
- **Richter's and Maria's standing status isn't Alucard's.** Their player code adds `NO_AFTERIMAGE`, and Maria's `0x200000` while she has hearts for a crash. Stage code that compares `g_Player.status` with 0x10000000 exactly (NO1's telescope) never works for them, in retail Richter's game too.
- **Mind branch delay slots when patching stage code.** The word after a branch runs with it: a `jal` placed there did nothing useful. The telescope's call goes one word later.

**Debugging with real devices**
- **Check installed versions first.** Four rounds of a device connection failure came from old builds on one side. Different versions now say so by name.
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
- We use the USA release, **ULUS-10277**; the decomp extracts from the EU release, ULES-00841. See D15.
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

## Moving the player from the module
`PLAYER.posX` is relative to the camera, and the engine keeps the world position in `g_PlayerX`/`g_PlayerY`. The module's frame hook runs after the engine compares the two, so a write to `posX` alone is undone the same frame. Write both.

## Scripts that assume Alucard
- **The walk after Richter's fight** (top `post_richter_cutscene.c`, step 3) holds Left and Cross once. Richter and Maria can't clear the ledge at x=550, and pause is off. With the Holy Glasses worn, the script lets go at the first landing instead.
- **The shop's Exit** (lib `e_shop.c`, steps 16 and 9) gives the pad back after 32 frames, but scene control stays on until the player walks past x=0xFF. Debug starts hold Alucard: `as_at_start` in `session_m12.py` puts the characters in play, and without it `characters=` has no effect on them.

## What a savestate costs
Serializing takes under 2 ms and a copy about 5 ms; the hitch was the 12.5 MB going through a worker's pipe. States that stay in the worker (`Emu.keep_state`) cost about 5 ms for both games together.

## Test starts and fights
- **A debug start can sit over a drop.** Maria in the Center's did: the player fell to a floor where her scene can't go on. Her scene needs the lift at x 384 on the floor at y 455.
- **A scripted boss kill hides what a long fight does.** Karasuman's chain fight ended in about 40 frames. Left alone, he can knock a player out of the door they arrived by: `boss_karasuman_stays_shared` keeps him alive for 30 s.

## Boot time is part of the tests
An extra CD read at boot shifts every savestate made afterwards, and `no_effect_on_play` and `pvp_familiar` fail on the shifted starts. Don't add boot reads: have the host write data to expansion RAM, as `link/portraits.py` does.

## Reading a crash from an F9 report
A report's `.state` file holds the game. After the header, the `CPU` marker is followed by 8 bytes, then 36 registers (pc is the 35th), and RAM starts 6702 bytes after the marker. A game stuck at pc 0x80000080 with a changed exception vector has been written over. Compare low memory with the partner's report: `g_Timer` stopped while emulator frames went on means the game itself stopped. Reports' `presences` are the player's own, not the partner's.

A game parked in the BIOS (pc 0xBFC0xxxx, sp near 0x8444, a black screen) took an exception the kernel didn't handle. The kernel saved the game's registers in the current thread's control block: the word at 0x108 points to it, and its word holds the block's address. The 32 registers start 8 bytes in, followed by epc, hi, lo, sr and cause. Cause bits 2-6 give the exception: 6 means a jump to an address with no memory behind it, and epc is where it landed. `ra` names the caller. In report 20261104-104320, epc 0x2F0F1F00 and ra in `func_8010A234` meant the menu's exit called a weapon overlay that was never loaded.

## Loading an F9 report's state
A report's state won't load as it is: the disc's path is blanked, in the header and in a trailer after the data. `harness/replay.py` points both at this machine's disc. `scripts/read_report.py` prints who was where from a report's memory, without an emulator.

## Doorways have gaps
The east door of the Marble Gallery's corridor (room (45,25) to (60,25)) has a one-tile gap in its floor under the door. Alucard's door walk crosses it. Richter's and Maria's walks check for a fall, and they drop in. In there, the wall pushes the player 13 px, which is through the door: the room changes, and the same happens on the other side, forever.

## Camera limits are a floor
`g_Tilemap.height` isn't only the camera: with no room below, a player is held there. A player past an `EntityLockCamera` it never ran for stands at y 251 on nothing, off the screen. If a report shows that y, look at the limits.

## ANIM_FRAME_LOAD
Bit 15 of `animCurFrame` means "the sprite is already in VRAM, don't upload it". A dead player's last frame has it: a body stuck at a frame like 0x8022 is a dead body.

## A mailbox can exist before its module runs
`magic` and `version` are set before the module's code runs, and a command written in that gap is lost. Anything sent to a booting game waits for nonzero presence flags: a running module always sets `IN_PLAY` or `BUSY`.

## The ending's movie stops g_Timer
`g_Timer` ticks in `MainGame`'s loop, and the ending's movie plays in its own (`VSync`, `StGetNext`). So in `Game_Ending` a stopped timer isn't a hang.

## Primitive chains need their full length
An entity's primitives are a linked chain, and its code walks them all. A chain cut short when a guest takes an entity over runs that code off the end (a Beelzebub part has 256 and froze the game). `CompleteChains` rebuilds them on hand-over.

## Fist weapons are primitives
A fist weapon's entity has no sprite (`animCurFrame` stays 0). Its overlay (`w_001.c`) draws four primitives on tpage 0x1A, and Alucard's own body plays the punch. So the link's weapon sprites carry nothing for a fist. Richter and Maria draw a crop of Alucard's own body frames instead (`DrawArm`, D164): frames 125-127 hold the reach, in front of x +12 and above his cape.

## The Android app has its own file list
`android/build.sh` stages the app separately from `scripts/build_release.sh`. A file added to one isn't in the other: 0.13 to 0.16.0 shipped an APK without `maria-partner.bps`, and every game start on Android with Maria's disc chosen crashed. `launcher_ship_lists` checks Maria's files are in both. On the Thor, 0.16.1 solo play holds 61 to 62 fps with the CPU at 200% (D154); a two-player session on it isn't measured.

## Sound on Android
pygame on Android isn't pygame-ce. Its AudioDevice callback deadlocks, and SDL_mixer's `Channel.queue` starts the queued sound from a callback that needs Python's lock, so it starts late and the sound gaps. SDL_QueueAudio through ctypes works: `libSDL2.so` is already loaded, and `pygame.mixer` must be shut first because Android opens one device. Also, `Clock.tick(60)` there rounds to 16 ms, 62.5 fps. F9 reports' `audio` has the numbers: `path`, `underruns`, `gaps` (when, the frame gap, what was buffered), `fed_ms` against `seconds`.

## A presence mid-load is half old, half new
While a game loads another stage (a teleport, a door to another area), its presence already has the new stage, but still the old room, the old scene's flag and a mid-load position such as (0, 4). Nothing may act on it then: a scene pull sent the partner there, and its own room change then waited for good on a graphics load of kind 0xFFFE that `LoadPendingGfx` never clears. Presences now say so (`FLIP_LOADING`), and pulls ignore them. Found by `crawl_dai`.

## Finding a place to stand in a room
`harness/roommap.py` reads a room's collision from sotn-decomp's extracted stage files (`assets/st/<stage>/layers.json`, the fg tilemap, the tile definition's `_cols.bin`): nonzero is solid. An arrival inside a wall or ceiling goes wrong in ways no player would see (it can land in another room, or in a scene), so tests arrive on a floor. NO1, RLIB, RNO3 and RARE have no extracted room table.

## An arrival keeps the speed it had
A teleport (a pull, a map teleport, a revive) puts the player at the partner's ground spot, but the player kept its velocity from before, and the ground spot is the doorway the partner came in by until the partner lands. Pulled into a boss's room right after the partner, a walking player slid straight back out through the door. `ArriveFinish` now zeroes the speed and keeps the spot 40 px from a room's left and right edges. Adding the move to `g_PlayerX` as well counted it twice: the frame's own update derives it from the entity's move (boss rush's joiner landed elsewhere).

## A save room is never left for a pull
`D_80137598` is DRA's "in a save room". `CanBePulled` refuses then, so a partner standing in a save room is pulled into a boss fight only once it walks out (`edges_boss_pull_waits_for_the_save_room`).

## When a test's game process dies
Each game process writes a native stack trace (faulthandler) to `coop-worker-<pid>.txt` in the temp folder, and the harness reports the exit code (a negative one is the signal) and that trace. Issue 142 was found this way: a SwanStation segfault in `UncheckedReadMemoryHalfWord`. For a native crash, swap in a `RelWithDebInfo` build of the core (`cmake -B build-dbg`), run with `ulimit -c unlimited` (the core file lands in the worktree), and read it with gdb: `CPU::g_state.regs`, and `Bus::g_ram` plus a PSX address for the game's RAM. Then map the PSX pc through `coop.elf` with `mipsel-linux-gnu-objdump -d -l`.

During a stage change, `g_StageId` is the next stage from `Play_PrepareNextStage` (4) on, but its overlay isn't in RAM until `Play_LoadStagePrg` (9) is done. Anything that looks up the current stage's addresses (`FindOverlay(g_StageId)`) only does so with `g_GameStep == Play_Default`. Issue 142 was `ResyncSpawner` walking the old stage's memory as the new one's layout list.

## The randomizer's disc (sotnrando 26.07.13, checked 2026-11-05)
- It writes raw offsets in the track 1 image (sector headers included) and recomputes each sector's checksums itself; its `.ppf` leaves the checksums to the player.
- Items: `zone.items + 2 * index` is the stage's `PrizeDrops` (same offsets as the decomp's maps), and the value is `(candle << 8 | id) + 0x80` for an item. Candles and enemy drops are other tables.
- Its own code lives in low RAM (`0x8000C000`, its `FrameHook` target) and in `WARNING.TIM`'s sectors on the disc, which it overwrites. Co-op uses neither.
- The seed and `<version> <preset>` are Shift-JIS text at `0x04389C6C` and `0x04389C8C` (its `setSeedText`). A hyphen comes back as U+2212 after NFKC.
- One seed URL on one randomizer version gives the same disc byte for byte, so two players' co-op discs match.
- Some presets take minutes to generate, since the randomizer retries placements until a seed is completable. From its command line (`node randomize`, pinned `3522dc6`), four presets never finish: **gem-farmer** and **bingo** crash in `randomize_relics.js:1249` (`target.min`: they have no `complexityGoal`), and **glitch** and **glitch-legacy** search past 15 minutes with every seed tried. That's the command line, not co-op: `mods.py` leaves them out (`RANDO_CANT_MAKE`), and a player's disc from sotn.io layers the same way as any other.
- **Start-room presets** (`startRoomRandoMode`, `startRoomRando2ndMode`: 12 presets, e.g. open, rampage, chaos-lite) rewrite NO3's room table at `NO3.BIN+0x3CC4` (`rooms`, 8-byte `RoomHeader`s). Retail room 16 (the corridor after the drawbridge, cells 4–10,40) becomes a one-cell "CD room" at (4,40). Room 24 becomes a teleport room at (5,40), with load `{100, 0xFF, 0, 0}`: entering it takes DRA's teleport entry 100 (`0x800A2844`), which the preset points at the seed's start room. Retail room 24's own content (Holy Mail) is unreachable on these seeds. Any test that hard-codes a retail NO3 room must check `session_mods.replaced_rooms` first. Co-op's own teleport only targets a room the partner is in, so it's unaffected (#178).
- **2nd-castle start-room presets** (`startRoomRando2ndMode`) also patch NO3's `EntityTrapDoor` (disc `0x4BA934C`, back to `0x801BA4AC`). Stepping on it sets `g_StageId = 0x20` and calls `func_800F2120`, while the player stays in NO3's room 0. The game then counts as the 2nd castle, for the preset's gravity-boots rule, until the CD room's teleport. A new game auto-walks both players onto it. Co-op's presence reports that fake stage, so a teleport to such a player goes to the real RNO0 (#179).
- A disc image is 540 MB, and under WSL Linux's disk is a file on C: that never shrinks: keeping one per preset (72) filled C: and stopped WSL. Only the tested presets keep theirs (`mods.TESTED`).


## Other mods' Richter and Maria (checked 2026-11-07)
- **SOTN Ultimate's Saturn characters are converted, not patched.** Ultimate Richter (`RIC2.BIN`) is retail Richter's code with the Saturn's long-coat art, which `tools/build_ric2.py` redraws onto the PS1's sprites: it narrows the Saturn's 1.25x-wide images back, matches each PS1 sprite, and recolours the body palettes. Saturn Maria is `src/ric` built again with `MOD_MARIA_SAT`, with her art made by `gen_mar_assets.py` (925 lines). Neither output is in any file on a disc, so a BPS patch of one disc file (how both Marias ship: D7, M8 §4) can't make them. The player's machine would have to run the converters.
- **The Saturn disc Ultimate needs** is the Redump *Akumajou Dracula X: Gekka no Yasoukyoku (Japan) (2M)*, Track 1 MD5 `32f037579707e192320db6e8f24ef571`. Knight0fDragon's English fan translation (v1.021) has another MD5 (`e529505a…`). Ultimate's converters read `GAME.PRG`, `RICHTER2.PRG/.CHR`, `RIC_W2.CHR`, `MARIA.PRG`, `MAR_W.CHR`, `0.BIN`, stage files and `SD/*.PCM`.
- **Alternate Scarlet Symphony's Richter Mode:** [sotn-editor](https://github.com/pddmergilla/sotn-editor) is GPL-3.0 and public. Richter Mode is in it as `tools/extra-hacks/specs/final/richter-mode.json`: byte edits (`off`/`on` hex for `DRA.BIN` and other files, about 30 KB changed), not C source. A few smaller Richter boss fixes do have C (`tools/bosses/richter-stopwatch-crash/*.c`). Its DRA edits overlap the places our hooks go, and it's built for the ASS -Final- disc layout. Taking it as a character would need its source, or a port of its bytes onto our DRA.

## Arenas without side walls
Richter's (BO6), Shaft's and Dracula's (RBO6) and the Succubus's (DRE) rooms have no wall tiles at their sides: the screen's edges are the walls. Alucard's `CheckWallRight`/`Left` (`src/dra/6BF64.c`) report a wall at x 248 and 8 in those stages; Richter's and Maria's (`RicCheckWallRight`, `MarCheckWallRight`) never had to. The possessed Richter's tackle and Blade Dash hit with `DAMAGEKIND_5`, which flings the player until they meet a wall (`RicStepHit` step_s 2). Past the edge, DRA's room code holds them at x 255 (`src/dra/5087C.c`, no room to load), where no wall is ever met (#188). In a report, step 10, step_s 2 at x 255 is this. Note that Richter's and Maria's `CalcPlayerDamage` (the short one at the top of `5D5BC.c`) never makes kind 4 or 5 from a hit's size: only the attack's own `hitParams` can.

## Heals only Alucard takes
The faerie's potions (`src/dra/7E4BC.c`) and Healing Mail (`src/dra/5F60C.c`) don't heal: they set `g_Player.healKind` and `healAmount`, and Alucard's player code applies them (`src/dra/692E8.c`). Healing Mail also needs `PLAYER_STATUS_UNK4000000`, which only Alucard's walk sets. Blood Cloak's hearts and Fury Plate's defense live in Alucard's `HandleDamage`, which Richter's and Maria's hits don't go through (#202).
