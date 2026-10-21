# Status

_Last updated: 2026-10-20_

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
- **Draft release v0.7.1** (rebuilt with the fixes and boss starts) for Tucker to test and publish, after merging `coop-fix-dualsense`.

## Next
- Tucker: test the draft release (couch, and online with a friend from another home), then publish it.
- **M8 design revised** (`docs/design/M8-maria-and-richter.md`, D84) with Tucker's answers, plus a new **M8b** (`docs/design/M8b-character-balance.md`): what each character can do (from the decomp), what the castle requires, a relic → Richter/Maria mapping, Mist Step, power scaling and a balance method using the boss debug starts. Waiting on Tucker's review of M8b §7.
- Follow-ups worth having:
  - UPnP port mapping (rescues some symmetric-router cases)
  - accept `.chd` disc images
  - a small branded `.exe` so the firewall prompt doesn't say "Python"

## Budget
- Day 3 of the month (2026-10-20): M0 through M7b done. M7b took one long session, inside its 4–5 usage-window budget. Still far ahead of the 2026-11-18 target.

## Decisions needed (Tucker)
- **Publish v0.7.1:** Tucker is testing couch and online on 2026-10-20. PR #1 is merged and the draft now targets `main`. Publishing is one click on GitHub, or `gh release edit v0.7.1 --draft=false -R tucker-bower/sotn-coop`.
- **Symmetric NAT (phone hotspots, some ISPs):** about 5–15% of pairs can't connect without a relay server (TURN) that we'd host and pay for. That would break D74's zero-infrastructure rule. Options:
  - keep it as is (the launcher explains the failure)
  - UPnP (free, partial)
  - a small TURN server (about $5/month)
- **M8 final approval** (D85: everything else is answered). Three open points, each with a recommendation:
  - **Where F9 reports go** (M8 §6): a free Cloudflare relay into a private repo, `tucker-bower/sotn-coop-reports` (recommended). It needs Tucker's free Cloudflare account and one GitHub token (about 15 min).
  - **Off-hand weapons** (M8b §4.1): option A, each weapon class on one of Richter's or Maria's own poses, showing the weapon's own sprite (recommended).
  - **Alucard's spell shortcuts** on the right stick (M8b §3.2): on the backlog (recommended), or in M8.

## Environment notes
- Standalone repository cloned and verified at `/home/tucker/sotn-coop` (remote: `https://github.com/tucker-bower/sotn-coop`).
