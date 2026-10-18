# Decision log

Format: **ID: decision** (owner | agent-default) then the context, the options considered, and why.

**D1: Fork sotn-decomp; mod code lives in `mods/co-op/`** (owner, 2026-10-18)
We inherit the matching build and all decompiled code, and keep upstream diffs minimal.

**D2: Target the PS1 US build (SLUS-00067)** (owner, 2026-10-18)
It's the reference build the decomp is most complete for, and PS1 netplay is mature and lockstep-deterministic. PSP has more content but weaker netplay.

**D3: P2 is a second Alucard; Richter/Maria as P2 are stretch goals** (owner, 2026-10-18)
Both alternate characters' player code loads into the same memory slot as Alucard's, so running them alongside Alucard is a relocation problem. It's deferred.

**D4: No networking code in the mod** (owner, 2026-10-18)
Local P2 on port 2. Online play comes from RetroArch netplay or streaming tools (Parsec, Steam Remote Play Together).

**D5: Must run on popular stock emulators and real hardware** (owner, 2026-10-18)
DuckStation, RetroArch cores, PCSX-Redux, ePSXe. No 8MB dev-RAM and no emulator hooks.

**D6: Dev loop and budget** (owner, 2026-10-18)
The spec-driven loop is in `AGENTS.md`. Claude Pro subscription, ~1 month target. An upgrade will be considered if needed.
