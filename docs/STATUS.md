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
- M0 PR #1 open, awaiting review.
- **M1 built, all criteria pass: PR #2** (branch `coop-m1-link-presence`, stacked on M0 #1 and the re-plan). Results are in `design/M1-link-presence.md`.
  - The co-op module loads from boot on every new game (SwanStation and PCSX-Redux).
  - Two linked games see each other. The partner is a blue-tinted Alucard in the same room, and a cursor on the map.
  - The link adds ≤ 2 frames of latency, survives the partner vanishing, and never changes game state (10-minute two-game soak).
  - The loader changed from the approved option B to the design's fallback C (`COOP.BIN` on the disc, D32), because DRA has no spare bytes and retail files can't move.

## Next
- M2 and M3 designs **approved** (with D37/D38 changes), now building: `design/M2-shared-progression.md`, `design/M3-teleport-respawn-save.md`. The joint save moves from M2 to M3, which builds the "put a player in a room" path that resuming needs.

## Budget
- Month started 2026-10-18. Day 1: setup, environment, M0 (12%), the re-plan, and M1 (budget 15%, target 2026-10-23). Well ahead of plan.

## Decisions needed (Tucker)
- Review the M1 PR. Optional: watch the side-by-side GIF (`.env/out/puppet_same_room_only/clip.gif`).
- **Before M7:** what mixed characters mean for shared progression, e.g. Richter with relics, equipment or levels, and Richter mode's world changes (D27).
- **Later (Maria):** obtain DXC **EU**, or let me write a `pspus` asset map (D15).

## Environment notes
- Setup lives in `SETUP.md` and `scripts/bootstrap.sh`. The old cloud Go-mirror note is obsolete, because this machine has direct internet.
