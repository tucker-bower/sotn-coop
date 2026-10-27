# Status

_Last updated: 2026-10-25 (M11 built)_

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
- **M12: the agent plays the game (coverage) + playtest 3 fixes** (2026-10-26, branch `coop-m12-coverage`). Design `docs/design/M12-coverage.md` awaits approval; notes and triage in `docs/playtest/2026-10-25-tucker-thor-pc.md`.
  - **Note 5 (graceful exit): fixed** (D101). `online_partner_leaves`, `test_connect` pass.
  - **Note 1 (cutscenes): fixed for the prologue, Death, and the scenes tested so far** (D102, D103). Found on the way: the partner kept Alucard's gear after Death's scene (it was a shared-room guest when Death took it), and a pulled-in partner could be sent out of the scene's room.
    - Passing: `m12_prologue_opening`, `m12_prologue_fight`, `m12_death_waits_for_partner`, and the catalogue (`session_m12.SCENES`/`ROOM_SCENES`): Succubus, Richter (Castle Keep), the Castle Keep scene, Maria in the Alchemy Lab. Maria in the Marble Gallery: `cutscene_pulls_partner_in` (M5).
    - Not yet triggering in the harness: the Librarian, Maria in the chapel and in the Center (that one starts in both games but doesn't end within 200 s: to investigate), and the inverted castle (Shaft, Dracula, the ending).
  - **Bosses (M12 part 2): 10 of 12 first-castle bosses pass** the two-game flow (`m12_boss_*`: pull-in, the fight, both fine after, the same flags). The fight bot can't win alone: the players are kept at full HP, the boss is worn down in the authority, and the last hit is scripted after 50 s.
    - **Succubus: a real co-op gap, open.** Both start at her door. A walks into her intro scene; B's copy starts 50 s later on its own (not held, not pulled: probably a different room), and ends 15 s before A's. After A's scene, B is pulled into the arena but has no Succubus of its own, and no shared room forms, so A fights alone. The end barrier is now up to 60 s (it was 5), which didn't change this. Next: log rooms and the hold state through her intro, then decide (hold or pull the partner into a nightmare-stage scene).
    - **Scylla:** the harness's walk bounces off her room's doorway (a single game does the same): a test problem.
    - Minotaur & Werewolf: passes. The pulled-in partner first plays the arena's intro scene, which (like the prologue's) steers the player only while a direction is held.
  - **Note 4 (Maria's guardians):**
    - **The wrong sprites: fixed** (D104). A hand weapon's graphics loaded over four of her guardians (owl, cardinal, dragon, doll). `m12_maria_guardians_keep_their_graphics` passes.
    - **No birds at all: reproduced, cause not found yet.** With a weapon (not a shield) in her hand, her cardinal costs hearts but never appears: `m12_maria_keeps_throwing` (77 frames with a bird per round without a weapon, 0 with one). Ruled out: her sprite banks and entity routing, and entity slots before the throw. Next: trace the cardinal's spawn (`MarCreateEntFactoryFromEntity`) with a weapon in hand.
  - **Note 3 (off-hands like Alucard's): decided by Tucker (D105).** Plan and spike: `docs/design/M12b-offhand-like-alucard.md`.
  - **Note 2 (partner's weapons drawn):** planned. Phase 1: subweapons, spells, familiar (graphics in every game), sent as sprite records with presence. Phase 2: hand weapons, drawn through the VRAM window (D106).
  - **VRAM (D106):** graphics are kept in the 8MB RAM and uploaded through a small VRAM window when drawn, as the puppet does. First: prove the window is free in every stage.
  - Tools: `fixtures_m12.py` (prologue and castle-start fixtures), the debug and boss starts built by the harness (`.env/fixtures/debug-starts`), `vram_survey.py` (VRAM read out of savestates).
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
## Next (M12, in order)
1. VRAM window survey (D106): "never changes during play" over every boss/debug start.
2. M12b spike: off-hand via the weapon's own overlay, 6 classes, Richter and Maria (design/M12b).
3. Succubus intro desync (STATUS above); Maria's missing birds with a weapon in hand (`m12_maria_keeps_throwing`).
4. Partner's weapons, phase 1.
5. Boss tests for R+M and A+R pairings; the open scenes (Librarian, chapel, Center, inverted castle); Scylla's walk.
6. M12 part 3: obstacles per character, the hand-item test (after M12b).

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
- **Approve M12** (`docs/design/M12-coverage.md`): cutscene, boss, obstacle and hand-item coverage, then a chained end-to-end playthrough as far as the budget goes. About 6–8 usage windows plus 3 for the fixes.
- **Android signing key (before the first public Android release, D95):** the APK is signed with this PC's debug key. An update signed with any other key won't install over it without an uninstall, and the uninstall deletes the player's saves. Options: (a) **a release keystore, backed up in your password manager (recommended)**; (b) keep the debug key and back up `~/.android/debug.keystore`.
- **M8b power curve (criterion 4): how to tune?** `harness/power_curve.py` fights each boss start as all three characters, but one generic bot isn't good enough to measure ±20%. It reaches 2 of the first 4 bosses, double bosses confuse its HP count, and its kill times swing widely. Options:
  - **(a) Tune by your playtest (recommended):** play Richter/Maria vs Alucard at a few boss starts (Developer › Debug starts › Bosses). The knobs are one table each (`richter/coop_ric.c`, `maria/coop_maria.c`: STR %, INT divisor, Fire/Echo %). Cost: your time, about an hour.
  - **(b) Per-boss bots** (approach and dodge patterns for each of the 12), then automatic tuning: about 2–3 usage windows.
- **M8b reachability audit (criterion 3): full route bot, or gate audit + playtest?** As designed, a bot walks each character room by room from every boss start, proving every relic, boss and save room is reachable with exactly the relics a player has. That's a pathfinding bot for the whole first castle, three times over: about 2–3 more usage windows, and brittle. Options:
  - **(a) Gate audit + your playtest (recommended):** a test per gate type from M8b §2 for Richter and Maria: high ledges (Gravity Boots / chained backflips / Maria's wings), low gaps (slide), mist grates (Mist Step, done), poison water (done), blue doors and the ferryman (they read the relic: character-neutral), and the worn-item gates (Spike Breaker, the rings, Holy Glasses), which work because they wear Alucard's gear now. Then a Richter + Maria couch playthrough by you finds what a gate list can't. The safety net (an Alucard player, D85) covers anything missed. About 0.5 window.
  - **(b) The full route bot**, as written: 2–3 windows.
- **Symmetric NAT (phone hotspots, some ISPs):** about 5–15% of pairs can't connect without a relay server (TURN) that we'd host and pay for. That would break D74's zero-infrastructure rule. Options:
  - keep it as is (the launcher explains the failure)
  - UPnP (free, partial)
  - a small TURN server (about $5/month)

## Environment notes
- **The decomp's `mods/co-op/module` is a link to this repo's `module/`** (2026-10-21). `.env` here points into the old fork (`/home/tucker/sotn-decomp-coop/mods/co-op/.env`), whose `mods/co-op` folder was an Oct 19 copy: DRA was being built against its stale `coop_api.h`. The stale folder is kept as `module.stale-2026-10-19`.
- Standalone repository cloned and verified at `/home/tucker/sotn-coop` (remote: `https://github.com/tucker-bower/sotn-coop`).
