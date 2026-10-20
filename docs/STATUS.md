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
- Tucker's playtest 2 (`README-playtest.md`), plus more autonomous playtest tours meanwhile.
- **M6:** a playable build, played from the start through the first few bosses.
- **Known gaps:**
  - moving platforms don't carry the guest (D52);
  - bosses other than the Doppleganger are untested (M5 risks);
  - big rooms share only while the players' screens overlap.

## Budget
- Day 2 of the month (2026-10-19): M0 through M3 done, against budgets that ran to 2026-10-30. Far ahead of plan.

## Decisions needed (Tucker)
- Merge PR #4, then #5, then #6 (M4b+M5). Approve or change the M6 design (`design/M6-playable-build.md`): the patch-file distribution is the D9 decision.
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
