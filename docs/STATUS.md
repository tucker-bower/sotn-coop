# Status

_Last updated: 2026-10-18_

## Done
- Forked sotn-decomp, `coop` branch.
- Matching `us` build verified: 115/115 game files match retail checksums.
- Findings: the player code (`src/dra`, `src/ric`) is fully decompiled, with no remaining asm. A native PC port exists in `src/pc`, including a replay system, which is a candidate harness backend.
- Project docs: README, AGENTS.md, ROADMAP, DECISIONS.
- Research: Discord, wiki and PR read-through → `research.md`.

## In flight
- M0 design proposal (harness backend: native PC port vs. headless emulator).

## Next
- M0 implementation after approval.

## Budget
- Month started 2026-10-18. Spent so far: setup only (~1 day).

## Decisions needed (Tucker)
- Link GitHub to Claude so commits can be pushed to the fork.

## Environment notes
- The cloud build needs local Go module mirrors (the proxy blocks proxy.golang.org). Setup lives outside the repo, in `~/gomirrors/env.sh`. TODO: script this into the M0 bootstrap.
