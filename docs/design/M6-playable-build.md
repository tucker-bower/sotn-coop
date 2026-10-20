# M6 design: A playable build

**Status:** proposal, awaiting Tucker's approval.
**Context:** the roadmap's M6, D8 (ship as a patched disc image), D9 (build from the user's own disc), D36 (our own launcher, PC couch first).

## Goal
Someone with their own SOTN (USA) disc image, a Windows PC and two controllers can install co-op and play it from a new game through the first few bosses, without the decomp toolchain or WSL. Tucker's playtest of that path is the acceptance.

## What's missing today
- **The co-op disc** is made by `scripts/build_disc.sh`. That needs the whole sotn-decomp toolchain (Linux, Go, a MIPS compiler) and builds every overlay. Fine for us, but not for a player.
- **The launcher** is installed by `scripts/install_launcher.sh` from WSL. It copies harness files, makes a Python venv and generates savestates. The playtest presets are dev tools; a player needs "New game" and "Continue".
- **Saves** live in `cards\` next to the launcher. That's fine, but undocumented.

## Options for making the co-op disc on the player's PC
| Option | How | For | Against |
|---|---|---|---|
| **A. Patch file (recommended)** | We publish a patch: xdelta of `DRA.BIN`, `COOP.BIN` (module code only), and a manifest. A small Python patcher checks the user's disc (track 1 hash), rebuilds the image with the patched `DRA.BIN` plus `COOP.BIN` and `COOPPAD`, and checks the result's hash. | No toolchain, one click, seconds. The patch holds only our code and the hook bytes, not game data. | D9 called an xdelta patch "subject to an owner decision": that's this decision. |
| B. Docker build (the Maria mod precedent) | The user runs a Docker image that does `build_disc.sh` from their disc. | Exactly our build. | Docker on Windows is a big ask for a couch co-op player. Slow (full decomp build). |
| C. Patch at run time | The launcher loads the retail disc and injects `COOP.BIN` and the DRA hook bytes into RAM at boot. | No disc image to make at all. | Overlays load from the CD again on every stage change, so hooks in overlays would need re-patching. It works for our RAM-only overlay patches already, but DRA is loaded once from the CD by the boot code: injecting that is doable in the emulator adapter, but it's emulator-specific code (D28). It's also harder to cross-check in other emulators. |

**Recommendation: A.**
- **Checks:** the patcher refuses any disc it doesn't recognize (wrong region or revision), and verifies the output.
- **Publishing:** the patch file goes in a GitHub release. Never a disc image.

## The player's launcher
- **One installer** (`SOTN-Coop-setup.exe`, PyInstaller plus Inno Setup). It holds Python, the launcher, the SwanStation core and the patcher. The first run asks for the disc image and makes the co-op disc next to it. The BIOS comes from the user too (like any emulator), with a file picker.
- **Menu (in the window):** New game (both), Continue (joint save), Settings (controllers, music source, aggro chance), Quit. The dev presets stay behind a `--dev` flag.
- **F9 bookmarks** stay, so a player's bug report is a folder to zip.

## Acceptance criteria
1. On a clean Windows machine (Tucker's PC with the dev folders renamed), `SOTN-Coop-setup.exe` installs, asks for the disc image and BIOS, makes the co-op disc and starts the menu. Under 5 minutes, with no other software installed.
2. The patcher rejects a wrong disc with a clear message, and the image it makes is byte-identical to `build_disc.sh`'s (harness check).
3. New game → prologue → Alucard → the first save room → Continue after quitting: both games resume in the save room.
4. The harness suite passes on the disc the patcher made.
5. **Manual (Tucker):** from a new game through Slogra and Gaibon and the Doppleganger, with notes (playtest 3).

## Risks
- **SwanStation's licence (GPL-3.0)** allows bundling the core with the source offered. Our launcher stays AGPL like the decomp.
- **The BIOS** can't be bundled; the user provides it. SwanStation also has an HLE BIOS, which could be an option if it runs SOTN well. That needs a check.
- **Antivirus false positives** on PyInstaller executables. A signed build is a later concern.
