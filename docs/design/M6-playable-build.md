# M6 design: A playable build

**Status:** approved 2026-10-19 (v2, with Tucker's changes: no timed autosaves, storage made visible; the patch-file patcher approved; nothing moves to M7).
**Context:**
- D8: ship as a patched disc image.
- D9: build it from the user's own disc.
- D36: our own launcher; PC couch co-op first, then online PC, then Android.

## Goal
Someone with their own SOTN (USA) disc image, a Windows PC and two controllers gets from download to playing co-op in a few minutes, with no toolchain, no WSL, no BIOS hunt, and no settings to understand.

The pieces are built so that online play (M7) and an Android version later reuse them rather than replace them:
- the disc patcher;
- the link protocol;
- the savestate and debug archive;
- the session engine.

## What the best launchers do, and what we take from them
**Slippi** (Melee online):
- **What it does:** you point it at your ISO once; it checks the ISO and tells you plainly whether it's the right one. From then on it's one big Play button. Its custom Dolphin updates itself silently. Online is an account plus a short connect code. Every game is saved as a replay you can browse.
- **What we take:** a verified disc chosen once; one button; silent updates; short codes for online; nothing lost.

**BBLauncher** (Bloodborne on shadPS4; [github.com/rainmakerv3/BB_Launcher](https://github.com/rainmakerv3/BB_Launcher)):
- **What it does:** one app wraps the emulator. It downloads and updates its builds, manages mods with error checking, makes automatic save backups at intervals with a restore screen, and puts the emulator's settings and control remapping in its own UI.
- **What we take:**
  - the launcher owns the emulator (the player never configures SwanStation);
  - automatic backups with a restore screen;
  - control remapping in the launcher;
  - errors explained in plain words.

**Principles:**
1. **First run is a short wizard, then never again:** pick the disc, it's checked, done.
2. **The home screen has one big button:** "Continue" if there's a save, otherwise "New game". Everything else is one level down.
3. **Controller-first:** the menus work with a pad, as on a console, since the player is on a couch. Mouse and keyboard work too.
4. **Errors say what to do:** "This disc is the Japanese version: co-op needs the USA disc (SLUS-00067)", not a hash mismatch.
5. **Nothing the player made is ever deleted by the launcher:** saves, savestates and bug reports.

## Architecture: built for PC now, online and Android next
```
             ┌──────────── launcher UI (PC: in-window, controller-first; Android: native app) ───────────┐
             │  wizard · home · settings · savestates · bug report (F9)                                  │
             └───────────────────────────────────┬──────────────────────────────────────────────────────┘
                                                 │ one small API
 ┌───────────────────────────────── session engine (headless) ─────────────────────────────────┐
 │ emulator adapter (SwanStation libretro) · co-op host (link protocol) · savestate archive     │
 │ · joint saves · debug snapshot · local or network transport                                  │
 └──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Session engine:** today's harness and host code, cleaned up behind a small API: start a game, step, pads, frames and audio out, snapshot. It's headless, so the harness tests the exact code players run.
- **Link protocol, written down:** `docs/link-protocol.md` covers the mailbox layout, the events, snapshots, and the presence and handshake (link version, patch version, disc hash). Then an Android host in Kotlin or C++ can be written against the spec and tested by the harness over UDP, against our host.
- **Couch (M6):** one engine, two emulator processes, local transport.
- **Online (M7):** each player runs one game. The transport becomes the network. A small rendezvous service gives short connect codes, Slippi-style, with a direct IP fallback. The handshake refuses mismatched versions with a clear message.
- **Android (later):**
  - **The game:** one game per device (online), the SwanStation core for Android, and the host reimplemented from the protocol spec, or embedded. That's decided when we get there; the spec keeps either option open.
  - **The disc:** patched on a PC, as Tucker allows, then copied to the phone.
  - **Possibly:** a browser-based patcher, which would work on any PC with nothing installed, and maybe on the phone itself.

## The disc patcher (option A from v1, unchanged)
- **The release:** our patch, an xdelta of `DRA.BIN` plus `COOP.BIN`, and a manifest. It holds only our code and the hook bytes, never game data.
- **The patcher:**
  1. checks the user's disc image (`.bin/.cue`, or `.chd`), recognizing region and revision by hash;
  2. rebuilds the image with `COOP.BIN` and `COOPPAD`;
  3. checks the result's hash.
- **The output:** written next to the original, which is never modified.
- **Where it runs:** inside the launcher's wizard, as a command-line tool, and possibly later as a web page.
- **The release check:** each release's patch must give a disc identical to `build_disc.sh`'s.

## The BIOS: ship OpenBIOS, no BIOS hunt
**Tested 2026-10-19:** our SwanStation core runs SOTN co-op on OpenBIOS, PCSX-Redux's open-source BIOS (MIT licence), so we can ship it.
- **Covered:** boot, new game, the prologue, the game's own save rooms and memory cards, resume from the title's Load menu, and **the full harness suite: all 55 scenarios** (`COOP_BIOS=…/openbios.bin`). The only fixes needed were in two tests, which assumed the retail BIOS's boot time.

So the launcher **ships OpenBIOS as the default**. A player can still choose their own BIOS in Settings ("Use my console's BIOS"), with a clear prompt:
> *A PlayStation BIOS file, dumped from your own console: USA "SCPH-1001", "SCPH-5501" or "SCPH-7001" (a 512 KB file, usually named like `scph5501.bin`).*

The file is recognized by hash, and the launcher says which BIOS it found. If any real-BIOS-only problem shows up in playtests, that's what the option is for.

## Savestates: plenty for debugging, never deleted
- **Predefined debug savestates** ship as a "Debug starts" menu: every harness checkpoint and every playtest preset, one per stage, boss room and save room on the route.
  - **How they're made:** on the player's PC, by the launcher on first run, from their own disc. Savestates hold game RAM, so we never ship them (D9).
  - **The list:** the castle entrance, the hall, the Alchemy Lab and its elevator shaft, Marble Gallery, Outer Wall, next to the Doppleganger, next to Maria, a save room, plus each later stage as the route grows. Making them takes about a minute, with a progress bar.
- **During a playthrough, the launcher keeps every savestate it makes, forever, but it makes few:**
  - **No timed autosaves** (Tucker: that wastes space).
  - **Only on moments worth going back to:** the first time either player enters a stage, a boss fight starting, and quitting. A joint save is a restore point already (the memory cards); deaths are covered by the boss states.
  - **Storage:** zstd-compressed, with B's state compressed against A's. That's about 2 MB per moment for both games (measured: 1.4 MB for A, under 0.9 MB for B), roughly 200 MB for a whole playthrough.
  - **Naming:** each file is named `<playthrough>/<time>_<event>_<A|B>.state.zst`, and every write goes to a new name, so nothing is ever overwritten or deleted by the launcher.
- **The space used is always clear:**
  - The home screen's Savestates entry shows the total ("Savestates: 142 MB").
  - The Savestates screen lists each playthrough with its size and date. It has an "Open folder" button and a "Delete this playthrough's savestates" button, which asks the player to confirm and is the only way anything is deleted.
  - Settings shows where everything lives, with sizes: saves, savestates, reports and debug starts.
  - The README and the first-run wizard say where savestates go and that the player can clean them up.
- **A savestate browser in the launcher** loads any of them into both games: "go back to before the boss". It's handy for players, and essential for debugging.

## F9: a full environment snapshot
F9, or "Report a problem" on the pause screen, writes one zip to `reports/<time>.zip`, ready to send. It holds everything needed to see, and replay, what happened:
- **Both games now:** savestates, both memory cards, `session.coop`, screenshots of both screens and of the window.
- **The lead-up:**
  - the rolling in-memory states from 5 and 10 s before;
  - the last 60 s of both pads;
  - the last 60 s of link events and snapshots, both ways, with timestamps;
  - the frame-time log.
- **The environment:**
  - versions: launcher, patch, link protocol and core;
  - the disc's hash, the BIOS used (by hash), and the OS;
  - the launcher's settings, controller names and mappings, and the launcher and emulator logs.
- **A text box:** "What happened?" (optional; the pause screen lets the player type it).

`harness/replay.py` opens these zips directly.

## The player's launcher (Windows first)
- **One installer**, `SOTN-Coop-setup.exe`. It holds the launcher, the SwanStation core, OpenBIOS and the patcher, with an embedded Python (PyInstaller); nothing else to install.
- **The first-run wizard:** (1) where's your SOTN disc image? (file picker; it's checked and patched); (2) controllers: press a button on pad 1, then pad 2; (3) make the debug starts (progress bar). That's all.
- **Home:** Continue / New game, plus Load a savestate, Settings, Report a problem, and Quit.
  - **Settings:** controls, music source, aggro chance, BIOS, folders.
  - **The dev presets** are under "Debug starts".
- **Updates:** a check at start-up against GitHub releases; one click updates the launcher and the patch, and re-patches the disc. Mismatched versions are refused for online play later.
- **Where things live:**
  - the program folder;
  - `Documents\SOTN Co-op\` for player data: saves, savestates, reports, and the debug starts;
  - the patched disc next to the original.

## Acceptance criteria
1. **Install:** on a clean Windows user account, the installer plus the wizard get from download to the home screen in under 5 minutes. Nothing else is installed, no BIOS is needed, and Tucker does it without instructions.
2. **The patcher:**
   - It rejects a wrong disc (other region, a modified image) with a plain message.
   - Its output is byte-identical to `build_disc.sh`'s (harness check).
   - The original image is untouched.
3. **New game:** New game → the prologue → Alucard → the first save room. Quit, then Continue: both games resume in the save room. On OpenBIOS.
4. **Savestates are never deleted, and their space is visible:**
   - A session writes event savestates (a new stage, a boss, quitting) for both games, and none on a timer.
   - The home screen and the Savestates screen show the right total, and deleting a playthrough's savestates asks first.
   - No file in the archive is ever overwritten or removed (a harness check over a session).
   - Any of them loads from the browser.
5. **F9:** the zip has every item listed above, and `replay.py` replays it in the harness.
6. **The debug starts:** each one loads, and a test runs from each.
7. **Regression:** the harness suite passes on OpenBIOS and on a real BIOS, on the disc the patcher made.
8. **Online-ready:** `docs/link-protocol.md` exists, and a test drives the host only through the spec's messages over UDP.
9. **Manual (Tucker), playtest 3:** install from scratch, then play from a new game through Slogra and Gaibon and the Doppleganger.

## Risks
- **Licences:**
  - SwanStation is GPL-3.0: bundling it is fine, with its source offered.
  - OpenBIOS is MIT: fine to bundle with its notice.
  - Our launcher stays AGPL like the decomp.
- **OpenBIOS gaps** may exist outside what the suite covers. The real-BIOS option is the fallback, and playtest 3 uses OpenBIOS on purpose.
- **Archive growth:** about 200 MB per playthrough, always shown, and deleted only by the player.
- **Antivirus false positives** on PyInstaller executables; signing comes later.
