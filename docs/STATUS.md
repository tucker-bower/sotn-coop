# Status

_Last updated: 2026-10-18_

## Done
- Forked sotn-decomp, `coop` branch.
- Matching `us` build verified: 115/115 game files match retail checksums.
- Findings: the player code (`src/dra`, `src/ric`) is fully decompiled, with no remaining asm. A native PC port exists in `src/pc`, including a replay system, which is a candidate harness backend.
- Project docs: README, AGENTS.md, ROADMAP, DECISIONS.
- Research: Discord, wiki and codebase → `research.md`. Key finding: about 85% of enemy targeting goes through shared helpers in `st_common.h`.
- Scope change (D7): Richter as P2 is now a core goal, using 8MB RAM mode. The roadmap has been re-planned.

- M0 spike: rebuilt a modded disc, booted it headless at 3.5× speed in 8MB mode on open-source BIOS, deterministic. See `design/M0-harness.md`.
- Finding: PCSX ReARMed and Beetle PSX don't support 8MB. SwanStation (RetroArch) is the co-op/netplay target.

## In flight
- M0 design doc, **awaiting approval**: `design/M0-harness.md`.

## Next
- M0 implementation after approval.

## Budget
- Month started 2026-10-18. Spent so far: setup only (~1 day).

## Decisions needed (Tucker)
- Approve the M0 design (incl. SwanStation as the primary core).
- ~~Installs~~: approved (D10).
- ~~Where agentic work happens~~: resolved. Claude Code on your PC (WSL2).
- 5-minute check on a Thor: does RetroArch's SwanStation core install and run?

## Environment notes
- The cloud build needs local Go module mirrors (the proxy blocks proxy.golang.org). Setup lives outside the repo, in `~/gomirrors/env.sh`. TODO: script this into the M0 bootstrap.
