# Decision log

Format: **ID: decision** (owner | agent-default) then the context, the options considered, and why.

**D1: Fork sotn-decomp; mod code lives in `mods/co-op/`** (owner, 2026-10-18)
We inherit the matching build and all decompiled code, and keep upstream diffs minimal.

**D2: Target the PS1 US build (SLUS-00067)** (owner, 2026-10-18)
It's the reference build the decomp is most complete for, and PS1 netplay is mature and lockstep-deterministic. PSP has more content but weaker netplay.

**D3 (superseded by D7): P2 is a second Alucard; Richter/Maria as P2 are stretch goals** (owner, 2026-10-18)

**D4: No networking code in the mod** (owner, 2026-10-18)
Local P2 on port 2. Online play comes from RetroArch netplay or streaming tools (Parsec, Steam Remote Play Together).

**D5 (revised by D7): Must run on popular PS1 emulators** (owner, 2026-10-18)
DuckStation, RetroArch cores, PCSX-Redux. Real PS1 hardware is no longer a target.

**D7: Richter and Maria as P2 are core goals; use 8MB dev-RAM mode from the start** (owner, 2026-10-18)
Playing as Alucard + Richter or Alucard + Maria is a much better experience than two Alucards. Because we build from source, `RIC.BIN` (and the Maria mod's overlay) can be relinked into the 8MB expansion area instead of their normal slot, so they coexist with Alucard. The community already treats 8MB as standard ("most modern emulators have the 8MB available"). Cost: players must enable the emulator's 8MB option, and each target emulator's support must be verified in M0. Maria additionally requires the user to own *Dracula X Chronicles (EU, PSP)*.

**D8: Ship as a patched PS1 disc image now; don't wait for the PC port** (owner, 2026-10-18)
The PC port has no release date and currently covers 23 of 41 stages. Our co-op code is shared C source, so it carries over to the port if and when that ships, and Android may follow quickly once it does.

**D9: Distribution builds from the user's own disc** (owner, 2026-10-18)
Follow the Maria mod precedent: a Docker image or script that takes the user's own disc image(s) and outputs the patched image. We publish no game data and no pre-patched images. An xdelta/PPF patch is a possible convenience option, subject to an owner decision.

**D6: Dev loop and budget** (owner, 2026-10-18)
The spec-driven loop is in `AGENTS.md`. Claude Pro subscription, ~1 month target. An upgrade will be considered if needed.

## D10: Install DuckStation + PCSX-Redux for cross-checks, using OpenBIOS
Approved by Tucker on 2026-10-18. Install both into `C:\Users\tucke\OneDrive\Desktop\Emulators`, pointed at OpenBIOS so the checks are fully automated. Tucker runs a real-BIOS smoke test at milestones.
