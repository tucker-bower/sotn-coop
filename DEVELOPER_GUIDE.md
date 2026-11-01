# Developer guide

How to set up a machine to work on SOTN Co-op. Players don't need any of this: they use the [installer or APK](README.md). How the mod works is in [`docs/TECHNICAL_SUMMARY.md`](docs/TECHNICAL_SUMMARY.md), and how we work and test is in [`AGENTS.md`](AGENTS.md).

## What you need
- **Ubuntu 26.04**, natively or in WSL2. Passwordless sudo lets the bootstrap run unattended.
- **Your own disc images.** No game data is in this repo, and none may ever be committed.
  - Required: *Symphony of the Night* (USA, SLUS-00067).
  - Optional: *Dracula X Chronicles* (USA, ULUS-10277), for Maria.
- **[GitHub CLI](https://cli.github.com/)**, signed in, to open PRs and make releases.

## First-time setup
1. Clone the repo. On WSL2, keep it in the Linux filesystem, not under `/mnt/c`: builds are much slower there.
2. Put your discs in `disks/` (git-ignored):
   - `sotn.us.cue` and its `.bin` tracks
   - `sotn.pspus.iso`, if you have it
3. Run `scripts/bootstrap.sh`. It installs the packages, fetches the pinned `sotn-decomp`, applies `patches/sotn-decomp.patch`, builds the SwanStation core and OpenBIOS, and checks that the US build matches retail. It's safe to re-run, and you can run single steps: `scripts/bootstrap.sh decomp`. The steps are `apt python swanstation openbios decomp`.
4. Run `scripts/doctor.py`. Every required check should pass, and each failure says how to fix it. Run it whenever something seems off.
5. Run `scripts/rebuild_fixtures.sh` (about 15 minutes). It builds the co-op disc and the savestates that most tests start from.
6. Try a test:
   ```
   .env/src/sotn-decomp/.venv/bin/python harness/run.py pvp_off
   ```

## Your local environment
Three git-ignored places hold what's specific to your machine.

**`env.toml`: paths.** `env.example.toml` lists every path and its default, and is committed. To change one, put only that entry in `env.toml`:
```toml
[paths]
win_emulators = "/mnt/c/Users/you/Emulators"   # Windows tools, seen from WSL
win_masters = "/mnt/c/Users/you/Emulators/SOTN"  # your master copies of the discs
```
`scripts/doctor.py` shows the paths it found. You can skip this file if the defaults suit you.

**`LOCAL.md`: notes for agents and yourself.** Agents read it if it exists, so use it for anything about your setup that they should know: your folders, your test devices, how you like builds delivered. Keep personal details here, never in tracked files.

**`local/`: anything else of yours,** such as playtest sheets and notes.

## What each kind of work needs
| To | You also need |
|---|---|
| Build and run tests | Only the setup above |
| Check on PCSX-Redux (`scripts/redux_check.sh`) | PCSX-Redux in `win_emulators` |
| Build the Windows installer | `scripts/bootstrap.sh swanstation_win`, Windows Python, and Inno Setup in `win_emulators` |
| Build the Android app | `scripts/android_setup.sh` (installs to `~/android`) and `scripts/bootstrap.sh swanstation_android` |
| Test on an Android device | adb in `android-tools` in `win_emulators`, then `android/device.py` over USB |
| Sign an Android release | The release key, kept outside the repo (`[android]` in `env.example.toml`). Only the maintainer has it |

## Where things are
| What | Where |
|---|---|
| Your discs | `disks/` |
| Everything built or downloaded: core, OpenBIOS, savestates, test output | `.env/` |
| Pinned sotn-decomp | `.env/src/sotn-decomp/` |
| Python venv, for the decomp's tools and the harness | `.env/src/sotn-decomp/.venv/` |
| The co-op disc | `.env/out/disc/` |
| Test reports, clips and logs | `.env/out/<test name>/` |

## Everyday commands
| Command | What it does |
|---|---|
| `scripts/doctor.py` | Checks the machine |
| `scripts/build_disc.sh` | Builds the co-op disc. Fails if a hook changes DRA's size or a retail file moves |
| `scripts/rebuild_fixtures.sh` | Rebuilds the disc and savestates. Needed after any module change |
| `harness/run.py` | Runs the tests: see [`AGENTS.md`](AGENTS.md) |
| `scripts/release.py <version>` | Builds the installer and a draft GitHub release |

## Troubleshooting
- **A first build failed partway:** run `rm -rf build/us` in `.env/src/sotn-decomp`, then build again. Ninja keeps the broken objects.
- **Savestates won't load, or tests read garbage from the mailbox:** the savestates are from another build. Run `scripts/rebuild_fixtures.sh`, and don't rebuild while tests are running.
- **`include/lba_us.h` shows as changed in the decomp:** upstream's `make disk` rewrites it. Restore it with `git checkout include/lba_us.h`.
- **`gcc-mipsel-linux-gnu` is missing:** Ubuntu 26.04 doesn't have it, so the bootstrap installs it from 24.04 with a low-priority apt pin (D12). Re-run `scripts/bootstrap.sh apt`.
- **An Android device isn't found from WSL:** WSL can't see USB, so `android/device.py` uses the Windows adb.
