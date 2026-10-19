# Status

_Last updated: 2026-10-18_

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
- PRs: M0 #1 and M1 #2, awaiting review.
- **M2 and M3 built, all criteria pass**, on branch `coop-m2-shared-progression`, stacked on M1 (PR #3). Results are in `design/M2-shared-progression.md` and `design/M3-teleport-respawn-save.md`.
  - **Shared progression, live:** relics, items (consumables too), max-ups, pooled gold, map, and flags. Pickups vanish and secret walls open in the partner's room.
  - **Teleport:** ✕ on the map, across stages. **Respawn:** at the partner. **Pause:** freezes a shared room. **Joint save + "Continue co-op":** both games, from the title.
  - 23 scenarios pass, plus the 30-minute and 10-minute chaos soaks and the PCSX-Redux check.
  - Two real bugs found and fixed on the way: a stale-`v0` freeze from the US `DebugUpdate` (M1 only worked by luck, D39), and a dropped frame from per-frame cost (D40).

## Next
- M4 design: shared rooms (the same enemies, fighting together). That's the main risk of the month.
- Then M5 (bosses and cutscenes together, including the boss-death rule) and M6 (the couch launcher: one window, two pads, on-screen co-op text D42, real save-room dialog playtest D43).

## Budget
- Day 2 of the month (2026-10-19): M0 through M3 done, against budgets that ran to 2026-10-30. Far ahead of plan.

## Decisions needed (Tucker)
- Review PRs #1–#3.
- Veto any agent-defaults you dislike: D42 (sounds, not text, for now), D45 (freeze, respawn and landing details).
- **Before M7:** what mixed characters mean for shared progression, e.g. Richter with relics, equipment or levels, and Richter mode's world changes (D27).
- **Later (Maria):** obtain DXC **EU**, or let me write a `pspus` asset map (D15).

## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
