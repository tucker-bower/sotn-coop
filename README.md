# SOTN Co-op

*What is a man? A co-operative little pile of friendship.*

Online and couch co-op mod for *Castlevania: Symphony of the Night*. Explore the castle independently, fight bosses together, share progression. See your partner's location on the map and teleport to them at will. 

This co-op mod utilizes a custom launcher running *two instances* of PS1 SOTN emulation, syncing with each other over a python api. 

## Getting started
You need your own copy of *Castlevania: Symphony of the Night*, the USA PlayStation version (SLUS-00067), as a disc image (`.cue` + `.bin`). We can't give you the game, and we never distribute game data. Maria also needs *Castlevania: The Dracula X Chronicles* (USA, PSP) as an `.iso`, which is optional.

1. Download from the [latest release](https://github.com/tucker-bower/sotn-coop/releases/latest):
   - **Windows 10 or 11:** [SOTN-Coop-setup.exe](https://github.com/tucker-bower/sotn-coop/releases/latest/download/SOTN-Coop-setup.exe)
   - **Android 7 or newer (preview, online only, needs a controller):** [SOTN-Coop.apk](https://github.com/tucker-bower/sotn-coop/releases/latest/download/SOTN-Coop.apk)
2. Run it. The installer and launcher guide you through the rest.

The downloads aren't code-signed, so your browser, Windows or Android may warn you. Choose **Keep**, **Run anyway** or **Install anyway**. Everything is built from the source in this repository.

## Features
**Play your way**
- **Online co-op:** share a room code and play, with no account or server setup. PCs and phones can play each other.
- **Couch co-op:** two controllers on one PC, side by side, stacked, or in two windows.
- **Solo:** every castle can also be played alone, with normal boss HP and full XP.

**A shared castle**
- **Explore independently,** each on your own screen, and see your partner on the map.
- **Shared progress, live:** relics, unlocked areas, the explored map, beaten bosses and max HP/MP/heart upgrades count for both of you. Gold is pooled, and each of you gets a copy of every item found.
- **Shared level:** kills give both of you half the XP.
- **Shared saves:** saving in a coffin saves both games. Anyone can pick up a castle, and whoever joins keeps a copy to play solo or host later.
- **Save-state safety net:** the launcher keeps savestates at big moments, and never deletes them.

**Fight together**
- **Your partner is a real second player** in your game, with their own character, attacks, familiar and sounds.
- **Same room, same enemies:** fight them together, and they can target either of you.
- **Bosses and cutscenes together:** bosses bring your partner in, have 2× HP and switch targets. Cutscenes play for both of you.
- **Revives:** if you die, you come back at your partner's side once any boss fight is over. If you both die, you reload your last save.
- **Faerie revive:** Alucard's faerie and a Life Apple revive a fallen partner on the spot.

**Three characters**
- **Alucard, Richter and Maria,** in any pairing, chosen each session.
- **The whole castle as any character:** Richter and Maria learn their moves from Alucard's relics, level up, wear his armor, and use his weapons in their off hand.
- **Rebalanced** to stay close to Alucard's power, with extra jumps to reach everywhere he can.
- **One-button shortcuts,** optional for each player: high jump and blade dash for Richter and Maria, spells on the right stick for Alucard.

**Extra modes**
- **Boss rush:** all 22 bosses back to back, timed with splits and a best time, solo, on the couch or online.
- **PvP:** optional, and off by default.
- **Test castles:** start right outside any boss or scene.

## Tips
- **Teleport to your partner:** press Select for the map, then Cross. Your partner's cursor is blue.
- **Report a bug:** press **F9** the moment something goes wrong. It saves a zip in `Documents\SOTN Co-op\reports`. Please send it to us privately, as it contains game data.
- **Pause:** Esc. You pause separately, unless you're in the same room.
- **Shortcuts:** press Triangle / Y on your lobby card to turn them on.
- **Relics for Richter and Maria:** Leap Stone gives the second jump, Gravity Boots the high jump, Soul of Wolf the slide, Echo of Bat item crashes, and Form of Mist lets you walk through grates.
- **Maria:** choose your *Dracula X Chronicles* `.iso` under Settings › Game files.
- **The window:** F11 for fullscreen, and the View menu changes the layout. On the couch, F1 picks which game plays the music.
- **Online:** you both need the same version. If you can't connect, the lobby says why, and Help › Online troubleshooting has what to try.

## Docs
- [`docs/TECHNICAL_SUMMARY.md`](docs/TECHNICAL_SUMMARY.md): how it all works
- [`docs/ROADMAP.md`](docs/ROADMAP.md): what's next, and known issues
- [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md): build it yourself
- [`AGENTS.md`](AGENTS.md): how we develop it, with AI agents
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md): why we chose what we chose
- [`docs/research.md`](docs/research.md): what we've learned about the game and tools

## Credits and thanks
SOTN Co-op stands on other people's work. Thank you to all of them.

**Foundations: what the mod is built from**
- **[sotn-decomp](https://github.com/Xeeynamo/sotn-decomp)**, by Xeeynamo and its contributors. The matching decompilation of *Symphony of the Night* is what made a mod of this depth possible: named symbols, the game's own headers, its build toolchain and asset tools. The co-op module is compiled against it. The decomp community's Discord answered our first questions: 8 MB RAM mode, hooking DRA, how enemies see the player.
- **The Maria mod** (`mariapsp-forpsx`, in sotn-decomp's `mods/`), by its authors in the decomp community. It ports *Dracula X Chronicles*' Maria to the PS1 and is our Maria's base. It also set the precedent we follow: build from the player's own discs, and never distribute game data.
- **[SwanStation](https://github.com/libretro/swanstation)**, the libretro PlayStation core, and **[DuckStation](https://github.com/stenzek/duckstation)** by Stenzek, which it's forked from. Every game in SOTN Co-op runs in it: on the couch two cores at once, online one per player. Its 8 MB RAM support and accuracy are what the module lives in.
- **[PCSX-Redux](https://github.com/grumpycoders/pcsx-redux)** by the Grumpycoders. Its **OpenBIOS** ships in every release, so nobody needs a BIOS dump. The emulator itself is our cross-check, and its Lua scripting lets us run the module headless.
- **[libretro.py](https://github.com/JesseTG/libretro.py)** by Jesse Talavera. It drives the core from Python, and the test harness and the launcher are built on it.
- **[libretro](https://www.libretro.com/)**: the core API that lets one frontend host the emulator.
- **[splat](https://github.com/ethteck/splat)** by Ethan Roseman, the decomp's binary splitter, which also splits Maria's PSP overlay.
- **[sotn-player-mmx](https://github.com/Xeeynamo/sotn-player-mmx)** by Xeeynamo: a custom player character, and our reference for injecting palettes (the partner's tint).

**Inspiration: what shaped the design**
- **[sotn-online-coop](https://github.com/jweyden/sotn-online-coop)** by jweyden: an online co-op mod with the same goal, built on a recompilation of the game. Reading it gave us the partner as a real second player in your game (our M13), PvP decided by the victim's game (M15), fairy revives and per-character respawn effects, more players (M17), and the Saturn characters (M16, on their AGPL ports). It also confirmed our shared-room design: the first player in runs the room.
- **[Slippi](https://slippi.gg)** (Melee online), by Fizzi and the Slippi team. Its launcher set our bar: point it at your disc once, then one button, short codes to play online. Its netplay showed that direct connections, plus clear advice when they fail, are enough, without running servers (D123).
- **Ocarina of Time Online**, by the [Hylian Modding](https://github.com/hylian-modding) team on ModLoader64, and the **[Ocarina of Time decompilation](https://github.com/zeldaret/oot)** by Zelda Reverse Engineering Team: an example of what we wanted: each player in their own copy of the game, with flags, items and progression kept in sync, and a decompilation as the foundation for mods like it.
- **[sm64coopdx](https://github.com/coop-deluxe/sm64coopdx)** and its ancestor **sm64ex-coop** (djoslin0 and contributors): co-op built on a decompilation, and proof that it can feel like the game was made for it. The decomp community compared our idea to it before we started; its netcode practice (compressed snapshots under the MTU) is in our link.
- **Natan Vishera's** *Modo Multiplayer Co-op com Familiars* for PS1 SOTN, and Pigsy's Genesis port with a two-player mode: earlier SOTN multiplayer that showed people want this.
- **TalicZealot's [SotnRandoTools](https://github.com/TalicZealot/SotnRandoTools)** and the SOTN randomizer community: tooling around live SOTN memory.
- **[BBLauncher](https://github.com/rainmakerv3/BB_Launcher)** by rainmakerv3: a launcher that owns its emulator, backs up saves and explains errors plainly.
- **[ntfy.sh](https://ntfy.sh)** by Philipp Heckel: the free relay where room codes meet, with no server of ours.
- **Python**, **[pygame-ce](https://github.com/pygame-community/pygame-ce)**, **SDL**, **Pillow** and **[python-for-android](https://github.com/kivy/python-for-android)**: the launcher on Windows and Android.

*Castlevania* and *Symphony of the Night* are trademarks of Konami. This project is not affiliated with Konami. Buy the game.

## Licence
SOTN Co-op is free software under the [GNU Affero General Public License v3](LICENSE), like [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp), which it is built on. What the releases bundle (SwanStation, OpenBIOS, Python and others) and under which licences: [NOTICE](NOTICE), with the full texts in [licenses/](licenses). No game data is in this repository or in any release.
