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

## In flight
- M0 PR open, awaiting review.

## Next
- M1 design doc (Ghost P2). It starts with **how co-op code gets loaded**: the familiar slot only loads with a familiar active, so M1 needs a DRA hook (feasible: only 2 hardcoded DRA addresses outside DRA).

## Budget
- Month started 2026-10-18. Day 1: setup, environment and all of M0 (M0 budget 12%, target 2026-10-22). On or ahead of plan.

## Decisions needed (Tucker)
- (none blocking right now)
- Later (M6, Maria): obtain DXC **EU**, or let me write a `pspus` asset map (D15).
- Before M5: the 5-minute Thor check that SwanStation installs and runs.

## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
