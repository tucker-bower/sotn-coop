# Status

_Last updated: 2026-10-18_

## Done
- Forked sotn-decomp, `coop` branch.
- Matching `us` build verified: 115/115 game files match retail checksums.
- Findings: the player code (`src/dra`, `src/ric`) is fully decompiled, with no remaining asm. A native PC port exists in `src/pc`, including a replay system, which is a candidate harness backend.
- Project docs: README, AGENTS.md, ROADMAP, DECISIONS.
- Research: Discord, wiki and codebase → `research.md`. Key finding: about 85% of enemy targeting goes through shared helpers in `st_common.h`.
- Scope change (D7): Richter as P2 is now a core goal, using 8MB RAM mode. The roadmap has been re-planned.

## In flight
- M0 design proposal (harness backend: native PC port vs. headless emulator).

## Next
- M0 implementation after approval.

## Budget
- Month started 2026-10-18. Spent so far: setup only (~1 day).

## Decisions needed (Tucker)
- Confirm D8 (ship as a patched disc now, not waiting for the PC port) and D9 (distribution builds from the user's own disc).
- Where agentic work happens: this cloud session or Claude Code on your PC (WSL2).

## Environment notes
- The cloud build needs local Go module mirrors (the proxy blocks proxy.golang.org). Setup lives outside the repo, in `~/gomirrors/env.sh`. TODO: script this into the M0 bootstrap.
