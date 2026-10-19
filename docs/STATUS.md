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
- M0 PR open, awaiting review.

## Next
- Write the new M1 design, `design/M1-link-presence.md`: the DRA-section loader, the mailbox, the host and emulator adapter, and the partner puppet. It will include a spike that runs two harness instances linked through a mailbox.

## Budget
- Month started 2026-10-18. Day 1: setup, environment, all of M0 (12%), and the re-plan.
- The new scope is larger than "P2 Lite". The month target (M1–M6) leaves only a 3% reserve, and M4 (shared rooms) is the main risk. Checkpoints are after M2 and after M4.

## Decisions needed (Tucker)
- **R1: which emulator we ship for.** This gets its own research session and conversation. Requirements and candidates are in `research.md` → "Product emulator". It isn't blocking until M6.
- **Before M7:** what mixed characters mean for shared progression, e.g. Richter with relics, equipment or levels, and Richter mode's world changes (D27).
- **Later (Maria):** obtain DXC **EU**, or let me write a `pspus` asset map (D15).
## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
