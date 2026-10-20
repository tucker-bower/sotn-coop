# Status

_Last updated: 2026-10-19_

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

## In flight
- PRs for M7 on `tucker-bower/sotn-coop` and `tucker-bower/sotn-decomp-coop`.

## Next
- **M8 design (`docs/design/M8-maria-and-richter.md`):** inspect `disks/sotn.pspus.iso` (`ULUS-10277`) to map Maria, Richter, and alternate DXC dialogue/voice assets, and design character selection + cross-character shared progression rules (D27).
- **Playtest:** `SOTN-Coop-setup-0.7.0.exe` (couch + online play).

## Budget
- Day 2 of the month (2026-10-19): M0 through M7 done, far ahead of the 2026-11-18 target.

## Decisions needed (Tucker)
- **Before M8 implementation:** what mixed characters mean for shared progression (D27) — e.g. when Richter or Maria picks up an Alucard relic/equipment item or vice versa, and how Richter/Maria world differences (like Alucard-only gates or dialogue triggers) behave in a mixed party.

## Environment notes
- Standalone repository cloned and verified at `/home/tucker/sotn-coop` (remote: `https://github.com/tucker-bower/sotn-coop`).
