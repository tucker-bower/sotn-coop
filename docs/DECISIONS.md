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

**D10: Install DuckStation + PCSX-Redux for cross-checks, using OpenBIOS** (owner, 2026-10-18)
Install both into `C:\Users\tucke\OneDrive\Desktop\Emulators`, pointed at OpenBIOS so the checks are fully automated. Tucker runs a real-BIOS smoke test at milestones.

**D11: Environment layout: one manifest plus a doctor; masters live in the OneDrive Emulators folder** (owner, 2026-10-18)
`env.example.toml` (committed) and `env.toml` (local) list every path. `scripts/doctor.py` checks them, and `scripts/bootstrap.sh` creates them. Masters go in `OneDrive\Desktop\Emulators\SOTN\` (Tucker accepted the ~1.5GB of OneDrive sync). Working copies stay in WSL `disks/`, and churny data (savestates, builds) stays in `mods/co-op/.env/`.

**D12: MIPS cross toolchain from Ubuntu 24.04 via an apt pin** (agent-default, 2026-10-18)
Ubuntu 26.04 dropped `gcc-mipsel-linux-gnu`. Options considered: pinned noble packages; building gcc from source; clang as the preprocessor. Chose noble because it's the exact compiler upstream's Docker image uses, so matching-build risk is lowest. Pin priority is 50, so nothing else is pulled from noble.

**D13: Branch names are `coop-mx-<name>`** (agent-default, 2026-10-18)
Git can't create `coop/...` while a branch named `coop` exists.

**D14: Docker disc builder deferred to M5** (owner, 2026-10-18)
M0 builds the heartbeat disc with a plain script. M0 acceptance criterion 6 is changed to match.

**D15: Dracula X Chronicles (USA) is kept, but the Maria mod can't use it as-is** (agent finding, 2026-10-18)
Tucker owns ULUS-10277. Upstream's Maria assets are extracted from the EU release (ULES-00841) at fixed offsets. All 65 USA PSP overlays differ from the EU hashes, and `maria.bin` is 46KB smaller (the EU build has 5-language HUDs), so the offsets don't carry over. This is decided at M6 (Maria is post-month): obtain the EU copy (no maintenance), or write and maintain a `pspus` asset map (~0.5 day, and lets USA owners play Maria). The 14 "HD" PSX files on the USA disc do match upstream.
