# SOTN Co-op

A two-player co-op mod for *Castlevania: Symphony of the Night* (PS1, US / SLUS-00067), built on [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp).

## Goal

Two people play through the castle together on the same screen: **Alucard + Richter**, and later **Alucard + Maria**.

The mod is a patched disc image for the popular PS1 emulators: DuckStation, RetroArch (Beetle PSX / SwanStation), and PCSX-Redux. It's playable over local wifi or the internet with standard tools:

- **RetroArch netplay** (LAN, or internet via relay). Works on PC and on Android handhelds such as the AYN Thor.
- **Streaming tools** (Parsec, Steam Remote Play Together, Moonlight), which work with any emulator because P2 is just a second local controller.

The mod itself only adds local two-player support (controller port 2). It contains no networking code.

## Scope

**Milestone target: "P2 Lite"**
- P2 on pad 2, playing as Alucard first (stepping stone), then as Richter.
- Shared progression and inventory. P2 warps to P1 on room transitions, cutscenes and boss intros.
- Both players fight, and enemies target either player.

**Later**
- Maria as P2. This requires the user to also own *Dracula X Chronicles (EU, PSP)*.
- Independent P2 stats, equipment and inventory.
- A shared-camera tether instead of warping.
- Two-player boss balancing.
- Inverted castle coverage.

## Non-goals
- Real PS1 hardware.
- Networking code. Netplay and streaming tools handle that.
- Distributing any copyrighted game data.

## Constraints
- **8MB RAM mode required.** Enable the emulator's "8MB RAM / dev console" option. Richter's code is relinked into the expansion RAM so he can coexist with Alucard.
- **Deterministic.** The same inputs must produce the same frames, or netplay desyncs.
- **Bring your own disc.** Users build the patched image from their own legally obtained copy (following the Maria mod's precedent). We never publish game data or pre-patched images.

## Testing approach
- A frame-stepped headless harness with savestates, scripted and bot inputs, and RAM assertions.
- Lockstep desync checks that run two instances and compare RAM every frame.
- Human playtests on PC emulators, then on the Thors.

## Docs
- [`AGENTS.md`](AGENTS.md): how AI agents work on this project
- [`docs/ROADMAP.md`](docs/ROADMAP.md): milestones and acceptance criteria
- [`docs/STATUS.md`](docs/STATUS.md): current state, budget, and decisions needed
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decision log
- [`docs/research.md`](docs/research.md): notes from the codebase, wiki and Discord

## Building
First follow the upstream build so that `make build` produces a matching `build/us`. Mod build steps will be added here.
