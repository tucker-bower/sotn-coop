# SOTN Co-op

*What is a man? A miserable little pile of secrets — and now, a party of two.*

**Dracula's castle has risen again, and this time Alucard does not walk its halls alone.** *Castlevania: Symphony of the Night* becomes a two-player odyssey: each hunter roams the cursed corridors on their own screen, free to part ways in the moonlit Marble Gallery or descend together into the Catacombs. Every relic one claims, every door one breaks, every chamber one charts belongs to both — the moment it happens. When fate brings you to the same room, you face the same horde, blade beside blade. When a lord of the night stirs, your partner is summoned to your side and the beast rises with twice its strength, turning its fury from one of you to the other. Fall, and you are reborn beside your ally; fall before a boss, and you must trust your partner to carry the fight. Teleport across the castle in an instant, save at the coffins as one, and stand witness together as the tale unfolds. The night is long. Hunt it together.

## Quick start (Windows — couch or online co-op)
1. **You need:** your own copy of *Castlevania: Symphony of the Night* (USA, SLUS-00067) as a disc image (`.bin`/`.cue`; rip it from your disc), a Windows PC, and a controller (two controllers for couch co-op). No BIOS is needed: an open-source one comes with the launcher.
2. **Download** `SOTN-Coop-setup.exe` from the [releases page](https://github.com/tucker-bower/sotn-coop/releases) and run it.
3. **On first launch, pick your disc image.** The launcher checks it, makes the co-op version next to it (your original is never changed), and asks you to press a button on your controller.
4. **Play couch or online:**
   - **Couch co-op:** press **New game** (or **Continue**). Player 1 is the left screen, player 2 the right.
   - **Online co-op:** press **Play online**, then **Host online** (shares a 6-character room code and a 10-character endpoint code) or **Join online** (enter your partner's code or `ip:port`).
   - Press **F9** any time something looks wrong: it saves a bug report you can send us.

**Where your data goes:** `Documents\SOTN Co-op\` holds your saves, bug reports, and the savestates the launcher makes at big moments (a new area, a boss fight, quitting), so you can go back. It never deletes them. A whole playthrough takes roughly 200 MB. The launcher's home screen shows how much space they use, with buttons to open the folder or clean up a playthrough.

We never distribute game data: the launcher builds everything from your own disc.

## About the project
A two-player co-op mod for *Castlevania: Symphony of the Night* (PS1, US / SLUS-00067), built on [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp).

### Goal

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
- **Shared, live:** relics, castle flags, the explored map, items and consumables (each player gets a copy), max-HP/MP/Hearts upgrades, pooled gold, and boss kills.
- **Separate:** level, XP, hearts and subweapon, and the equipped loadout.
- Teleport to the partner from the map (✕). A player who dies respawns at the partner's location, except during a boss fight, where the survivor has to finish the boss alone first. Each player can pause on their own, unless both are in the same room.
- **Same room means the same enemies:** both players fight them, and enemies can target either player.
- **Bosses together:** the partner is teleported in automatically, and bosses get 2× HP. Cutscenes are seen together.
- **Joint save:** saving at a save room's coffin saves both games, and both resume from the title's Load menu.

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
- **Our own launcher around the SwanStation libretro core** (D36). PC couch co-op first, then online PC, then Android. PCSX-Redux is a cross-check.
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
