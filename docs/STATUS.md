# Status

_Last updated: 2026-10-22_

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
- **M9 Android (design `docs/design/M9-android.md`, D93), branch `coop-m9-android`.** Resumed 2026-10-22 after a cut-off session.
  - Criterion 1: `android/build.sh` builds arm64-v8a + x86_64 (39 MB, no game data). Fixed: pyjnius needed `wheel` without build isolation.
  - Criterion 2: `android_pair` **passes** (74 s); criterion 3: `android_pc` **passes** (60 s). Both now run with sound on.
  - Fixed on the way: on Android (plain pygame) the SDL audio callback deadlocked on the GIL as soon as an online session started (the earlier pass had sound off). Sound now goes through SDL_mixer, queued from the main thread.
  - **Open:** sound on the emulator underruns often (1138 of 1728 chunks); frames take about 16 ms (games 4–6 + draw 11), right at the 60 fps limit. Criterion 5 work: measure, then tune (bigger queue, cheaper draw).
  - Criterion 4 (setup on the device): **simpler install (D94).** The player picks the folder their disc is in (one tap), and the app copies just the disc (`.cue` + `.bin` files, or a `.zip`) with a progress bar. Checked live on an emulator through Android's real picker (`.env/out/android_setup/`, about 30 s to "Co-op disc ready"); `launcher/test_android_disc.py` passes. README has Android install steps. `release.py` attaches `SOTN-Coop.apk`.
  - Left for criterion 4: wrong files on Android should show the PC's errors (test them through the picker). The DXC `.iso` copy for Maria has no progress bar yet.
  - Criterion 5 (frame times): not started.
- **M8 + M8b (approved 2026-10-21, D85/D86), branch `coop-m8-maria-richter`.** Resumed 2026-10-21 after a PC restart cut the previous session off (nothing lost: everything but the launcher's game-files screen was pushed; that's committed now).
  - **Done, with passing tests:**
    - The world stays Alucard's whoever plays; each game's character is picked in the lobby, applied at the next load; our Richter (`COOPRIC.BIN`) and Maria (built from the player's DXC disc) in any pairing.
    - `char_select_session`: all 9 pairs from one save, re-picked at each load, disc unchanged. `mixed_party_shared_room` (+`_am`, `_rm`): puppets both ways, the guest's hits count. `mixed_party_progression` (R+M, M+R, R+A), `mixed_party_boss`, `mixed_party_cutscene`.
    - M8b for Richter and Maria: relic gates, L2/R2 shortcuts, growth (levels, STR/INT scaling, Fire of Bat), Mist Step; Life/Heart Max Up give +5 for everyone.
    - Alucard's spells on the right stick (`m8b_spell_shortcuts`, all 6 castable spells).
    - Launcher: Game files screen (`uxdriver.py characters`: wrong files refused in plain words, then Maria), lobby (Maria locked until her disc, Triangle/Y shortcuts per player), Settings › Controls. `test_characters.py` (Maria from the USA DXC disc).
    - **Patch hygiene fix:** COOPRIC.BIN had put Richter's retail art into the patch as literal bytes. Now copied from the player's RIC.BIN, and changed sectors' EDC/ECC are computed on the player's PC; `test_patcher.py` proves the patch holds no retail data or checksums.
    - Criterion 3: `mixed_soak_10min` against two Alucards (D92). §5 HUDs: the footage's cut was a 16:9 recording of an ultrawide window (D91); `uxdriver.py hud` 144/144 on Windows.
    - Off-hand weapons (D88): every class swings its own sprite and hits with the hand's attack; potions and food heal; a shield adds DEF. Equipping a weapon no longer turns Richter/Maria magenta (a palette clash, fixed).
  - **Built, being tested (uncommitted until it passes):** Richter's and Maria's code moved to expansion RAM so familiars fit (D89), familiars for them, poison water + Holy Symbol, Force of Echo / Gas Cloud for them.
  - **Left:** the power-curve tuning and the reachability audit (both decisions below); familiars, weapons and gates for Richter/Maria are done and tested (88/88 suite + M8 tests).

## Next
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
- Day 3 of the month (2026-10-20): M0 through M7b done. M7b took one long session, inside its 4–5 usage-window budget. Still far ahead of the 2026-11-18 target.
- Day 4 (2026-10-21): M8 designs approved; M8 implementation well along (two sessions so far, one cut off by a PC restart).

## Decisions needed (Tucker)
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
