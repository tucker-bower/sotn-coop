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
- **The rule:** playthroughs keep every savestate the launcher makes, compressed and uniquely named. The launcher makes them only on events (a new stage, a boss, quitting), never on a timer: about 2 MB a moment, some 200 MB per playthrough. The space used is shown on the home screen and in Settings, with the folder and a confirmed "delete this playthrough's savestates". Players may delete them; the launcher never does on its own.
- **Debugging:** predefined debug starts, made on the player's PC because they hold game RAM, and F9 as a full environment snapshot.

**D70: Plan for online and Android now** (owner, 2026-10-19)
- **Structure:** a headless session engine under the launcher UI, and the link protocol written down (`docs/link-protocol.md`).
- **The patcher:** separate from the launcher, so the disc can be patched on a PC for an Android player.
- **The model:** ease of use after Slippi and BBLauncher.

**D71: The disc patcher ships as a patch file (resolves D9's open question)** (owner, 2026-10-19)
We publish an xdelta of `DRA.BIN`, `COOP.BIN` and a manifest; never game data. The patcher checks the user's disc and writes the co-op disc next to it.

**D72: Move the mod to its own repository** (owner, 2026-10-19)
The co-op mod moves out of the sotn-decomp fork into its own repository, to make it easier to share. Planned for M7. The mod still builds against sotn-decomp, as a dependency rather than a fork.

---
## M7–M10 planning (2026-10-19)

**D73: Standalone repository target (`tucker-bower/sotn-coop`) and self-hosted CI** (owner, 2026-10-19)
- **Repository:** `mods/co-op/` moves to `tucker-bower/sotn-coop`, keeping its git commit history.
- **Dependency model:** `sotn-decomp` is fetched at a pinned commit into `.env/src/sotn-decomp` (or `decomp/`), and our 5-file upstream hook diff (`src/dra/{42398,5087C,62DEC}.c`, `tools/builds/gen.py`, `tools/sotn-assets/build.go`) is applied from a tracked patch file during bootstrap/build.
- **CI:** runs on a self-hosted runner where the retail disc and BIOS are already available on disk, verifying a clean checkout build and the full harness suite on every push/PR.

**D74: Zero-infrastructure online PC co-op with compressed, MTU-chunked snapshots** (owner / agent-default, 2026-10-19)
- **Connect codes:** zero-infrastructure P2P connection using public STUN servers (`stun.l.google.com:19302`, `stun.cloudflare.com:3478`) + UPnP port mapping where available, encoding the discovered `ip:port` into a short connect code (plus optional public WebSocket relay signaling for 1-code room matching), with a direct `ip:port` fallback.
- **Smooth UDP transport:** over the internet, raw 8 KB `SNAP` datagrams exceed path MTU (~1200–1400 bytes) and would suffer IP fragmentation drops. `SNAP` payloads are compressed (`zlib`/`zstd`) and split at the application layer into ≤ 1200-byte chunks (`TAG_SNAP` / `TAG_SNPC`), reassembled per `snap_seq`.
- **Joint saves online:** when either player saves at a save room (or when the host initiates a Continue / both-dead reload), `JointSave` relays the partner's save command and `SaveData` blob over the reliable event/control channel so both players' local memory cards and `session.coop` files stay in sync across machines.

**D75: Roadmap M8–M10: Richter & Maria from the start + DXC audio/dialogue (M8), Android port (M9), and AYN Thor dual-screen + widescreen (M10)** (owner, 2026-10-19)
- **M8 (Playable Richter & Maria + DXC dialogue/voices):** Either player can choose Alucard, Richter, or Maria from the start of a fresh playthrough. Character and audio/dialogue assets are extracted from Tucker's local *Dracula X Chronicles* USA ISO (`disks/sotn.pspus.iso`, solving D15 with a `pspus` asset map). Includes a launcher/mod option to use the alternate DXC dialogue and voice acting.
- **M9 (Android port):** Port the launcher, session engine, and SwanStation Android core integration to Android.
- **M10 (AYN Thor dual-screen & widescreen):** Curated dual-screen mode for the AYN Thor handheld: the top 6.0" 16:9 screen displays your game and the bottom 3.92" screen displays your partner's screen. Plus an expanded-FOV widescreen mode (not stretched) on the top screen.

## M7b planning (2026-10-20)
**D76: M7b polish before M8** (owner, 2026-10-20)
- M8 is tabled while Tucker decides the mixed-character rules.
- M7b scope:
  - a real release
  - mode-first launcher with lobbies
  - native menu bar, resizable window, layouts
  - widescreen spike
  - networking review under simulated real-world networks
  - stranger playtest
- **No stretch scaling mode, ever:** the picture is only shown at its true shape.
- **Ship unsigned:** the README explains the browser and SmartScreen warnings.
- **Tucker publishes each release** after testing it. The agent only makes drafts.

## M7b build (2026-10-20)
**D77: Wire protocol 9: playout online, delta snapshots, measured round trips** (agent-default, 2026-10-20; design/M7b-netcode.md)
- Online, the partner's presences and snapshots are played back through an adaptive jitter buffer: the 95th percentile of jitter, at least a frame while packets are lost, at most 250 ms.
- **Why:** shared enemies must move smoothly, because the guest's hit detection runs against the copies it sees.
- **Cost:** latency on jittery links (Wi-Fi 33 → 133 ms on the partner). The guest's own actions stay instant.
- **Not online:** couch play (one PC) doesn't use it.
- Reversible: `link/playout.py` constants.

**D78: Room codes meet on ntfy.sh, both ways, with a token** (agent-default, 2026-10-20)
- Codes look like `BAT-7K2Q` (12.6 M of them).
- Both sides post their candidates (LAN, and STUN from the game socket) to the room's hashed topic, over one streaming request each, then hole-punch.
- HELO carries a token from the room code. Only a matching HELO becomes the partner, and nothing else from other addresses is heard.
- Options considered: our own rendezvous server (infrastructure, against D74), and a manual code exchange (worse UX).

**D79: Window: Automatic layout and sharp-bilinear pixels by default** (agent-default, 2026-10-20)
- **Automatic** picks side by side or stacked, whichever gives the bigger picture.
- **Sharp** enlarges by whole pixels, then smooths the last fraction, at the true 4:3 shape (no stretch: D76). **Smooth** is plain filtering.
- **2026-10-28 (Tucker):** "Smooth" removed. Sharp is the only scaling; there's no pixel setting.

**D80: The Game menu has no Reset and no "Joint save now"** (agent-default, 2026-10-20)
- Coffins are the save points by design.
- Resetting one game of a co-op pair has no clear meaning.

**D81: The pause menu carries the View settings** (agent-default, 2026-10-20)
- Layout, Pixels and How to play, so couch players on a TV with only controllers can reach what the menu bar has.

**D82: Widescreen / expanded FOV is tabled** (Tucker, 2026-10-20)
- True expanded FOV needs a VRAM relayout of every stage (`docs/design/M10-widescreen-spike.md`: 3–6 weeks, high risk); the emulator hack does nothing for SOTN, and stretching is ruled out (D76).
- Revisit only with the side-bar co-op info idea, or not at all.

**D83: Boss debug starts carry a typical first-playthrough's progress** (agent-default, 2026-10-20)
- One start outside each of the 12 first-castle bosses (Developer › Debug starts › Bosses), made on the player's PC with the other debug starts (never shipped: D9, D69).
- **Route:** the critical path in `docs/research.md` (Slogra & Gaibon → … → Richter). **Levels** rise from 8 to 38; level-up gains are applied at the game's own averages (`CheckAndDoLevelUp`), and vessels follow the route. **Gear** is items found on the way by then (the per-area item lists in `castle_flags.h`), plus a few earlier pieces in the bag and potions. Familiar cards are found but not summoned.
- **Earlier bosses** are recorded as beaten (time attack records, `SLO_GAI_DEFEATED`), with the story flags met so far. **The map** shows every area visited so far, fully explored (from each area's own room table, read at build time).
- **The state is a real save:** it's written, then saved and loaded through the joint-save commands, so the game recomputes attack, defense and stat totals as after a memory card load.
- **Placement exceptions:** Scylla starts in her arena, right of her, with the Scylla Wyrm beaten (2026-10-27: it started in the Crystal Cloak room behind her, whose way in is barred until she's beaten). Lesser Demon starts at the bars you pass in mist form. Richter starts at his arena's door, with his intro dialogue; Holy Glasses are in the bag, not worn (equip them for Shaft's orb instead).
- **Why:** quick to tune, since each boss is one row in `launcher/bossstarts.py`. Every start is proved by a bot that walks in until the boss is there; `launcher/smoke.py` requires all 12.

**D84: M8 direction** (Tucker, 2026-10-20; one agent-default noted)
- **Characters are chosen every session** in the lobby, in any combination. The same playthrough continues with any characters, and the disc is never rebuilt for a choice: the launcher loads Maria and our Richter into expansion RAM (M8 option 1A).
- **Mixed-team puppets:** option 2A, provided it costs no performance. That's an acceptance criterion with numbers.
- **Every character gets the full Alucard castle (3A).** Richter's and Maria's progression is tied to Alucard's relics, aiming at equal power at every point; abilities that don't map are borrowed from Alucard (Mist Step). Details and the mapping: `docs/design/M8b-character-balance.md`, for Tucker's review.
- **Maria comes from the optional USA DXC disc (4A).** A clear game-files screen covers the SOTN disc, the DXC disc and the BIOS.
- **The DXC 2007 dialogue and voice option is dropped from M8 and goes on the backlog** (agent-default: Tucker said "whatever is easiest"; it's weeks of audio and script work for few players).

**D85: M8 approved options, and the backlog** (Tucker, 2026-10-21)
- **M8:** every recommended option (1A–4A) is approved. Added to M8:
  - both players' HUDs fully visible in every layout (P1's may be cut off in the 2026-10-20 footage)
  - F9 sends a bug report: a form plus the full game state, to Tucker's private storage, never anything outside the launcher window
- **M8b:** the mapping and the balance plan are accepted, including crashes gated by Echo of Bat and Alucard's equip menu. Added:
  - one-button moves: L2 high jump, R2 blade dash, on buttons Richter and Maria don't use in vanilla
  - off-hand weapons on ○, with the whip and guardians always in the other hand
- **Safety net:** a spot only Alucard can pass is still passable by a team with an Alucard player (the partner teleports). The audit still aims for full parity.
- **Backlog:** a new section at the end of `docs/ROADMAP.md`, for the most ambitious long-term ideas. Tucker moves items into milestones. It starts with the DXC dialogue/voice swap and 3–4 players.
- **Still open, for final approval:**
  - where reports go (M8 §6: a Cloudflare relay into a private repo, recommended)
  - off-hand option A
  - Alucard's spell shortcuts in M8 or on the backlog

**D86: M8 final approval** (Tucker, 2026-10-21)
- **Sending F9 reports goes on the backlog** (no hosted relay for now). The design moved to `docs/design/backlog-report-sending.md`; F9 keeps saving the local zip.
- **Off-hand weapons:** option A, using only existing art. No new animations, poses or drawn art; the swing is made from Richter's and Maria's own frames plus the weapon's own sprite, as natural as possible.
- **Alucard's spell shortcuts on the right stick are in M8.**
- **Every button shortcut is optional, per player,** set in the launcher. Off means vanilla controls.
- **Go ahead with M8.**

**D87: Button shortcuts start on, per seat; the right stick's default spells** (agent-default, 2026-10-21)
- Each seat's shortcuts (Richter/Maria: L2 high jump, R2 blade dash, ○ off-hand; Alucard: spells on the right stick) start **on**. They only use buttons the character doesn't use in vanilla, so on changes nothing a vanilla player does. Off is one press of Triangle / Y on the lobby card, or Settings › Controls.
- Right stick: ↑ Hellfire, → Soul Steal, ↓ Tetra Spirit, ← Dark Metamorphosis (the four most-used). Each direction cycles through the six castable spells or nothing in Settings › Controls. Wolf Charge and Wing Smash need a form, so they aren't on the stick.
- **How a spell is cast:** a flick plays the spell's own input sequence into the pad (module/spells.c), so the game's checks decide (known, MP, pose, Sword Brothers' familiar). It costs the sequence's frames (up to ~1.3 s for Tetra Spirit and Sword Brothers, which need up held), the same as the player typing it.
- Keyboard: player 1 gets D/W for L2/R2 and the keypad 8/6/2/4 for the stick; player 2 gets R/Y for L2/R2.
- Options considered: off by default (less discoverable, and the buttons are unused anyway); casting directly through DRA's spell functions (skips the game's own pose and MP rules).

**D88: Off-hand weapons, version 1** (agent-default, 2026-10-21; design/M8b §4.1 option A)
- ○ uses what's in a hand (the first hand holding something usable).
  - **A weapon** swings its own furthest-reaching frame (from its overlay, which the game loads), with the hilt at the player's hand, turning from raised to lowered. Fists push forward.
  - It hits with the game's numbers for that hand (`GetEquipProperties`: ATK + STR, element, hit effect, critical rate).
- **Potions** (Potion, High potion, Elixir, Manna prism) and **food** take effect at once, with DRA's amounts. Alucard's item entities are DRA's, which Richter's entity loop doesn't run, and food is dropped and picked up by its weapon overlay, which would take Richter's sprite bank.
- **Not yet:**
  - thrown items (TNT, Karma Coin...)
  - the stat and resist potions
  - weapon specials
  - the partner's puppet showing the swing: the partner's game doesn't have the weapon's sprites loaded. Their hits count either way.
- No pose change for Richter or Maria during the swing: Tucker's rule is existing art only, and their own attack poses bring their whip or guardian.

**D89: Our Richter's and Maria's code runs from the expansion RAM** (agent-default, 2026-10-21)
- Only their data (the tables DRA reads at fixed addresses, and their sprites) stays in Richter's overlay slot. Their code and BSS go to 0x805C0000, placed by the module after each load (`richter/ric.ld` and `maria/maria.ld` add a trailer with the sizes).
- **Why:** built with a modern gcc they're 220–237 KB, past 0x80170000, where familiars and the weapon overlays load. With the code moved, the slot ends at 0x801567D4 (Richter) and 0x8015CF50 (Maria), so familiars work for them too. Their entity loops run familiar entities as DRA's does (a COOP change in `pl_blueprints.c`).
- Options considered: `-Os` plus dropping unused functions (still 1.8 KB over for Richter); familiars kept off for them (a gap in the design's mapping).

**D90: The patch never carries sector checksums or retail art** (agent-default, 2026-10-21; refines D71)
- Our Richter (`COOPRIC.BIN`, M8) put Richter's retail art into the patch as literal bytes, and every changed sector's EDC/ECC with it.
- **Now:** the patch copies our Richter's art from the player's own `RIC.BIN` (BPS source copies), and stores changed sectors with their EDC/ECC zeroed. The patcher computes them on the player's PC (`patcher/sectors.py`), then checks the whole disc's CRC.
- `test_patcher.py` checks that the patch stores no checksums and nothing of the retail disc (every 64 stored bytes against every retail sector). `test_characters.py` does the same for Maria's patches against the DXC files.

**D91: Both HUDs: nothing was cut in the launcher** (agent-default, 2026-10-21; design/M8 §5)
- The 2026-10-20 footage is a 16:9 recording of the launcher maximized on a 21:9 monitor (3440×1440). That view cuts P1's HUD on the left and P2's picture on the right; on the monitor itself both were whole.
- `uxdriver.py hud` checks every layout, pixel mode and three window sizes on Windows: 144/144.
- Hardening: a remembered window size is clamped to the biggest screen there is.
- Options considered: re-laying out ultrawide windows (nothing is wrong on screen).

**D92: Performance is measured against two Alucards** (agent-default, 2026-10-21; design/M8 criterion 3)
- In the 10-minute shared fight, the game's main loop misses about 1% of frames with **two Alucards** too (686 of 72,000), in that busy room. "No dropped frames" can't be absolute.
- The criterion became "a mixed team misses no more frames than two Alucards with the same inputs (within 0.5% of play), and costs no more scanlines per frame (p99 within 5%)". Richter + Maria: 821 missed, p99 200 scanlines (two Alucards: 686, 202). Host p99 0.20 ms.

**D93: Android runs the same Python** (agent-default, 2026-10-21; Tucker delegated M9's design)
- python-for-android packages CPython, pygame (SDL2) and our `harness`/`link` code. The game runs in the app's own process (no worker processes on Android), loading the SwanStation Android core through ctypes, as the PC does.
- **Why:** one implementation of the link protocol, so Android ↔ Android and Android ↔ PC play by construction, already tested by the harness.
- Options considered: a native Kotlin app (a protocol port to keep in sync forever); RetroArch plus a companion app (two apps, no per-frame RAM mailbox).
- Online only; touch controls go on the backlog (controller-first, as the roadmap says).

**D94: On Android the player picks their disc's folder** (agent-default, 2026-10-22; design/M9 criterion 4)
- The first-start button opens Android's folder picker (one tap on "Use this folder"). The app copies the SOTN `.cue` and the `.bin` files it names (or a lone `.bin`, or a `.zip` of them, unpacked), saved under the names the `.cue` uses, with a progress bar. `platform_android.disc_files` picks the files; `launcher/test_android_disc.py` tests it.
- **Why:** Android won't let an app see the files next to a picked `.cue`, so a file picker made players long-press to multi-select every file. Picking the `.cue` alone, the natural move, couldn't work.
- Options considered: multi-select (as before); a single `.bin` (loses the audio track); `.zip` only (most rips aren't zipped).
- Android refuses the `Download` folder itself as a tree, so the README says to use a folder of its own (`Download/SOTN`).

**D95: The Android app ships debug-signed for now** (agent-default, 2026-10-22)
- `release.py` attaches `android/build.sh`'s APK as `SOTN-Coop.apk`, signed with this PC's debug key (`~/.android/debug.keystore`).
- **Why:** no key to manage while M9 is in preview. But an update only installs over an app with the same key: a build from another PC would need an uninstall, which deletes the app's saves. Before the first public Android release, decide on a release keystore and where it's backed up (Decisions needed, STATUS).

**D96: Same-network games find each other without the relay** (agent-default, 2026-10-24)
- The game's socket asks for UDP port 47811 first (any port if it's taken), and while looking for the partner it broadcasts the room's `HELO` on the LAN to that port, twice a second, beside the relay's hole punching (`link/connect.py`, `docs/link-protocol.md`).
- **Why:** in the Thor tests (rounds 3–4) the relay was unreachable from Android, and nothing could connect at all, though both devices were on one Wi-Fi. Same-network play is common (a phone and a PC at home), and it now needs neither ntfy.sh nor STUN. A fixed port also makes a hand-made port forward or an ip:port join predictable.
- The lobby says at once when the relay can't be reached ("Can't reach the room-code server · Looking on this Wi-Fi") and the five-minute failure names it, instead of "Waiting for your partner's game". A failed relay post is retried after 5 s (was 20 s), and the relay's reader stops when a connect attempt ends (each retry had left one streaming forever).
- Options considered: LAN only by typing ip:port (as before: no help to a player who doesn't know their address); multicast/mDNS (needs Android's MulticastLock and more code, for the same result); a second relay service (keeps the internet dependency).
- Windows Firewall lets the partner's unicast answer back in after our broadcast (its default "unicast response to broadcast" rule), so no firewall rule is needed. The per-user installer couldn't add one anyway.

**D97: Castles: any partner continues any save; solo; one shared level** (Tucker, 2026-10-25; `docs/design/M11-castles.md`)
- A castle is the only save concept: the shared world and two slots. Slot 1 is always the player on this machine, slot 2 whoever plays with them. There are no player names or seats.
- The host picks the castle. The joiner keeps a copy at every joint save, and can play it solo or host it later. No merging. Old playthroughs aren't converted.
- Level is shared: a kill's XP is halved while a partner is linked, and the gain goes to both games. Solo turns off the duo balancing (2× boss HP, aggro switching, the XP cut).
- Names: `<typed name>_<created>`, e.g. `Tucker_2026-10-25-21:40`.

**D98: M11's implementation defaults** (agent-default, 2026-10-25)
- **The joiner's copy:** it's updated in place while it has only ever received. Once played here (solo, couch, hosting), the next copy from a host is a new entry, `… (2)`. Nothing played is overwritten.
- **The host names its castle in its HELO** (`Host.set_castle`), so the joiner knows it in the lobby, before any save. That's no wire change: old hosts simply don't send it.
- **A save with no linked partner** (solo, or a partner gone for 10 s), or one whose partner never answers within 5 s, writes slot 1 alone and keeps slot 2.
- **On load,** a missing slot 2 is a copy of slot 1, and both slots get the higher XP. The game then levels the behind one up the normal way.
- **The castle list** is skipped when there are no castles: New castle, at once. The list shows the newest 7.
- **The folder** takes the castle's name after the session that gave it one (e.g. `Tucker_2026-10-25-21-40`), because Windows can't rename it while files are open.
- **Single-game sessions** (solo, online) use card `A`: slot 1 is this player on every machine.
- **Home order:** Solo, Couch co-op, Online co-op. Solo is the big button.

**D99: M11 finish: Solo's status bar, its tests, version 0.11.0-dev** (agent-default, 2026-10-25)
- **Solo's status bar says "Solo"** (no partner, ping or Together/Apart). It had said "Partner connected · ping ? ms" for a solo game: the online status line read a partner age that starts at 0.
- **The playtest build is 0.11.0-dev**, after the milestone (as 0.9.0-dev was M9's). Its patch differs from 0.9.0's (`EV_EXP`), so a 0.9.0 partner is refused by name.
- **Criterion 4 and 5's tests:** `m11_copy` covers both halves of criterion 4 (B hosts its copy, C joins). Criterion 5's rule (a played copy is never overwritten; `(2)`) is tested on the castle files in `launcher/test_castles.py`, without games: the games only decide when a save happens, which `m11_copy` covers.
- **Criterion 8 on Android:** the online join script (used by the Android pair tests) checks the joiner keeps a copy of the host's castle at connect; the save into it is `m11_copy`'s (the same `OnlineSession` code, in-process on Android).

**D100: A joiner with a room code only takes a HELO with that room's token** (agent, 2026-10-25)
- Found by `android_room` while the harness ran on the same PC: the PC joiner's LAN broadcast (D96) was answered by one of the harness's games (no room code), and the joiner took it as its partner. The Android host was left waiting. A real house could do the same with any game joined by ip:port.
- `Host._check_hello`: with a room code, a HELO with no room token is accepted only by a host (its partner typed our ip:port, the fallback). A joiner requires the room's token. `link/test_connect.py` covers both.

**D101: Leaving says goodbye** (agent-default, 2026-10-26; playtest 2026-10-25 note 5)
- A closing app (or one going back to its menu) sends `BYE` three times, unacknowledged: it's closing. The partner's launcher pauses once with "Your partner left the game. You can keep playing alone." Silence for 10 s without a goodbye: "Lost contact with your partner…", once. Both clear when the partner comes back (a new host sid).
- Considered: a reliable control message (needs acks from an app that's already closing); only the status bar (what failed on the Thor: nobody reads it mid-game).

**D102: The prologue is co-op, and scenes are held for each other** (agent-default, 2026-10-26; playtest 2026-10-25 note 1)
- The prologue is a shared room (one Dracula): both fall into its ending together. No teleports in or out of it.
- A scene pulls the partner in from the same room too (not only from another room), and waits up to 60 s (not 10) for a partner still on its way: loading, in the opening video, or still in the prologue.
- End barrier: whoever's scene ends first waits up to 10 s, so both get control back on the same frame (60 s froze a player whose partner stood still in a scene that only moves on while a direction is held).
- Considered: leaving the prologue solo (what playtest 3 hit); holding only the start (scenes driven by where each player stands drift apart).

**D103: Where a partner arrives, and no shared room while the game steers the player** (agent, 2026-10-26)
- The presence's ground spot resets on entering a room (by the tilemap's cell: the room id lags) and stays put during a scene. A pulled-in partner arrives where the scene started. Before, the partner was sent to the previous room's coordinates, or to where the scene had walked the leader, and Death's scene walked it out of the room, again and again.
- A shared room doesn't form while the game steers the player (`demo_timer`), though one already shared stays shared. As a guest, the partner's Death was the leader's copy and never took the partner's gear.

**D104: Maria's guardians are re-uploaded after a hand weapon loads** (agent-default, 2026-10-26; playtest 2026-10-25 note 4)
- DRA loads a hand weapon's graphics where Maria's PS1 layout puts four guardians (owl, cardinal, dragon, doll). After every weapon load in her game, the module calls her `MARIA_Load` (exported at 0x8013C1F4; her palettes move to 0x8013C1F8).
- Cost: her off-hand weapon is then drawn from her guardians' tiles. That's part of the off-hand decision (note 3), which the fix for drawing it waits on.
- Considered: moving her guardians, or the weapons, to free VRAM. A survey (`harness/vram_survey.py`, VRAM read out of savestates) found no 64×32 block that's unused in every stage, so there's no known-safe spot yet.

**D105: Off-hand weapons work exactly like Alucard's** (Tucker, 2026-10-26; playtest 2026-10-25 note 3)
- Richter's and Maria's off-hand runs the weapon's own overlay code (option B of design/M8b §4.1), fed a virtual Alucard swing: the same sprite, timing (wind-up), hitboxes and specials as Alucard's. Replaces D88's version 1 (the weapon's frame swept in an arc).
- Plan: `docs/design/M12b-offhand-like-alucard.md`. Spike first (6 weapon classes); every hand item is then covered by the M12 hand-item test.

**D106: Graphics live in the 8MB RAM and pass through a small VRAM window** (agent-default, 2026-10-26; Tucker's question)
- The 8MB expansion is RAM: the GPU draws only from its own 1MB VRAM. But any graphics can be kept in the 8MB and uploaded, a frame's worth at a time, into one small VRAM window just before they're drawn, as the partner puppet already does (its page at 0x1C0,0x100).
- This replaces "find a free 64×128 area per weapon" (D104's blocker): weapon tile sheets (own off-hand, partner's hand weapons) are copied to the 8MB when loaded and drawn through the window; Maria's guardians keep their VRAM.
- **The window: x 0x1E0-0x1FF, y 0x100-0x1DF** (32×224 words, in the puppet's page beside its frame slot). Proved unused by corruption: `vram_survey.window_free` fills it with garbage in a savestate and compares 2-3 s of play and of the pause menu, over 29 states (the library, the debug and boss starts): no difference anywhere. The method catches smaller used areas (controls at 0x200 and 0x280: every frame differs).

**D107: A shared-room guest runs its own red and sealed doors** (agent-default, 2026-10-27)
- Found by `m12_boss_ar_olrox`: when the partner was the room's authority, a guest Alucard was walled in at the sealed door outside Olrox's room. Doors open only for their own game's player, and the guest got the authority's closed door, tiles included (the room's tiles come with the snapshot since M5). A guest couldn't open any red door either: in real play, whoever entered a room second couldn't leave it through a door until the first player did.
- Now `EntityRedDoor` and `EntitySealedDoor` are on each overlay's list of entities a guest runs itself (`scripts/gen_overlay_table.py`). The local door writes its own tiles after the authority's are copied in. What locks a boss room's door (NZ1's `g_bossDoorsLocked`) lives in the BSS, which the guest still gets from the authority. `guest_blocked_by_closed_door` (M5) checks that a locked boss room stays locked for the guest.
- Cost: each game shows its own door, so a partner can be seen walking through a door that's closed on your screen.
- Considered: the guest asking the authority to open its door. Rejected because a sealed door also steers the player who opens it (it walks them through), so the authority's player would be moved.

**D108: The everyday suite runs in parallel, the long tests before playtest builds** (agent-default, 2026-10-27; Tucker: the suite was slowing development to a halt)
- `harness/run.py` runs each test in its own process, the cores less 4 at once (12 on this PC: a few left for its own use), longest first by the last run's time. The tests that time the host in real time (`run.SOLO`: the mixed soaks' p99) run alone at the end: at 14 at once `mixed_soak_short` measured 1.10 ms against its 1 ms budget. Session tests step a simulated clock, so they're deterministic under load; the tests with real sockets, relays or LAN broadcasts (`run.NETWORK_MODULES`) share one lane. Maria's blob is built once before the workers start.
- **Everyday suite:** everything but the names ending `min` or `_long`. `run.py --full` adds them and is the check before a playtest build (AGENTS.md).
- **Trimmed, no coverage lost:** `teleport_fuzz` is 60 teleports (200: `teleport_fuzz_long`). The three 72-weapon sweeps are six halves, and Alucard's reference results are committed (`harness/data/hand_items_alucard.json`: item ids and pass/fail flags, no game data), so Richter's and Maria's halves no longer wait for his.
- **Removed:** the M12b spike's `m12b_offhand_like_alucard_{richter,maria}` and `m12b_alucard_baseline`: 6 weapons, passing at 5 of 6, fully covered by the hand-item sweeps (all 72, item by item).
- **Measured (2026-10-27):** 155 tests: about 1.2 h one after another (3300 s of tests plus start-up); in parallel 600 s at 7 at once, 505 s at 10, 486 s at 12 (the default), 454 s at 14. All pass.
- Kept, though large: every boss in every pairing (36 tests, about 30% of the time). Each pairing has found its own bugs (D107), and in parallel they cost minutes.

---
## 2026-10-27: expanded scope (after the comparison with sotn-online-coop)

**D109: Expanded scope and priority order: M12 (v1.0) → M13 → M14 → M15 → M16 → M17 → M18 → M19** (Tucker, 2026-10-27)
- Goal: the best, most open, most durable, most complete and easiest-to-use version of this idea. A similar project appeared (`jweyden/sotn-online-coop`, on SymphonyRecomp: `research.md` → "sotn-online-coop").
- Order: finish M12 into a public v1.0; the partner as a real second player (M13); every pair connects with no server of ours (M14); PvP (M15); Saturn characters (M16); 3+ players (M17, replaces D48); Mac and Linux (M18); widescreen (M19).
- The timeline is extended to fit Pro's limits; Pro stays the budget.

**D110: Boss fights pause when either player opens the menu** (Tucker, 2026-10-27)
- Today's behaviour stays. The other project keeps a boss fight running through the menu; we don't. Guarded by a regression test in M12.

**D111: To the backlog: power tuning, more characters' testing, the Thor's dual screen, community characters** (Tucker, 2026-10-27)
- Tuning and testing more characters is easier with community feedback on a playable build: easy and fun first.
- The Thor's dual screen helps only Thor owners. M10's widescreen part is M19.
- A guide and format for community characters (for example, Soma) is a backlog item.

**D112: Android release keystore, backed up in Tucker's password manager** (Tucker, 2026-10-27; replaces D95)
- Option (a) of STATUS's signing decision. The keystore and its password never go in the repository; the build reads the keystore's path from `env.toml`.
- The last debug-signed build moves the app's saves to shared storage first, so the switch doesn't lose them (`design/M12-v1-release.md`).

**D113: The mod never requires a hosted server; a relay is the last step, and anyone's** (Tucker, 2026-10-27; keeps D74)
- Every pair should connect with no choices by the player. IPv6, router port mapping and port prediction come first; a relay that any player's launcher or anyone's server can run is the last step (`design/M14-relay.md`). Replaces STATUS's "Symmetric NAT" decision.

**D114: v1.0 ships after the first-castle playthrough; the inverted castle is v1.1** (Tucker, 2026-10-27)
- `design/M12-v1-release.md` decision 1. The launch black screen is the 19 s black start (Tucker agreed with the assumption).

**D115: The Mac build ships unsigned, with the steps in the README** (Tucker, 2026-10-27)
- `design/M18-mac-linux.md`: no Apple Developer ID for now.

**D116: The key switch is a USB backup and restore, not an in-app move to shared storage** (agent-default, 2026-10-27; revises D112's migration)
- No APK has ever been published (v0.7.1 has none; v0.11.0 is a draft), so the only debug-signed installs are Tucker's Thor and the test emulators. `android/device.py switch-key` backs up the app's folder over USB, uninstalls, installs the release-signed APK, and puts the folder back.
- Files adb writes into the app's folder are unreadable to the app, and `run-as` can't reach shared storage, so the backup goes into the app's private folder and the app copies it into place at its next start (`android/main.py` `restore`), as its own files. Nothing already there is overwritten.
- **Release-signed builds stay debuggable** (as today's): the tests and this restore use `run-as`. Only someone with USB debugging access to the device can use it.
- Evidence: `android/test_key_switch.py` (emulator, Android 14): every file back with the same contents, owned by the new app, release-signed. `release.py --android` refuses an APK not signed with the release key (checked with the 0.12.0-dev debug APK).

**D117: The launcher ships OpenBIOS built with FASTBOOT; the old build stays for old savestates** (agent-default, 2026-10-27; M12 v1.0 criterion 6)
- Measured in the real launcher (`uxdriver.py startup`): the title came 23.1 s after pressing Solo. Two causes:
  - **The 2× disc read switched itself off at frame 113.** During the BIOS, `g_GameState`'s address holds a 2 for one frame. Now the title has to last 10 frames.
  - **PCSX-Redux's standard OpenBIOS waits about 300 frames (5 s) before starting the disc.** The harness has always used OpenBIOS built with `FASTBOOT=true` (`scripts/bootstrap.sh`, the same source and licence), and all its tests run on it. After the disc's program starts, the two are identical (frame for frame).
- Now: **a picture 0.4 s after pressing Solo, the title at 18.2 s** (was 23.1 s; target 20 s).
- The release and the APK ship it as `bios/openbios-fast.bin`, the default. PCSX-Redux's `openbios.bin` stays beside it: a savestate holds the BIOS's RAM, so it only loads on the BIOS that made it. Each new savestate pair gets a `.bios` note; "Go back to a moment" boots the BIOS it names, and pairs from before 0.12 (no note) boot the old one (or the player's own BIOS, if they chose one). Debug starts are kept per BIOS (`<disc>@<bios>`), so they're remade once.
- Our disc still reaches the title 84 frames (1.4 s) after retail (the co-op module and Richter loading). Left as is.

**D118: Maria keeps her guardian when she picks up a Bible** (agent-default, 2026-10-27; found by `m12_subweapons_maria`)
- The Maria port's glue (`mods/mariapsp-forpsx/maria.c`, upstream) turns Alucard's subweapons into her guardians: dagger → cat, axe → cardinal, holy water → turtle, vibhuti → dragon. The cross, stopwatch, rebound stone and agunea keep the guardian she has and give a heart back. The **bible** was mapped to none: picking one up left her nothing to throw.
- Now the bible is like the other four (`patches/sotn-decomp.patch`, one hunk). Considered: mapping the five to the doll (her fifth guardian), which isn't selectable in the port and would need its graphics loaded.

**D119: "Every room, every character" is proved by movement envelopes, not a tile planner** (agent-default, 2026-10-27; changes the method of `design/M12-v1-release.md` option B)
- If, with the same relics, Richter and Maria jump at least as high and as far as Alucard, every room Alucard can cross with those relics they can cross too. The room's other gates have per-character tests already (mist grates, low gaps, poison water; blue doors and the ferryman read only the relic). `m12_envelope_{richter,maria}` measures each relic step against Alucard's from the same spot.
- **Why:** a collision-tile planner with each character's physics is several usage windows and its own source of false results; the envelope is one test, measured in the real game.
- It found two gaps (a decision for Tucker, STATUS): with Gravity Boots, Maria's high jump reaches 191 px and Richter's 261 px against Alucard's 331 px; with the Leap Stone only, Richter's backflip adds little height (63 px against 101 px). Climbing with the Soul of Bat is unlimited for both.

**D120: The first-castle playthrough is chained by boss, with teleports between** (agent-default, 2026-10-27; `design/M12-v1-release.md` work item 4)
- `m12_chain_first_castle_long`: both games play the 12 bosses in route order, carrying what they earn; between bosses, the teleport, and that stretch's relics and story flags. Walking the routes is left to the gate and movement tests (D119): scripted routes for every stretch would be several usage windows and brittle.
- Time-attack records are reported, not asserted: a scripted kill can skip the death sequence that writes one.

**D121: Everything planned for 1.0 ships now as 0.12.0, the public beta; 1.0 after playtesters' feedback** (Tucker, 2026-10-27)
- A normal GitHub release, not a "pre-release": the README's download links use `releases/latest`, which skips pre-releases. The notes say it's the beta and ask for feedback (GitHub issues, F9 reports).

**D123: Online play connects the way Slippi does: direct, plus what to try when it fails; no relays** (Tucker, 2026-10-28; cuts down `design/M14-relay.md`)
- The game tries a direct connection (hole punching, the LAN broadcast) and asks the router to open its port (UPnP IGD, NAT-PMP). When nothing works, the lobby says what either player can do: turn on UPnP, forward UDP 47811, or use another network (not a phone hotspot).
- Options considered: launchers relaying for each other, opt-in or on by default (each helper's public IP is posted on a public ntfy topic); community relays listed in the repo (may be none at launch). Rejected as complexity for a few percent of pairs. Slippi and Dolphin netplay run no relays; games with relays get them from a platform (Steam, Epic) or a paid server (RetroArch), against D74.
- `link/relay.py` and the transport's relay mode stay, marked unused and still tested: a starting point for an invested player to run their own (`COOP_RELAYS`). IPv6 and port prediction are deferred until playtest reports say how often pairs get stuck.
**D122: Richter and Maria get extra jumps, not higher jumps** (Tucker, 2026-10-27; closes the gaps D119 found)
- Each of the Leap Stone and the Gravity Boots gives Richter and Maria one jump in the air, refilled on landing (`g_CoopAirJumps`, `COOP_AIR_JUMPS` in `richter/coop_ric.h`). The jump heights stay as they are.
- Richter's backflip keeps its vanilla moment (jump again just after leaving the ground) and costs one; any other press in the air, or falling off a ledge, is a plain jump. Maria's double jump is her Leap Stone jump, and her Gravity Boots jump is her own high jump, done in the air (her double jump alone left her 105 px short); a press uses the double jump first, Up asks for the high jump. The Soul of Bat's climbing re-arm is unchanged.
- Measured (`m12_envelope_*`): with the Leap Stone, Richter 121 px, Maria 104, Alucard 106; with the Gravity Boots too, Richter 375, Maria 425, Alucard 375.

**D124: The partner's body draws its own attacks; a hand weapon that isn't ours comes from the link** (agent-default, 2026-10-28; `design/M13-partner-player.md` step 1)
- The body gets the partner's status (stats, level, equipment) from its host, so DRA's own code (subweapons, spells, poses) runs right in it. The partner's attack sprites and primitives from the link (M12) aren't placed while the body is shown: they doubled its own.
- A hand weapon different from this player's runs from the partner's weapon overlay, which isn't in this game. The body strikes the poses (DRA's), its weapon entity is dropped by our overlay, and the partner's real swing is drawn from the link (weapons.c, D106) at the body's spot.
- Options considered: swapping the partner's overlay into 0x8017A000 around the body's frame and drawing (12 KB a hand, both ways, twice a frame during attacks, and a FlushCache each time: costly on Android's recompiler, and the sheet would still need the VRAM bank). Reversible: the swap can come later with the VRAM bank (step 2).

**D125: VRAM's second bank is addressed by spare bits; every platform ships our own core build** (agent-default, 2026-10-28; `design/M13-partner-player.md` step 2)
- Uploads and fills: bit 9 of y (the PS1 masks it away, so retail code never sets it). Texture reads: bit 14 of the texpage (unused by the GPU in polygon attributes and E1). Palettes: bit 15 of the clut (rows 512 and up). Separate texture and palette flags, so a partner of the same character can keep using player 1's palettes. Software renderer only (the hardware renderers ignore the bank).
- Savestates: version 58, 12 MB with both banks; version 57 states load with an empty second bank.
- The Windows DLL and the Android cores were downloaded builds of a newer SwanStation than our pinned Linux one, so a Windows savestate didn't load in the harness (Tucker's 0.12.0 report). Now all three are built from the pinned source plus our patch (MinGW for Windows, the NDK for Android). `harness/core_check.py` checks a build: Linux and Windows give identical RAM and VRAM hashes.
- Options considered: a second VRAM array selected by a GPU register (state outside the primitives, wrong for the ordering table); keeping the page-to-the-left workaround (no room for other characters, weapons or familiars).
