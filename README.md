# SOTN Co-op

A two-player co-op mod for *Castlevania: Symphony of the Night* (PS1, US / SLUS-00067), built on [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp).

## Goal

Two players explore Dracula's castle **independently**, each on their own screen, with **shared progression**. A relic, item, unlocked area or explored room found by one player counts for both, live. Players meet up to fight the same enemies, take on bosses together, and watch cutscenes together. They can also teleport to each other at any time. The aim is co-op that's still fun after tens of hours and repeat playthroughs, including co-op speedruns. See `docs/DECISIONS.md` D19–D31.

## How it works
Each player runs their **own copy of the game** in an emulator. A **co-op link** connects them. Each game has an in-game module in the 8MB expansion RAM, and a host program per player that relays shared state between the two games.

```
 Player 1: emulator + patched SOTN + co-op module      Player 2: emulator + patched SOTN + co-op module
            |  mailbox (8MB RAM)                                    |
         host 1 -------------- local socket / network ----------- host 2
```

## Scope

**Month target: "explore together"** (Alucard + Alucard)
- Each player sees their partner on the map, and as a tinted puppet when the two are in the same room.
- **Shared, live:** relics, castle flags, the explored map, equipment (each player gets a copy), and max-HP/MP/Hearts upgrades.
- **Separate:** level, XP, gold, consumables, and the equipped loadout.
- Teleport to the partner from the pause menu. A player who dies respawns at the partner's location, except during a boss fight, where the survivor has to finish the boss alone first. Each player can pause on their own, unless both are in the same room.
- **Same room means the same enemies:** both players fight them, and enemies can target either player.
- **Bosses together:** the partner is teleported in automatically, and bosses get 2× HP. Cutscenes are seen together.
- **Joint save:** saving in either game saves both.

**Later**
- Each player picks Alucard, Richter or Maria. Maria requires *Dracula X Chronicles (EU, PSP)*.
- Full inverted castle coverage.
- Speedrun features.

## Non-goals
- Real PS1 hardware. The mod is emulator-only.
- Two players inside a single game instance (D20).
- Distributing any copyrighted game data.

## Constraints
- **8MB RAM mode required.** It holds the co-op module and the partner's sprite data.
- **The emulator we ship for isn't decided yet** (R1, D28). It must allow RAM access from outside, every frame, and run two instances. Development uses SwanStation through our harness, with PCSX-Redux as a cross-check.
- **Bring your own disc.** Users build the patched image from their own legally obtained copy, following the Maria mod's precedent. We never publish game data or pre-patched images.

## Testing approach
- A frame-stepped headless harness with savestates, scripted and bot inputs, and RAM assertions.
- **Multi-instance session tests:** two games plus the host, with scripted inputs on both and assertions across both games (for example, "P1 picks up a relic, and P2 has it within N frames").
- Human playtests on PC.

## Docs
- [`AGENTS.md`](AGENTS.md): how AI agents work on this project
- [`docs/ROADMAP.md`](docs/ROADMAP.md): milestones and acceptance criteria
- [`docs/STATUS.md`](docs/STATUS.md): current state, budget, and decisions needed
- [`docs/DECISIONS.md`](docs/DECISIONS.md): decision log
- [`docs/research.md`](docs/research.md): notes from the codebase, wiki and Discord

## Building
First follow the upstream build so that `make build` produces a matching `build/us`. Mod build steps will be added here.
