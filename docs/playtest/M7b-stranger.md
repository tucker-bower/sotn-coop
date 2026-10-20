# M7b stranger playtest: a first-time player, from the README

**Date:** 2026-10-20. **Who:** the agent, following only the README, on Tucker's Windows 11 PC. **Build:** 0.7.1 release candidate (the draft GitHub release).

## Method
- **Clean slate:** a fresh data folder for every run; the install went to a temp folder, with no Start-menu or desktop icons; then a silent uninstall.
- **Download:** the installer from the draft GitHub release. Drafts aren't public, so I downloaded with my GitHub login (`gh release download`) instead of a browser. The SHA-256 matched the published `SHA256SUMS.txt`.
- **Install:** the real installer, run interactively. A script photographed every page and clicked what a player would (`Next`, `Next`, `Finish`).
- **Play:** the installed launcher, driven by `launcher/uxdriver.py`. Scripted controllers: two pads join the lobby, one character is locked, a new game starts, a pad is unplugged and another takes over, then pause and leave.
- **Online:** two launchers on one PC, through the real ntfy.sh relay and real STUN. One hosts; the other types the room code.

## Timeline (first-time player)
| step | what the player does | time | inputs |
|---|---|---|---|
| Download | click the README link | — | 1 |
| Install | Information → **Next**; desktop shortcut → **Next** (installs); **Finish** (starts SOTN Co-op) | 8 s | 3 |
| First start | **Choose my disc image** → pick the `.cue` → co-op disc made → **OK** | ~5 s | 3 |
| Couch | **Couch co-op** → both press a button on their pad → both press Cross / A | ~3 s | 5 |
| Playing | new game starts (no playthroughs yet) | ~15 s boot | 0 |
| Online (host) | **Online co-op** → **Host: new game** → press a button, Cross / A → partner connects | ~17 s incl. disc | 5 |
| Online (join) | **Online co-op** → **Join your partner** → paste the code, Enter → press a button, Cross / A | ~17 s | 6 |

Home to playing is 5 inputs on the couch (Couch co-op, two joins, two readies). The check `ux_couch_lobby` requires 10 or fewer.

## Friction found
| # | friction | status |
|---|---|---|
| 0 | **The launcher started from the installer's last page ("Start SOTN Co-op") vanished at once, silently.** Inno Setup runs under Windows' RedirectionGuard, and the launcher inherits it. The first DLL pygame loads by name (libpng, for the window icon) fails: "the path cannot be traversed because it contains an untrusted mount point" (Windows searches `PATH`, and reparse-point folders there are refused). `pythonw` has no console, so nothing was shown or logged. | **Fixed:** pygame's folder goes first on `PATH` (verified: the same failure reproduced with the mitigation turned on, then gone with the fix; the full couch walkthrough, games included, passes under it). Errors under `pythonw` now go to `launcher-errors.log` in the data folder. |
| 1 | The README said "Next, Install, Finish"; the installer shows **Next, Next, Finish** | **Fixed** (README) |
| 2 | The installer had five pages (licence acceptance, folder, tasks, ready, finish) | **Fixed:** now information, tasks, finish |
| 3 | The window and taskbar used pygame's snake icon | **Fixed:** our own icon (a bat in front of the moon) on the window, installer, shortcuts and uninstaller |
| 4 | Uninstalling left `__pycache__` folders in the program folder | **Fixed:** the uninstaller removes the program folder (saves are in Documents) |
| 5 | Error messages ran off the screen as one long line | **Fixed:** wrapped |
| 6 | Glyphs the Windows font lacks (✕ ◀ ▶ ▸ □ ○ △) showed as boxes | **Fixed:** "Cross / A", drawn arrows, `›` |
| 7 | With real controllers plugged in, the lobby crashed (`Controller.as_joystick()`: "Invalid joystick device number"). Same latent bug in 0.7.0's controller matching. | **Fixed:** controllers are matched through the joystick API |
| 8 | Online between two PCs on one LAN advertised `0.0.0.0` | **Fixed:** the real LAN address |
| 9 | The ping showed `?` for the first ~15 s of a game (the game was still booting) | **Fixed:** measured from the handshake, so the lobby already shows it |
| 10 | Re-choosing the disc while a game runs failed (the co-op disc was in use) | **Fixed:** an existing, correct co-op disc is kept |
| 11 | **Browser and SmartScreen warnings:** couldn't be seen here, because files from `gh` carry no "downloaded from the internet" mark | **Left:** the README walks through Edge, Chrome and SmartScreen. Verify on the first public download. |
| 12 | **Windows Firewall** may ask about "Python" the first time online. The name is confusing. | **Left:** the README explains it. A proper fix needs our own `.exe` stub (a follow-up). |
| 13 | Disc images as `.chd` / `.pbp` (common in emulator libraries) aren't accepted | **Left:** the README says `.cue` + `.bin`. Accepting CHD would be a follow-up. |
| 14 | Settings shows the data folder path in full | **Left:** harmless, and useful when sending reports |

## Not covered (needs people)
- A real two-home internet session. The router simulation passes 12 of 16 pairings, and the real relay and STUN work on one PC, but only Tucker plus a friend can prove two homes.
- Real controllers in the lobby. Virtual controllers drive the tests; the crash in #7 was found with Tucker's real pads plugged in, and is fixed.

## Evidence
Screenshots (game screens are game data: kept out of git, in `C:\Users\tucke\AppData\Local\Temp\sotn-ux\`):
- `stranger\setup-01..03.png` (installer pages)
- `stranger\first-launch.png`
- `stranger\play\*.png` (installed copy: disc → lobby → game → unplug → pause)
- `out\onlinerealrelay\{host,join}\*.png` (online through ntfy.sh)
- `out\perf\report.json` (frame rates)
- `out\menus\win-home.png` (the native menu bar)
