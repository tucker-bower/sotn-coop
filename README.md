# SOTN Co-op

A two-player co-op mod for *Castlevania: Symphony of the Night* (PS1, US / SLUS-00067), built on top of [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp).

## Goal

Two people play a full run of the game together. Each player controls their own character, on the same screen, in the same castle.

The mod is a patched disc image that runs on the popular PS1 emulators: DuckStation, RetroArch (Beetle PSX, SwanStation, PCSX ReARMed), PCSX-Redux and ePSXe. It's also designed to run on real hardware. It plays over local wifi or the internet using standard tools:

- **RetroArch netplay** (LAN, or internet via relay servers). This works on PC and Android handhelds such as the AYN Thor.
- **Streaming tools** such as Parsec, Steam Remote Play Together or Moonlight. These work with any emulator, because P2 is just a second local controller.

The mod itself only needs local two-player support (controller port 2). It contains no networking code.

## Scope

**Milestone 1: "P2 Lite"**
- A second Alucard, driven by pad 2.
- P2 shares P1's stats, equipment and inventory.
- P2 warps to P1 on room transitions, cutscenes and boss intros.
- Both players can attack and take damage, and enemies can target either player.

**Later / stretch**
- Independent P2 stats, equipment and inventory.
- A shared-camera tether instead of warping.
- Richter or Maria as P2.
- Inverted castle coverage.

## Non-goals
- Online play beyond what RetroArch netplay already provides.
- Shipping any copyrighted game data. You must supply your own disc image.

## Constraints
- **Deterministic.** The same inputs must produce the same frames, or netplay desyncs.
- **PS1 memory limits.** The game has 2MB of RAM and tight overlay budgets.
- **Ships as a patched disc image** (`.cue`/`.bin`), with an xdelta/PPF patch for distribution.
- **No emulator-specific tricks.** The mod stays within stock PS1 hardware: no 8MB dev-RAM mode and no emulator hooks, so it behaves the same everywhere.

## Docs
- [`AGENTS.md`](AGENTS.md): how AI agents work on this project
- [`docs/ROADMAP.md`](docs/ROADMAP.md): milestones and acceptance criteria
- [`docs/STATUS.md`](docs/STATUS.md): current state, budget and decisions needed
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decision log
- [`docs/research.md`](docs/research.md): notes from the codebase, wiki and Discord

## Testing approach
- A frame-stepped headless harness: savestates, scripted and bot inputs, and RAM assertions.
- Lockstep desync checks that run two instances and compare RAM every frame.
- Human playtests at milestones, for game feel.

## Building
Follow the upstream build first, so that `make build` produces a matching `build/us`. Mod build steps will be added here.
