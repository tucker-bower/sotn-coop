# Status

_Last updated: 2026-10-27 (scope expanded, D109: M12 → v1.0, then M13–M19; designs approved; M12 v1.0 in progress)_

## Done
- Forked sotn-decomp, `coop` branch. Project docs, research, scope change D7 (Richter as P2, 8MB).
- **Dev environment (D11–D13):** `bootstrap.sh` sets up a fresh Ubuntu 26.04/WSL2 machine, `doctor.py` verifies it in about 1 s, and `env.example.toml` says where everything lives. The us build matches retail 115/115 locally.
- **M0 built** (`coop-m0-harness`): harness (25× real time, savestates in 22 s, room-walk scenario, 10-min lockstep with rollback, headless PCSX-Redux check).
- **Re-plan (2026-10-18):** independent exploration, with one game per player and shared progression (D19–D31).
- **M1–M3 landed** (PR #4): `COOP.BIN` loader, puppet, map marker, live shared progression (flags, map, relics, items, gold, max-stats), door-transition `Arrive`, teleport, respawn, pause freeze, and joint saves.
- **M3b, M4, M4b, M5 built and passing** (PRs #5, #6): memory-card joint saves, authority/guest shared rooms, 2× HP bosses with aggro switching and no mid-boss respawn, cutscene pull-in, autonomous playtest tooling (`harness/playtest.py`, `harness/replay.py`).
- **M6 built and verified** (`coop-m6-playable`): Windows installer, disc patcher (`sotn-coop.bps`, 222 KB, zero game data), bundled OpenBIOS, event savestates with visible storage, F9 snapshots, and link protocol spec (`docs/link-protocol.md`).
- **M7 built and verified** (`coop-m7-repo-online`, pushed to standalone repo [`tucker-bower/sotn-coop`](https://github.com/tucker-bower/sotn-coop)):
  - **Standalone repository (`tucker-bower/sotn-coop`, D72/D73):** full git history preserved (`git subtree split`, 48 commits), builds against pinned `Xeeynamo/sotn-decomp @ d12b397f36` via `patches/sotn-decomp.patch` (5 files, 38 lines), with `.github/workflows/ci.yml` for self-hosted CI and game-data hygiene checks. Clean clone verified at `/home/tucker/sotn-coop`.
  - **Online PC co-op (D74):** `"Play online"` flow in the launcher (`Host online` / `Join online`), zero-infrastructure 6-char room codes + 10-char base32 STUN endpoint codes + direct `ip:port` fallback (`link/rendezvous.py`), `zlib`-compressed MTU-chunked (`<= 1200` bytes) shared-room snapshots (`TAG_SNPC`), reliable online joint saves / Continue / both-dead reload (`TAG_CTRL`/`TAG_CACK`), and version mismatch refusal UI.
  - **Tests:** 61/61 multi-instance harness scenarios pass (including `online_connect_codes`, `online_version_mismatch`, `online_mtu_and_loss`, `online_joint_save`), plus `launcher/smoke.py` (`check_online`) and `patcher/test_patcher.py`.
  - **Release installer updated:** `SOTN-Coop-setup-0.7.0.exe` in `Emulators\SOTN-Coop-release\`.
- **Roadmap updated with M8–M10 (D75):**
  - **M8:** Maria and Richter playable by either player from the start of a fresh playthrough (using local `disks/sotn.pspus.iso`), plus optional DXC alternate dialogue and voice acting.
  - **M9:** Android port of the launcher and session engine.
  - **M10:** AYN Thor curated dual-screen support (top screen = you, bottom screen = partner) + true expanded-FOV widescreen on the top screen.

- **M7b built** (`coop-m7b-polish`, design `docs/design/M7b-polish.md`, all 9 criteria with evidence):
  - **Release:** `scripts/release.py` builds a **draft** GitHub release `v0.7.1` (installer + SHA-256), with a game-data check. The README is rewritten for first-time players.
  - **Launcher:** a mode-first home, a couch lobby (press a button to join, characters with Richter/Maria locked, ready), and an online lobby with room code and ping. A native Windows menu bar, a resizable window, fullscreen, layouts (automatic, side by side, stacked, one player, two windows), and sharp 4:3 pixels: 60 fps at every size on Windows. An unplugged controller pauses its game. The pause menu carries the View settings. Help pages, and an icon.
  - **Netcode (wire v9):**
    - a playout/jitter buffer
    - XOR-delta snapshots (841 → about 250 kbit/s)
    - round trips measured for free
    - resends on a measured timeout
    - STUN on the game socket, two-way rendezvous, hole punching, a room token, restarts handled
  - **Before/after on simulated networks:** transatlantic stutter 24.7% → 1.7%, bad Wi-Fi 36% → 1.8%. Routers: 12/16 kinds of pairings connect, and the other 4 fail with a reason.
  - **Stranger playtest** (`docs/playtest/M7b-stranger.md`): found and fixed a silent crash when the installer starts the launcher (Windows RedirectionGuard), a lobby crash with real controllers, LAN candidates, an unclean uninstall, and missing glyphs.
  - **Widescreen spike** (`docs/design/M10-widescreen-spike.md`): the emulator hack does nothing for SOTN, and true FOV is blocked by VRAM.

- **After M7b (2026-10-20, branch `coop-fix-dualsense`):**
  - **Controller fixes from Tucker's test:** a PS5 controller that re-appears ~7 s after start was never opened, and a controller with id 0 could ready up but never start the game. The couch walkthrough now uses id 0.
  - **Boss debug starts (D83):** Developer › Debug starts › Bosses has one start outside each of the 12 first-castle bosses, with a typical player's level, gold, gear, relics, map and beaten bosses. A bot proves each one reaches its boss, and `smoke.py` requires all 12. They take about 51 s to make on Tucker's PC, along with the other debug starts.

- **Playtest fixes (2026-10-20 evening, `docs/playtest/2026-10-20-tucker-couch.md`, branch `coop-fix-cutscene-audio`):**
  - Cutscenes play in step: the leader holds, followers are flagged, there's a cooldown, and no shared room while your own scene runs. That ends the Maria loop.
  - The couch mix no longer doubles the same sound (no clipping).
  - Audio stats in F9 reports.
  - Debug starts are tied to their patch.
  - 63/63 harness and smoke pass.
  - **The published v0.7.1 installer was replaced with this build by mistake** (release.py now refuses to touch a published release).

## In flight
- **M12: the agent plays the game (coverage) + playtest 3 fixes + M12b off-hands** (2026-10-26, branch `coop-m12-coverage`, not merged). Designs: `docs/design/M12-coverage.md` (Tucker asked for this coverage directly; approval only needed for part 4, the chained playthrough), `docs/design/M12b-offhand-like-alucard.md` (D105). Playtest notes, triage and status per note: `docs/playtest/2026-10-25-tucker-thor-pc.md`.
  - **Playtest 3 notes:**
    1. **Cutscenes: fixed** for every scene tested (D102, D103): the prologue is co-op (one Dracula, scenes held both ways), Death waits for a partner still in the prologue, a pulled-in partner arrives where the scene started, both get control back on the same frame. Found and fixed on the way: the partner kept Alucard's gear after Death's scene. Tests: `m12_prologue_opening`, `m12_prologue_fight`, `m12_death_waits_for_partner`, `m12_scene_*` (Succubus, Richter, Castle Keep, Maria in the Alchemy Lab), `cutscene_*` (M5: Maria in the Marble Gallery).
    2. **Partner's attacks on screen: phases 1 and 2 built.** Phase 2 (2026-10-27, `module/weapons.c`, link version 11): the partner's hand-weapon swings. When a weapon loads, each game copies its overlay, sheet and 24 palettes to the 8MB; the host sends them (reliable control channel) when they change; the partner's game draws the swing's sprites itself through the VRAM window. `m12_partner_swing_drawn` (Alucard next to Alucard) and `_richter` (Richter's off-hand sword next to Alucard) pass. Not yet: the 5 weapons with a second sprite bank, rotated/scaled frames (drawn upright); the blade's colour looks bluish, to check against the swinger's own screen. Phase 1: Each game sends its own attack entities' sprites and primitives (most attacks draw with primitives: Alucard's subweapons, Richter's whip) with presence, and the partner's game draws them itself (`module/sprites.c`, link version 10). `m12_partner_dagger_drawn`, `m12_partner_attack_drawn`. Phase 2: hand-weapon swings (their tile sheet is only in the swinger's VRAM: copy it through the 8MB, D106).
    3. **Off-hands like Alucard's: built (D105, M12b).** The weapon's own overlay code runs with a virtual Alucard swing: all 72 hand weapons behave in Richter's and Maria's off hand exactly as in Alucard's hands, item by item (`m12_hand_items_*`); swings filmed frame by frame match. Maria's weapon draws from its own sheet (D106). Open: some frames' palette (a raised blade blue instead of white), thrown items (TNT, Karma Coin).
    4. **Maria's guardians: fixed** (D104): weapon graphics overwrote them (the skull and shield, or invisible birds). `m12_maria_guardians_keep_their_graphics`, `m12_maria_keeps_throwing`. Her cardinal can't be thrown moving or in the air (DXC's rule).
    5. **Leaving: fixed** (D101): `online_partner_leaves`, `test_connect`.
  - **Coverage (M12 parts 1-3):**
    - **Scenes:** see note 1. Open (`session_m12.OPEN_SCENES`): the Librarian (his scene starts when its entity spawns; why it doesn't in the harness is open), Maria in the chapel, Maria in the Center (the harness arrives on the wrong floor), the inverted castle (Shaft, Dracula, the ending).
    - **2026-10-27, after the PC crash:** both of the suite's failures fixed. **A+R at Olrox was a real co-op bug, not the walk:** a shared-room guest couldn't open a red or sealed door until the room's authority went through it (it got the authority's closed door, tiles included). Now each game runs its own doors (D107): `m12_boss_ar_olrox`, new `m12_guest_opens_red_door`, and M5's `guest_blocked_by_closed_door` (a locked boss room stays locked) pass. **Scylla:** her start was in the Crystal Cloak room behind her, whose way in is barred until she's beaten. It's now in her arena: `m12_boss_scylla`, `_rm_`, `_ar_` pass. The 0.12.0-dev build on the PC doesn't have these yet.
    - **Bosses: 12 of 12** first-castle bosses pass the two-game flow (Scylla since 2026-10-27) (`m12_boss_*`: pull-in, the fight with the players kept alive and the last hit scripted when the bot can't land it, both fine after, the same flags). The Succubus now passes: a partner in the same wide arena but too far to share it is pulled to the other, once per fight. **Scylla:** her arena pushes the player back out (a single game too: the start lacks something she needs; a fixture problem). **Pairings** (`m12_boss_rm_*`, `m12_boss_ar_*`): Richter + Maria and Alucard + Richter, 19 of 20 pass (A+R at Olrox: the walk from the door doesn't get Alucard in); the Succubus has no pairing tests (no saving in the Nightmare, so no character change at her door). A flying boss leaving a camera made the games pull each other back and forth: fixed (a 10 s boss-pull cooldown). Not yet: the inverted castle.
    - **Hand items: all 72 weapons** for Alucard, Richter, Maria (`m12_hand_items_*`). Not yet: obstacles per character, abilities per character.
  - **Tools:** `fixtures_m12.py` (prologue and castle-start fixtures), the debug and boss starts built by the harness (`.env/fixtures/debug-starts`), `vram_survey.py` (VRAM read out of savestates; `window_free` proves a VRAM area unused), `scenarios_m12.pin_target` (an enemy kept on a weapon's live hitbox).
  - **Suite (2026-10-27 morning): 150 of 152 pass.** The two (Scylla, A+R at Olrox) are fixed since; **2026-10-27: 155 of 155 pass** (with D107 and phase 2), in 8 minutes: the suite now runs in parallel (D108; `run.py --full` adds the long soaks, before a playtest build).
  - **Rebuilding after a module change:** `scripts/rebuild_fixtures.sh` (disc, Maria, savestates, M12 fixtures, debug starts; about 15 min), or only the starts: `scripts/make_debug_starts.py`.
  - **Playtest build 0.12.0-dev:** installed on the PC (silent install, 2026-10-27); the Thor's APK is built (`.env/android/SOTN-Coop-0.12.0-dev.apk`), to install when it's plugged in. What to try: `docs/playtest/M12-playtest.md`.
- **M9 Android (design `docs/design/M9-android.md`, D93–D95), branch `coop-m9-android`. Ready for Tucker's Thor playtest (`docs/playtest/M9-thor.md`).**
  - Builds: `.env/android/SOTN-Coop-0.9.0-dev.apk` (arm64 + x86_64) and the matching PC installer `Emulators\SOTN-Coop-release\SOTN-Coop-setup-0.9.0-dev.exe`.
  - Cross-play, all three ways passing: `android_pair` (100 s), `android_pc` (PC hosts, 66 s), `android_pc_join` (Android hosts, 50 s), with sound on.
  - Disc setup (D94): pick the folder; the rip is found up to 4 folders deep, and its `.bin` files anywhere by name. There's a "Pick the files instead" fallback, plain errors, and a failed disc's copy is deleted. Checked through Android's real picker; `launcher/test_android_disc.py` passes.
  - Fixed:
    - a sound deadlock that froze online sessions
    - a stalled sound channel
    - Back closed the app (it now pauses)
    - pyjnius arm64 build
  - Confirmed: the screen stays on (`KEEP_SCREEN_ON`); frames take about 13 ms on the emulator.
  - Progress screens show a vial of blood filling up.
  - `android/device.py`: install, disc and log over USB through Windows adb (`Emulators\android-tools`).
  - **Thor playtest, round 1 (2026-10-22):** installed over USB (`device.py` now runs Windows adb on its own port, 5038: the default port reached WSL's adb server, which can't see USB). Thor hosting, PC joining, didn't connect: the PC still ran **0.7.1** (Oct 20), whose lobby can't start with controller id 0 and which can't talk to 0.9.0-dev. Fixed since:
    - room-code connect waits **5 minutes** (was 30 s), with a "Still looking: m:ss left" countdown on the partner card (`link/test_connect.py` passes);
    - `uxdriver online` joins with Tucker's presses (controller id 0: A, then Start): passes;
    - the vial's cork is centred (M10: a metal bat in its place, in ROADMAP).
  - **Round 2:** same symptom: the 0.9.0-dev installer had never been run (Windows still listed 0.7.1). The agent installed it silently. Also found and fixed:
    - **after an update, the co-op disc stayed the old version** (0.7's), while HELO claimed the new patch CRC. The launcher now remakes it once from the player's own disc ("Updating the co-op disc"), and asks for the disc again if it moved. Checked with the real 0.7.0 → 0.9.0 patches.
  - **Round 3:** both sides "Still looking". **Android couldn't reach the room-code relay at all:** its Python has no CA certificates, so every HTTPS request to ntfy.sh failed, silently. The Android tests had always joined by ip:port, so they never caught it. Fixed: android/main.py makes a CA file from Android's own trusted CAs, and the relay uses it; relay errors are now logged. New `android/test_pair.py --room` (an emulator hosts, the PC types the room code, over the real ntfy.sh): **PASSED android_room (67 s)**.
    - **different versions now say so within seconds**, by name ("Your partner has an older SOTN Co-op…"), through the room-code relay, instead of waiting (`link/test_connect.py`).
  - **Round 4 (2026-10-23):** Tucker: still both sides waiting, either one hosting. Checked on the PC: 0.9.0-dev installed, the relay works from its Python, LAN address right (10.0.0.177), no firewall rules either way (network: Public). Unknown whether the Thor ever got round 3's APK (not plugged in). Added, so the next try says where it stops:
    - the lobby names the step instead of "Still looking": *Finding my address* / *Waiting for your partner's game* (the relay never brought the partner) / *Found your partner: reaching them* (packets blocked);
    - the connector logs each step (addresses, router kind, partner's version, connected or why not): on the PC to `Documents\SOTN Co-op\session.log` (the game process's log had been thrown away), in F9 reports; on Android to logcat (`device.py log`).
    - Rebuilt both (installer 11:32, APK 11:32); `test_connect`, `android_room` (61 s) pass. Next: install on the Thor (`device.py install`) and the PC, one try each way, read both logs.
  - **Round 5 prep (2026-10-24):** the Thor's APK turned out to be from **Oct 22 20:05**, before round 3's CA fix, so in rounds 3–4 it never reached the relay. That explains both sides waiting. Now installed on both: the Thor (APK 23:46) and the PC (installer 23:46, silent). Also, from a review of the connect code (D96):
    - **same-network games find each other without the relay:** a fixed port (47811, any if taken) and a LAN broadcast HELO;
    - the lobby says "Can't reach the room-code server" at once, and the timeout names it;
    - relay retries after 5 s; relay reader threads stop after each attempt.
    - `test_connect` (26 checks, including no-relay same-house and a stranger's broadcast), 6 online harness scenarios, and `android_room` (55 s) pass. Next: Tucker tries both ways; then read `device.py log` and `session.log`.
  - **Open:** sound underruns on the emulators (7–38%, CPU-bound; check on the Thor). The Android release waits for the playtest (`release.py --android` is opt-in).
- **M11 castles (design approved 2026-10-25, D97–D99), branch `coop-m11-castles` (stacked on M9). Built; playtest build 0.11.0-dev.**
  - Castles replace playthroughs: Solo / Couch / Host each pick a castle (skipped when there's none); the joiner keeps a copy of the host's castle (updated in place until played, then a `(2)` entry); slot 1 is always this machine's player.
  - One shared level: a kill's XP is halved while a partner is linked and the gain goes to both games (`EV_EXP`); Richter and Maria level up from it too. Solo: 1× boss HP, full XP, status bar says "Solo".
  - Tests: `m11_shared_xp`, `m11_shared_xp_richter`, `m11_solo`, `m11_copy` (criteria 3 and 4), `m11_slot2_clone`; `launcher/test_castles.py` (14 checks: names, copies, criterion 5's rule, slots); uxdriver `solo`, `couch`, `online` (the joiner keeps the host's castle) pass.
  - Builds: `Emulators\SOTN-Coop-release\SOTN-Coop-setup-0.11.0-dev.exe`, `.env/android/SOTN-Coop-0.11.0-dev.apk`.
  - Old playthroughs aren't listed (not converted, D97): a 0.9 save is still on disk but doesn't show up.
  - Full harness 97/97, smoke 17/17, `test_connect` (with D100's fix: a room-code joiner took a roomless game answering its LAN broadcast), uxdriver solo/couch/online, `android_pc` (60 s) pass.
  - **Installed on both (2026-10-25 13:05):** PC (silent install) and the Thor (`device.py install`). Ready for Tucker's playtest.
  - **Test environment broke after the PC crash:** since WSL restarted, nothing from outside reaches the Android test emulators (their STUN fails too). `android_room` and `android_pc_join` fail the same way with yesterday's 0.9.0 code and APK, which passed then, so it isn't the code. The real Thor and PC don't use this path. Next: fix the emulator networking (likely a restart of the emulators/WSL), then re-run both.
  - **PR #6** (`coop-m11-castles` → main): M8, M9 and M11 together; merging it also merges #4 and #5.
  - **Release draft v0.11.0** (the v0.9.0 draft, retagged; 2026-10-25 15:14): `SOTN-Coop-setup.exe` (0.11.0, sha256 6469…4013) and `SOTN-Coop.apk` (e7c8…f949), notes `docs/releases/v0.11.0.md`. Includes the launcher's off-screen window fix (Tucker's saved position was x = −3267, on no monitor). Not yet installed on the PC or the Thor.
## Next (M12 v1.0, design `docs/design/M12-v1-release.md`, approved; D109–D116)
1. ~~**Licence**~~ (done 2026-10-27): `LICENSE` (AGPL-3.0), `NOTICE`, `licenses/`, in the installer and the APK; `release.py` refuses a release without them. GitHub shows the licence once this reaches `main`.
2. ~~**Android release key**~~ (done 2026-10-27, D112/D116): builds are release-signed, `release.py` refuses any other key, `device.py switch-key` moves the Thor over with its saves (`test_key_switch.py` passes). Tucker backed the key up; the Thor is on it (0.12.1-dev, saves kept).
3. ~~**Launch black screen**~~ (done 2026-10-27, D117): a picture 0.4 s after pressing Solo, the title at 18.2 s (was 23.1 s), measured in the real launcher (`uxdriver.py startup`, passes). The 2× disc read had switched itself off at frame 113, and the shipped OpenBIOS waited 5 s; it's now the FASTBOOT build the harness always used, with old savestates booting the old one.
4. **Coverage, widened:** every relic, spell, subweapon and Item Crash per character; the room report (static planner plus live checks); the 4 open scenes (Librarian, chapel, Center).
   - **Relics (2026-10-27):** `m12_relics_alucard` (his forms and their upgrades: 9 measured, each only with its relic), `m12_vlad_relics_*` (+10 STR/CON/INT/LCK, the Heart's curse immunity, all 3 characters), `m12_familiars_*` (all 5 cards, all 3 characters: the M8 leftover "faerie, demon, sword need a check" is done, they work). Richter's and Maria's gates were M8b's. **Gaps:** Power of Wolf and Skill of Wolf (the wolf's dash isn't reached in the test hall; listed in the report). Not yet: Jewel of Open, Merman Statue, Cube of Zoe, Spirit Orb, Faerie Scroll per character (stage code reads the relic; they need fixtures at a blue door, the ferryman, a candle).
   - **Subweapons and crashes (2026-10-27):** `m12_subweapons_*` (all 9 of the castle's subweapons, all 3 characters) and `m12_crashes_{richter,maria}` (every crash with Echo of Bat) pass. Alucard's spells were covered already (`m8b_spell_shortcuts`).
5. **Known bugs:** the M8 leftovers, the sound underruns, the M12 playtest notes. M12b leftovers: frame palettes, thrown items.
   - **New (found by `m12_subweapons_maria`): Maria throws nothing with the Cross, Bible, Stopwatch, Rebound Stone or Agunea.** Her game reads Alucard's subweapon id as an index into her own table (`src/maria/gen/subweapons.h`): 1 dagger → Cardinal, 2 axe → Cat, 3 holy water → Turtle, 4 cross → Dragon (which doesn't come out either: no hearts spent, so `MarDoSubweapon` returns early; why is open), 8 vibhuti → a Cardinal-crash fireball, and 5, 6, 7, 9 land on unused entries. A Maria player who picks one up has a dead button. Her crashes work with all nine. **Fix next:** a mapping from Alucard's nine to her four guardians and the doll (an agent-default, logged), and the Dragon's early return; then take them off the test's KNOWN list.
6. **The first-castle playthrough in segments** (`run.py --full`), then v1.0 (`run.py --full`, PCSX-Redux boot check, Tucker's playtest). The inverted castle is v1.1 (D114).
- Also in flight: debug starts outside every cutscene and boss: **Debug starts outside every cutscene and boss (Tucker, 2026-10-26): in progress.** Developer › Debug starts now has Bosses (12), **Scenes** and Places. Scene starts (`bossstarts.S`): each in the room before the scene, with the progress of the nearest boss before it in the story and the scene's flag cleared. Checked by a bot and played together (`m12_scene_*_from_start`): Maria in the Alchemy Lab (from the right: her scene steers Alucard left), Maria in the Royal Chapel, the Castle Keep. Maria in the Center: the start's scene begins, but its spot is wrong (Alucard drops to the floor below and the scene doesn't end, even in one game). Not yet: the Librarian (his scene's entity, in room 32's upper floor, doesn't start on coming into view, and his chair isn't in the room's layout: something else, maybe the Librarian himself, spawns it). To do: the inverted castle's bosses and scenes; the prologue and Death come from a new game. They stay debug starts (savestates in both games), not castles: a castle resumes at a save room.

## Next (older)
- **Tucker: playtest M8** with `Emulators\SOTN-Coop-release\SOTN-Coop-setup-0.8.0-dev.exe` (local, not uploaded):
  1. Settings › Game files: choose your Dracula X Chronicles .iso (`SOTN\discs\Castlevania - The Dracula X Chronicles (USA).iso`). Maria appears in the lobby.
  2. Couch: Continue your playthrough as Maria + Richter (Left/Right on each card). Their moves come with Alucard's relics; Start opens Alucard's equip menu (armor, a weapon in a hand: ○ swings it).
  3. Developer › Debug starts › Bosses: try a boss as Richter or Maria against Alucard. That's the power-curve check (decision below).
  4. Alucard: flick the right stick to cast spells you know (Settings › Controls picks which).
- Then the two decisions below, and merge the M8 PR.
- Tucker: test the draft release (couch, and online with a friend from another home), then publish it.
- Follow-ups worth having:
  - UPnP port mapping (rescues some symmetric-router cases)
  - accept `.chd` disc images
  - a small branded `.exe` so the firewall prompt doesn't say "Python"

## Budget
- 2026-10-26 (M12 session 1): one long session, the playtest 3 fixes and parts 1–2 of the coverage. Full suite 106 pass (before the boss and scene additions).
- Day 3 of the month (2026-10-20): M0 through M7b done. M7b took one long session, inside its 4–5 usage-window budget. Still far ahead of the 2026-11-18 target.
- Day 4 (2026-10-21): M8 designs approved; M8 implementation well along (two sessions so far, one cut off by a PC restart).

## Decisions needed (Tucker)
- None new. Android key backed up by Tucker (Google Drive, 2FA, 2026-10-27); the Thor moved to it the same day (`device.py switch-key`: 19 files, 2.1 GB, back and owned by the app; 0.12.1-dev installed).
- **Approved 2026-10-27:** the M12 v1.0 and M13–M19 designs (D109), v1.0 without the inverted castle (D114), the Mac build unsigned (D115).

### Older, still open
- None.

## Environment notes
- **The decomp's `mods/co-op/module` is a link to this repo's `module/`** (2026-10-21). `.env` here points into the old fork (`/home/tucker/sotn-decomp-coop/mods/co-op/.env`), whose `mods/co-op` folder was an Oct 19 copy: DRA was being built against its stale `coop_api.h`. The stale folder is kept as `module.stale-2026-10-19`.
- Standalone repository cloned and verified at `/home/tucker/sotn-coop` (remote: `https://github.com/tucker-bower/sotn-coop`).
