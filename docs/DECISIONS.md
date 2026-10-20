# Decision log

Format: **ID: decision** (owner | agent-default) then the context, the options considered, and why.

**D1: Fork sotn-decomp; mod code lives in `mods/co-op/`** (owner, 2026-10-18)
We inherit the matching build and all decompiled code, and keep upstream diffs minimal.

**D2: Target the PS1 US build (SLUS-00067)** (owner, 2026-10-18)
It's the reference build the decomp is most complete for, and PS1 netplay is mature and lockstep-deterministic. PSP has more content but weaker netplay. _(2026-10-18: the target stands. The netplay reason no longer applies, because of D20.)_

**D3 (superseded by D7): P2 is a second Alucard; Richter/Maria as P2 are stretch goals** (owner, 2026-10-18)

**D4 (superseded by D20): No networking code in the mod** (owner, 2026-10-18)
Local P2 on port 2. Online play comes from RetroArch netplay or streaming tools (Parsec, Steam Remote Play Together).

**D5 (revised by D7, then by D20/D28): Must run on popular PS1 emulators** (owner, 2026-10-18)
DuckStation, RetroArch cores, PCSX-Redux. Real PS1 hardware is no longer a target.

**D7 (revised by D27): Richter and Maria as P2 are core goals; use 8MB dev-RAM mode from the start** (owner, 2026-10-18)
Playing as Alucard + Richter or Alucard + Maria is a much better experience than two Alucards. Because we build from source, `RIC.BIN` (and the Maria mod's overlay) can be relinked into the 8MB expansion area instead of their normal slot, so they coexist with Alucard. The community already treats 8MB as standard ("most modern emulators have the 8MB available"). Cost: players must enable the emulator's 8MB option, and each target emulator's support must be verified in M0. Maria additionally requires the user to own *Dracula X Chronicles (EU, PSP)*.

**D8: Ship as a patched PS1 disc image now; don't wait for the PC port** (owner, 2026-10-18)
The PC port has no release date and currently covers 23 of 41 stages. Our co-op code is shared C source, so it carries over to the port if and when that ships, and Android may follow quickly once it does.

**D9: Distribution builds from the user's own disc** (owner, 2026-10-18)
Follow the Maria mod precedent: a Docker image or script that takes the user's own disc image(s) and outputs the patched image. We publish no game data and no pre-patched images. An xdelta/PPF patch is a possible convenience option, subject to an owner decision.

**D6: Dev loop and budget** (owner, 2026-10-18)
The spec-driven loop is in `AGENTS.md`. Claude Pro subscription, ~1 month target. An upgrade will be considered if needed.

**D10: Install DuckStation + PCSX-Redux for cross-checks, using OpenBIOS** (owner, 2026-10-18)
Install both into `C:\Users\tucke\OneDrive\Desktop\Emulators`, pointed at OpenBIOS so the checks are fully automated. Tucker runs a real-BIOS smoke test at milestones.

**D11: Environment layout: one manifest plus a doctor; masters live in the OneDrive Emulators folder** (owner, 2026-10-18)
`env.example.toml` (committed) and `env.toml` (local) list every path. `scripts/doctor.py` checks them, and `scripts/bootstrap.sh` creates them. Masters go in `OneDrive\Desktop\Emulators\SOTN\` (Tucker accepted the ~1.5GB of OneDrive sync). Working copies stay in WSL `disks/`, and churny data (savestates, builds) stays in `mods/co-op/.env/`.

**D12: MIPS cross toolchain from Ubuntu 24.04 via an apt pin** (agent-default, 2026-10-18)
Ubuntu 26.04 dropped `gcc-mipsel-linux-gnu`. Options considered: pinned noble packages; building gcc from source; clang as the preprocessor. Chose noble because it's the exact compiler upstream's Docker image uses, so matching-build risk is lowest. Pin priority is 50, so nothing else is pulled from noble.

**D13: Branch names are `coop-mx-<name>`** (agent-default, 2026-10-18)
Git can't create `coop/...` while a branch named `coop` exists.

**D14: Docker disc builder deferred to M5** (owner, 2026-10-18)
M0 builds the heartbeat disc with a plain script. M0 acceptance criterion 6 is changed to match.

**D15: Dracula X Chronicles (USA) is kept, but the Maria mod can't use it as-is** (agent finding, 2026-10-18)
Tucker owns ULUS-10277. Upstream's Maria assets are extracted from the EU release (ULES-00841) at fixed offsets. All 65 USA PSP overlays differ from the EU hashes, and `maria.bin` is 46KB smaller (the EU build has 5-language HUDs), so the offsets don't carry over. This is decided at M6 (Maria is post-month): obtain the EU copy (no maintenance), or write and maintain a `pspus` asset map (~0.5 day, and lets USA owners play Maria). The 14 "HD" PSX files on the USA disc do match upstream.

**D16: Savestate library keyed by disc image** (agent-default, 2026-10-18)
SwanStation rejects states from a different image. `.env/savestates/<disc-stem>/`, rebuilt in about 20 s per disc build.

**D17: The co-op module flushes the instruction cache after patching code** (agent-default, 2026-10-18)
Required for PCSX-Redux and real hardware, found by the cross-emulator check. Applies to any future code patch.

**D18: Cross-emulator checks are automated where the emulator allows it** (agent-default, 2026-10-18)
PCSX-Redux runs headless (`-cli` + Lua) from WSL, with no window. DuckStation has no scripting, so it stays a manual check. Options considered: computer use, DuckStation's GDB stub. Both cost more than a 2-minute manual check per milestone.

---
## 2026-10-18 pivot: independent exploration

**D19: The final goal is independent exploration with shared progression** (owner, 2026-10-18)
Each player explores the castle on their own screen. Progression is shared, and players meet up to fight together. Two players stuck in one camera view would be fun for about an hour. Independent exploration keeps what makes SOTN fun (exploring, secrets, power-ups, new abilities) for tens of hours and repeat playthroughs, and it makes co-op speedruns possible. This replaces the same-screen "P2 Lite" goal.

**D20: One game instance per player, plus a co-op link** (owner, 2026-10-18)
Each player runs their own emulator instance of the patched game. An in-game module plus a host program per player exchange progression, presence, teleports and shared-room state. Emulator-only from now on: real hardware limits don't apply.
- **Considered:** running both players in one instance. SOTN keeps one stage in memory at a time: stage code loads at a fixed address, about 1MB of VRAM holds one stage's tiles, and sound banks and CD streaming are per stage. Two players in different areas would mean swapping the whole world in and out every frame. Rejected as open-ended research.
- **Consequences:**
  - Pausing separately and having separate screens come for free.
  - Online play becomes natural, so D4 is superseded.
  - Whole-game lockstep determinism is no longer what netplay needs. It still matters for harness reproducibility, and possibly for shared rooms (D23).

**D21: What's shared and what's separate** (owner, 2026-10-18)
- **Shared:** relics, castle flags (walls, doors, switches, bosses, cutscenes, item pickups), explored map, and equipment. Finding equipment gives each player a copy, so both can use it at once. Max HP/MP/Hearts upgrades go to both.
- **Separate:** level, XP, gold, consumables, the equipped loadout, current HP/MP.
- **Agent-default:** a consumable pickup goes only to whoever picked it up, but it disappears in both worlds, because its pickup flag is shared.

**D22: Live updates for everything** (owner, 2026-10-18)
Shared changes apply within frames, including in the room the partner is standing in (walls break and doors open in front of them). Presence (position, pose) is live too. Players should be able to see each other, explore, solve puzzles and fight together.

**D23: Same room means the same enemies** (owner, 2026-10-18)
When both players are in one room, they fight the same enemy instances, not copies. Damage from either player counts, and enemies target and damage either player. The method is decided in the M4 design: room authority vs lockstep merge (see `research.md`).

**D24: Death means respawning at the partner, except during a boss fight** (owner, 2026-10-18)
No Game Over while the partner is alive. The player who died reappears at the partner's location with full HP.
- **During a boss fight:** a player who dies stays dead, and the remaining player has to clutch it. If the remaining player kills the boss, the dead player respawns next to them.
- If both players are dead at the same time, both reload the last joint save.

**D25: Bosses are fought together, with 2× HP** (owner, 2026-10-18)
When either player enters a boss room, the partner is teleported in automatically. Bosses get double HP. Regular enemies keep normal HP.

**D26: Cutscenes are seen together, and both get credit** (owner, 2026-10-18)
When either player triggers a cutscene, both see it, and its flags count for both.

**D27: Each player chooses Alucard, Richter or Maria** (owner, 2026-10-18)
Each character runs natively in its own instance, so there's no need to relocate Richter's code (that was the old M2). The 8MB area still holds the co-op module, plus the partner's sprite data for drawing the puppet.
- **Still open (before M7):** what shared progression means for a character who doesn't use it, such as Richter with relics, equipment or levels. Also, Richter mode changes world behavior.
- Maria still depends on D15.
- The month target is Alucard + Alucard.

**D28: Which emulator to ship for is decided separately (R1)** (owner, 2026-10-18)
Tucker wants it researched and discussed on its own. Requirements are collected in `research.md`. Until R1, development uses the harness (two SwanStation processes) plus PCSX-Redux. All emulator-specific code goes behind a thin adapter.

**D29: The ghost-P2 M1 design is withdrawn; its loader (option B) carries over** (owner, 2026-10-18)
The context swap was for P2 sharing P1's instance, which is now unnecessary. It may come back as one option for shared rooms (D23). Loading the module as an extra DRA section is still the plan for getting co-op code resident at boot.

**D30: Teleport to the partner on demand; pausing is independent unless both are in the same room** (owner, 2026-10-18)
- Teleport is a pause-menu entry (owner: "a menu entry or whatever is easiest"). The M3 design proposes ✕ on the map screen as the easiest equivalent (the pause menu is DRA code, which can't grow, D33).
- When both players are in one room, a pause by either one pauses both.

**D31: The joint save covers both games** (owner, 2026-10-18)
Saving in either game saves both, plus a session file with the shared state. Resuming restores both.

---
## M1 build

**D32: The module loads from its own disc file, `COOP.BIN`** (agent, 2026-10-18; changes the approved loader from option B to the design's fallback C)
Option B (the whole module appended to `DRA.BIN`) failed for two reasons found while building:
- DRA can't grow (D33).
- A `DRA.BIN` longer than its last CD sector shifts every later file on the disc, and boot hangs in the intro FMV, which is read from a fixed sector.

So `DRA.BIN` gains only `CoopBoot`, 184 bytes inside its last sector, which runs in place as the first call in `MainGame`. It reads `COOP.BIN` (added after every retail file) into 8MB RAM, the way `main.exe` reads `DRA.BIN`.
- The module's size is now unlimited in practice.
- Cost: one CD read at boot, a few frames.

**D33: Every DRA hook is size-neutral: it retargets an existing call** (agent, 2026-10-18)
DRA's code and BSS end exactly at `0x8013B6A0`, where its fixed-address data block starts. Adding even one call (0x90 bytes) pushed BSS into that block. Under `COOP`, each hook replaces a call with a same-signature module function that does its work and calls the original:
- `InitializePads` → `CoopBoot`
- `DebugUpdate` → `CoopUpdate`
- `RenderEntities` → `CoopRenderEntities`
- `DrawMapCursor` → `CoopDrawMapCursor`

`build_disc.sh` fails if DRA's image no longer ends at `0x801B9870`.

**D34: No retail file may move on the co-op disc** (agent, 2026-10-18)
`scripts/check_disc_layout.py` compares every file's sector with retail after mastering. CD-DA entries are skipped, because upstream's own mastering already places them differently.

**D35: Puppet defaults** (agent-default, 2026-10-18)
- Blue-grey tint (RGB 0x60/0x70/0xA0 over 0x80).
- The partner is hidden after 30 frames without an update.
- Body only (no weapon or effects).
- Drawn one depth step behind the partner's own priority.
- The map cursor is the same as the player's, tinted blue and half a blink cycle out of phase.

---
## 2026-10-18 evening

**D36: R1 decided: our own co-op launcher, PC first** (owner, 2026-10-18; supersedes D28's open question)
Order of work:
1. PC couch co-op that works.
2. Online co-op for PC.
3. Port everything to Android.

**Why a dedicated launcher:**
- The link reads and writes RAM exactly between frames, which our own libretro frontend does natively.
- No stock emulator runs two games on two pads in one window.
- The harness is already most of a frontend.

The launcher may also own anything that's easier outside the game, such as save files (owner). SwanStation stays the core. Android means a launcher port later, not RetroArch.

**D37: Every find is shared, consumables included** (owner, 2026-10-18; revises D21)
Tucker: duplicating consumables or giving them only to the finder are both fine, "whatever is easy". Sharing every `AddToInventory` from the world is the simplest (no category check), so both players get a copy of any item found.

**D38: Gold is pooled** (owner, 2026-10-18; revises D21)
Both players spend from one purse, so the late-game expensive item stays reachable. Each game's gold changes travel as deltas and are added on the other side, never below 0.

---
## M2 and M3 build (2026-10-19)

**D39: The main-loop hook always runs the game update** (agent, 2026-10-19)
In US, `DebugUpdate` is `jr ra` and sets no return value. DRA runs `UpdateGame` on the stale `v0` (in retail, `ClearOTag`'s non-zero result). `CoopUpdate` returned "DebugUpdate's result", which is really whatever our code left in `v0`, and froze the game for some code layouts. It now calls `DebugUpdate` and returns true, or false only for its own reasons (the pause freeze, waiting while both players are dead).

**D40: Per-frame work in the module stays small** (agent, 2026-10-19)
A byte-by-byte scan of the flags and map (about 30k cycles) dropped a frame in a busy scene. That changes how the game plays, and `no_effect_on_play` caught it. Scans compare words. Any new per-frame work should be checked against that test.

**D41: `COOPPAD.` restores retail's 150 blank sectors after the XA stream** (agent, 2026-10-19)
Upstream's mastering drops them, which puts `COOP.BIN` right behind the music stream. Now the disc ends like retail's data track, and `check_disc_layout.py` checks that the filler is blank.

**D42: No on-screen co-op text yet; sounds instead** (agent-default, 2026-10-19)
The designs had debug-font text for "Go to partner", "Partner busy", "PARTNER PAUSED" and "Partner found: …". The debug font needs VRAM and a flush that could fight the game's own drawing. The launcher (M6) can draw text outside the emulated screen instead.
- ✕ on the map plays the confirm sound, or the error sound if the partner is busy.
- The pause freeze and the partner's finds are silent for now.

**D43: Joint saves in tests go through `JointSave.request`, not the save-room menu** (agent, 2026-10-19)
The save room's memory-card dialog isn't driven in the harness. Its `StoreSaveData` call is hooked (5th size-neutral hook, verified in place), and `request` makes the same module call. Tucker's playtest (M6) covers the real dialog.

**D44: Arrive borrows door-teleport entry 7** (agent, 2026-10-19)
Arrive uses the game's door transition with a borrowed entry of `D_800A245C`, restored afterwards. Entry 7 is one of the few that make `Play_LoadStageChr` load the target stage's tiles, which a normal door would get from the CD room. With any other entry, cross-stage teleports drew the new room with the old stage's tiles.

**D45: Pause freeze, respawn and teleport details** (agent-default, 2026-10-19)
- The freeze applies only while I'm in normal play in the partner's room and the partner is in their menu, on the map or in a status pause.
- A respawn gives full HP and MP.
- Teleport and respawn land on the partner's last grounded spot.

**D46: Saving uses the game's own save rooms, and resuming uses the game's own Load menu** (owner, 2026-10-19)
Tucker: the built-in save rooms are "very cool"; launcher saves are OK only as a backup. The partner's game writes a normal memory-card save for the same save room (M3b). `session.coop` stays as the backup, and for the both-dead reload. D42 and D45 defaults approved.

**D47: Bosses switch aggro between players** (owner, 2026-10-19)
After each boss attack, there's a 50% chance the boss targets the other player next. Expect to tune it. Bosses have 2× HP (D25, restated).

**D48: Final milestone: 3–4 player support** (owner, 2026-10-19)
Added at the very end of the roadmap.

**D49: Saving may freeze the partner; a coffin heals only its user** (owner, 2026-10-19)
While one player saves at a save room, the partner's game may freeze; it writes its own card save during that time (M3b). The coffin's HP restore affects only the player who used it. HP isn't shared, so that's the natural result.

---
## M4 build (2026-10-19)

**D50: Shared rooms work by room authority with mirroring, as designed** (agent, 2026-10-19)
- **Authority:** the player who entered the room first; ties go to rank 0.
- **When the room is shared:** same room, both in normal play, cameras within a screen of each other. A role change has to hold for 4 frames, and a clash (both picked the same role) is settled by rank.
- **The guest:** stubs `g_api.o.Update` and `UpdateRoomPosition`. Each frame it copies the authority's snapshot in: stage entities, their primitives with stable index remapping, and stage BSS.
- **Hits:** the guest's hits go to the authority as `EV_HIT`/`EV_HIT2` events. The authority applies them right after its own hit detection (the `g_api.o.HitDetection` wrapper).
- **Targeting:** the helpers of every stage and boss overlay are patched in RAM to aim at the nearer player. The module checks each helper's first instruction before patching.

**D51: A guest's pickup goes to the authority** (agent-default, 2026-10-19)
The guest's touch on a mirrored drop reaches the authority as a hit, and the authority's player collects it. Items, relics and gold are shared anyway (M2), so this only affects hearts. A later fix could move the reward to the guest.

**D52: Known shared-room gaps, left for later** (agent, 2026-10-19)
- Moving platforms don't carry the guest.
- About 135 direct player reads still target the authority's player.
- Big rooms only share while the players' cameras overlap.

All are listed in `design/M4-shared-rooms.md`.

**D53: Per-frame copying uses word copies and reuses primitive chains** (agent, 2026-10-19)
A first version dropped the guest to about 50 fps (D40). `COOP.BIN` is now 160 KB because the snapshot buffers are part of the image. Boot reads it in about half a second; moving the buffers out of the image is a possible trim later.


---
## M4b: playtest 1 fixes (2026-10-19)

**D54: The rainbow flash on hit enemies is the game's own** (agent, 2026-10-19)
The unmodified disc shows the same rainbow palette flash when a Warg is hit (checked side by side in the harness). The real bug was the opposite: an enemy the guest hit didn't flash at all. The authority now starts the flash for relayed hits, as the game's own hit detection does.

**D55: Couch audio mixes both games; one game plays music** (agent-default, 2026-10-19)
- **Mixing:** the launcher mixes both games' sound into one stream.
- **Music:** muting is done in the game itself (the module holds the CD/XA volume at 0, `CONTROL_MUTE_MUSIC`), so sound effects stay audible.
- **Which game:** music comes from the left game while it's in play, otherwise from the right one. F1 switches between auto, left and right.
- **Online play** (later) won't mute anything: each player hears all of their own game.

**D56: Scenery is run by the guest, not copied** (agent, 2026-10-19)
- **Problem:** decorations that draw from the camera with a 3D projection or parallax can't be shifted into place for another camera. That was the playtest-1 bug with the bouncing trees and the missing bushes.
- **Fix:** each overlay's scenery update functions are listed in `overlay_table.c`, generated from names. The guest copies these entities once, then runs them itself.
- **Scope:** only pure decoration is listed. Spawners stay copied, while their children are run locally.

**D57: Kills, drops and effects from guest hits happen in the authority's world** (agent, 2026-10-19)
- **The kill bit:** the authority sets `PreventEntityFromRespawning`'s bit for a relayed kill, and the guest ORs in the snapshot's bits.
- **Created entities:** whatever the guest's hit detection creates (a drop, blood, a Soul Steal orb, a damage number) is sent as `EV_SPAWN`×3. The authority creates it, and it reaches the guest in the next snapshot. Before this, drops from guest kills were lost.
- **XP:** stays with whoever landed the kill.
- **Candles:** `hitParams` goes along with a relayed hit, so a guest's hit breaks candles.

**D58: The spawner's cursors are re-seated at hand-over** (agent, 2026-10-19)
The layout spawner's cursors are in the copied stage BSS, so at hand-over they point where the authority's camera was. The new owner re-seats them for its own camera, as `InitRoomEntities` would, without spawning anything. Without this, killed enemies came back.

**D59: Co-op messages use the item-pickup text box** (agent-default, 2026-10-19)
- **The text box:** the stage's `BottomCornerText`, on the right and in green, so a message isn't mistaken for a pickup.
- **The messages:** "Partner is saving" / "Game saved", "Joined partner", "Partner out of reach", "Revived by partner", "Partner is fighting a boss!", "Can't leave a boss fight", "Partner fights on alone".
- **Effects:** death fades to black slowly (`FADE_TO_BLACK_SLOW`) before the respawn. Arrival from a teleport or respawn uses the screen flash of Richter's Cross Crash (`FADE_NONE`).
- This also answers D42 (on-screen co-op text).

**D60: A death only counts in normal Alucard play; a stale joint save is never loaded** (agent, 2026-10-19)
- **What went wrong:** in playtest 1, the end of the prologue counted as "both dead", and the launcher loaded `session.coop` left over from the save-room test.
- **Deaths:** now count only outside ST0 and in `Play_Default`.
- **Reloads:** the launcher reloads only a joint save written or resumed in the same run. The New Game preset deletes `session.coop`.
- **Busy partner:** a dying player waits up to 30 s for a busy partner instead of forever.

---
## M5: bosses and cutscenes (2026-10-19)

**D61: A boss is identified by its enemy definition** (agent-default, 2026-10-19)
- **The list:** 31 bosses by `enemyId`. Slogra and Gaibon are fought in an ordinary stage, so the stage can't be the test.
- **2× HP:** the module doubles those entries in the in-RAM enemy table while a partner is linked, never mid-fight.
- **Presence:** `PRESENCE_BOSS` means a living boss is in the room.

**D62: Aggro re-rolls every 3 s, with the partner swapped in** (agent-default, 2026-10-19)
- **When it switches:** "After each attack" is approximated by time: a 50% re-roll every 3 s. A first try re-rolled on a change of the boss's `step`, but the Doppleganger's step rarely changes, so it switched only 2–3 times a minute. The switch chance can be changed from the launcher through the control word (bits 8–15), and `CONTROL_NO_AGGRO` turns aggro off for the control test.
- **How:** while the target is the partner, the boss's update runs with `PLAYER`'s position and facing (and `g_PlayerX/Y`) set to the partner's. Afterwards they're restored, and a grab carries over. This works for every boss, also those that read `PLAYER` directly.
- **Tuning:** per-boss attack hooks can come later if playtests say it feels wrong.

**D63: The room's foreground tiles are mirrored** (agent, 2026-10-19)
- **The gap:** doors, breakable walls and the clock room's stone doors change `g_Tilemap.fg`, and with it what's solid. A guest never ran those changes, so it walked out of a closed boss room.
- **The fix:** the authority checksums the layer every frame. It sends the whole layer, up to 8K tiles, when it changes, and again every second. This closes part of D52 (walls); moving platforms are still open.

**D64: A mirrored `PRIM_ENV` gets its own `DR_ENV`** (agent, 2026-10-19)
- **The problem:** render-to-texture effects, such as the Warg burning away, use `PRIM_ENV` primitives that point into DRA's 16-entry `DR_ENV` pool. The guest copied the authority's pointer, which in the guest's RAM is one of its own entries, maybe in use, for example by Alucard's afterimages. Its screen showed leftover VRAM, a piece of the HUD; this was the playtest-1 "glitch when a monster we both hit died".
- **The fix:** snapshots now carry each env's contents, and the guest allocates and keeps its own pool entry per mirrored env.
- **Safety:** mirror chains are never allocated as `PRIM_ENV`, because freeing one without an env writes through a null pointer.

**D65: Stage VRAM uploads are mirrored** (agent, 2026-10-19)
- **The gap:** some entities write into VRAM as they run, for example the text of a relic's "Obtained ..." box and palette fades. The guest showed an empty box.
- **The fix:** the module patches `LoadImage`, `LoadTPage` and `LoadClut` in `main.exe`, each with a first-instruction jump to a module copy.
- **What's sent:** uploads whose caller is stage code are recorded on the authority and sent with the snapshot, at most 8 KB a frame. DRA's own uploads, such as each player's sprite frames, are never sent.
- **UI placement:** the guest also stops shifting UI primitives (priority 0x1E0 and up, or `DRAW_ABSPOS`) by the camera difference, so the box stays where it belongs.

**D66: A prize drop the guest touches is the guest's (replaces D51)** (agent, 2026-10-19)
- **What changed:** hearts, gold and subweapons are prize drops, the same entity in every stage. When the guest's hit detection marks a mirrored drop as touched, the guest runs that drop's update once. It collects into the guest's own status, with the sound and the text.
- **The authority:** `EV_TAKEN` tells it to remove its drop without a reward.
- **Edge cases:** the guest doesn't copy that slot's drop again for half a second, until the authority has removed it. The old subweapon, dropped when you take a new one, reaches the authority through the spawn relay (D57).

---
## M6 planning (2026-10-19)

**D67: Agents document, commit and push before they can run out of tokens** (owner, 2026-10-19)
This is a rule in `AGENTS.md`: at every natural checkpoint, and always before a likely cut-off, update the docs, then commit and push, marking unfinished work as such.

**D68: Ship OpenBIOS by default** (owner approved, 2026-10-19)
- **Tested:** SOTN co-op runs on OpenBIOS (PCSX-Redux's open-source BIOS, MIT) in our SwanStation core. That covers boot, new game, the save rooms, memory cards, the Load menu, and all 55 harness scenarios (`COOP_BIOS=…`).
- **What it means:** no BIOS for players to find.
- **The fallback:** a real-BIOS option in Settings, with a plain prompt naming the files that work.

**D69: The launcher never deletes or overwrites a savestate** (owner, 2026-10-19)
- **The rule:** playthroughs keep every savestate the launcher makes, compressed and uniquely named. The launcher makes them only on events (a new stage, a boss, a joint save, quitting), never on a timer: about 100–200 MB per playthrough. The space used is shown on the home screen and in Settings, with the folder and a confirmed "delete this playthrough's savestates". Players may delete them; the launcher never does on its own.
- **Debugging:** predefined debug starts, made on the player's PC because they hold game RAM, and F9 as a full environment snapshot.

**D70: Plan for online and Android now** (owner, 2026-10-19)
- **Structure:** a headless session engine under the launcher UI, and the link protocol written down (`docs/link-protocol.md`).
- **The patcher:** separate from the launcher, so the disc can be patched on a PC for an Android player.
- **The model:** ease of use after Slippi and BBLauncher.

**D71: The disc patcher ships as a patch file (resolves D9's open question)** (owner, 2026-10-19)
We publish an xdelta of `DRA.BIN`, `COOP.BIN` and a manifest; never game data. The patcher checks the user's disc and writes the co-op disc next to it.

**D72: Move the mod to its own repository** (owner, 2026-10-19)
The co-op mod moves out of the sotn-decomp fork into its own repository, to make it easier to share. Planned for M7. The mod still builds against sotn-decomp, as a dependency rather than a fork.
