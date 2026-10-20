# Status

_Last updated: 2026-10-19_

## Done
- Forked sotn-decomp, `coop` branch. Project docs, research, scope change D7 (Richter as P2, 8MB).
- **Dev environment (D11–D13):** `bootstrap.sh` sets up a fresh Ubuntu 26.04/WSL2 machine, `doctor.py` verifies it in about 1 s, and `env.example.toml` says where everything lives. The us build matches retail 115/115 locally.
- **M0 built, PR pending** (branch `coop-m0-harness`). All 6 acceptance criteria pass, including Tucker's DuckStation check. Results are in `design/M0-harness.md`.
  - Harness: 25× real time, savestates in 22 s, room-walk scenario, 10-min lockstep with rollback (0 desyncs), headless PCSX-Redux check.
  - The co-op module runs from the 8MB area on SwanStation and PCSX-Redux.
- DuckStation is set up with a DualSense on port 1 (SDL bindings in its portable `settings.ini`).
- Emulators installed in `Emulators\DuckStation` and `Emulators\PCSX-Redux` (portable, OpenBIOS, 8MB) (D10).
- **Re-plan (2026-10-18):** the goal is now independent exploration, with one game per player and shared progression (D19–D31). `ROADMAP.md`, `README.md`, `AGENTS.md` and `research.md` are rewritten to match. The ghost-P2 M1 design is withdrawn (D29).

## In flight
- PR #4 lands M1–M3 on `coop`. PR #5 (`coop-m4-shared-rooms`) has M3b and M4, built and passing.
- **M4b and M5 built, all criteria pass** on `coop-m5-bosses`, PR #6 (stacked on #5).
  - **M4b:** every playtest-1 note is fixed or explained, plus three bugs found in my own playtests: a glitch when the burning Warg dies, a closed boss door the guest could walk through, and an empty relic message box.
  - **M5:** bosses pull the partner in, have 2× HP and switch targets. A dead player stays down until the boss falls, and cutscenes pull the partner in.
  - **Tools:** autonomous playtests (`harness/playtest.py`: bots, anomaly checks, contact sheets, "suspect" frames) and launcher F9 bookmarks with `harness/replay.py`.
- **Playtest 2 is installed** in `Emulators\SOTN-Coop`: 8 presets, including "Boss fight together" and "Cutscene together".

## Next
- Tucker's playtest 2 (`README-playtest.md`) and playtest 3 (`docs/playtest_notes/playtest_3_plan.md`).
- **M6 built and verified** (`coop-m6-playable`, PR stacked on #6): Windows installer, disc patcher, bundled OpenBIOS, event savestates with visible storage, F9 snapshots, and link protocol spec. Full multi-instance harness suite passes 57/57.
- **M7 design ready for review** (`docs/design/M7-repo-and-online.md`): standalone repository (`tucker-bower/sotn-coop`, self-hosted CI, pinned `sotn-decomp` dependency, D72/D73) + online PC co-op (zero-infra connect codes, direct-IP fallback, compressed MTU-chunked snapshots, online joint saves, version mismatch refusal, D74).
- **Roadmap updated with M8–M10 (D75):**
  - **M8:** Maria and Richter playable by either player from the start of a fresh playthrough (using local `disks/sotn.pspus.iso`), plus optional DXC alternate dialogue and voice acting.
  - **M9:** Android port of the launcher and session engine.
  - **M10:** AYN Thor curated dual-screen support (top screen = you, bottom screen = partner) + true expanded-FOV widescreen on the top screen.
- **Known gaps:**
  - moving platforms don't carry the guest (D52);
  - bosses other than the Doppleganger are untested (M5 risks);
  - big rooms share only while the players' screens overlap.

## Budget
- Day 2 of the month (2026-10-19): M0 through M6 done, far ahead of the 2026-11-18 target.

## Decisions needed (Tucker)
- **Approve M7 design** (`docs/design/M7-repo-and-online.md`). Once approved, I'll branch `coop-m7-repo-online`, build and test online PC co-op + standalone repo scripts, and migrate `mods/co-op/` into `tucker-bower/sotn-coop` with self-hosted CI.
- **Playtest 2:** does the game feel right?
  - aggro switching (a 50% re-roll every 3 s, D62);
  - 2× boss HP;
  - music from the left game;
  - the fades, flash and messages (D59);
  - the partner pull-in for cutscenes.
- **Before M7:** what mixed characters mean for shared progression, e.g. Richter with relics, equipment or levels, and Richter mode's world changes (D27).
- **Later (Maria):** obtain DXC **EU**, or let me write a `pspus` asset map (D15).

## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
