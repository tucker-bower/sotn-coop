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
- PRs #1–#3 merged. They were stacked, so `coop` only got M0. **PR #4** lands M1–M3 on `coop` (no new changes).
- **Designs awaiting approval:**
  - `design/M3b-save-rooms.md`: the game's own save rooms end to end. The partner's game writes its own memory-card save, so both players resume from the title's Load menu.
  - `design/M4-shared-rooms.md`: shared rooms, via room authority plus mirroring. Spikes first, then a checkpoint with Tucker.

## Next
- Build M3b, then M4's spikes (S1–S4) and the checkpoint.

## Budget
- Day 2 of the month (2026-10-19): M0 through M3 done, against budgets that ran to 2026-10-30. Far ahead of plan.

## Decisions needed (Tucker)
- Merge PR #4.
- Approve M3b and M4 (or redirect).
- **Before M7:** what mixed characters mean for shared progression, e.g. Richter with relics, equipment or levels, and Richter mode's world changes (D27).
- **Later (Maria):** obtain DXC **EU**, or let me write a `pspus` asset map (D15).

## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
