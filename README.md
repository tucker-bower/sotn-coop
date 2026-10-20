# SOTN Co-op

*What is a man? A miserable little pile of secrets — and now, a party of two.*

**Dracula's castle has risen again, and this time Alucard does not walk its halls alone.** *Castlevania: Symphony of the Night* becomes a two-player odyssey: each hunter roams the cursed corridors on their own screen, free to part ways in the moonlit Marble Gallery or descend together into the Catacombs. Every relic one claims, every door one breaks, every chamber one charts belongs to both — the moment it happens. When fate brings you to the same room, you face the same horde, blade beside blade. When a lord of the night stirs, your partner is summoned to your side and the beast rises with twice its strength, turning its fury from one of you to the other. Fall, and you are reborn beside your ally; fall before a boss, and you must trust your partner to carry the fight. Teleport across the castle in an instant, save at the coffins as one, and stand witness together as the tale unfolds. The night is long. Hunt it together.

## Play it (Windows 10 or 11)

### What you need
- **Your own copy of the game:** *Castlevania: Symphony of the Night*, the USA PlayStation version (SLUS-00067), as a disc image: a `.cue` file plus its `.bin` file(s). Rip your own disc with a disc-imaging tool (for example ImgBurn: *Create image file from disc*, then pick *BIN/CUE*). We can't give you the game.
- **A controller per player** (Xbox, PlayStation, Switch Pro and most USB controllers work). No controller? The keyboard works too.
- For online play: a friend with their own copy, and the same version of SOTN Co-op.

### 1. Download
Download **[SOTN-Coop-setup.exe](https://github.com/tucker-bower/sotn-coop/releases/latest/download/SOTN-Coop-setup.exe)** (about 25 MB).

Your browser and Windows will probably warn you. The installer isn't code-signed, because signing costs money every year; everything it installs is built from the source in this repository.
- **Edge:** "SOTN-Coop-setup.exe isn't commonly downloaded". Click **…**, then **Keep**, then **Show more**, then **Keep anyway**.
- **Chrome:** click **Keep**.
- **When you run it:** "Windows protected your PC". Click **More info**, then **Run anyway**.

### 2. Install
Click **Next**, **Next**, then **Finish**. It doesn't need administrator rights, and it starts SOTN Co-op at the end. Later, start it from the Start menu (or the desktop shortcut, if you ticked it).

### 3. First start: your disc
Click **Choose my disc image** and pick your game's `.cue` file. In a few seconds SOTN Co-op makes its co-op version of the disc next to yours (your files are never changed). It only asks once.

### 4. Play on one PC (couch co-op)
**Couch co-op**, then each player presses a button on their own controller (or Enter for the keyboard) and presses **Cross / A** when ready. Then **New game**, or **Continue** your last save. Player 1 is the left screen, player 2 the right one.

### 5. Play online
- **One of you hosts:** **Online co-op**, then **Host: new game**. You get a room code like `BAT-7K2Q`; it's on your clipboard. Send it to your friend.
- **The other joins:** **Online co-op**, then **Join your partner**. Type or paste the code.
- The first time, **Windows Firewall** may ask whether to let *Python* communicate. Click **Allow** (SOTN Co-op runs on Python).
- If it can't connect, the launcher says why. *Help › Online troubleshooting* has what to try.

### While you play
- **The window:** resize it, maximize it, or press **F11** for fullscreen. *View* in the menu bar lays the two games out side by side, stacked (for a vertical monitor), or with player 2 in its own window (a second monitor or TV). Pixels are sharp, and the picture is always the game's true 4:3 shape.
- **Esc** pauses. **F9** saves a bug report (a zip in `Documents\SOTN Co-op\reports`): please send it to us when something goes wrong.
- **Your saves** live in `Documents\SOTN Co-op\`, with savestates the launcher makes at big moments (a new area, a boss, quitting), so you can go back. It never deletes them. A whole playthrough takes about 200 MB.

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
- Each player picks Alucard, Richter or Maria (M8, being designed).
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
See [`SETUP.md`](SETUP.md): `scripts/bootstrap.sh` sets up a machine, `scripts/doctor.py` checks it, `scripts/build_disc.sh` builds the co-op disc, and `scripts/release.py` builds the installer and a draft GitHub release.
