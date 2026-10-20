# M7b design: Polish M7 into something a non-technical player can use

**Status:** built 2026-10-20 on `coop-m7b-polish`, with a draft release `v0.7.1` for Tucker to test and publish. Approved earlier that day (Tucker: no stretch mode, ship unsigned, Tucker publishes the release after testing it, and add a networking review, part 6). M8 is tabled until Tucker decides the mixed-character rules.

## Result
| # | criterion | evidence |
|---|---|---|
| 1 | `release_draft` | `scripts/release.py 0.7.1`: draft release with `SOTN-Coop-setup.exe` + `SHA256SUMS.txt`. Game-data check passes (1,286 files; our `app/` files on an allow-list; no disc images, savestates or cards anywhere; nothing disc-sized). The download from the draft matches its SHA-256. The README link (`releases/latest/download/SOTN-Coop-setup.exe`) resolves once Tucker publishes. |
| 2 | `ux_couch_lobby` | `launcher/uxdriver.py couch`, on Linux headless, on Windows from the stage, and on Windows from the **installed** copy (also under RedirectionGuard). It passes all of these, with 21 screenshots: the locked character can't be ready, home to playing in 10 or fewer inputs (5 on the plain path), Back un-joins, an unplugged pad pauses that game, another pad takes over, and the pause menu changes the layout. |
| 3 | `ux_online_lobby` | `uxdriver.py online` on Windows: two launchers, host and join by room code, both lobbies show "Connected · ping", both play 15 s, both status bars show "Partner connected · ping 19 ms (good)". Passes through the folder relay **and through the real ntfy.sh relay with real STUN**. |
| 4 | `window_layouts` | `uxdriver.py window`: every layout (automatic, side by side, stacked, P1, P2, two windows) × both pixel modes, plus 1280×720, 1920×1080, 1080×1920, 700×400, fullscreen and maximized: 34 screenshots. `uxdriver.py perf` on Windows: a steady **60 fps** at every size, in fullscreen at the monitor's native resolution, and with two windows (59.8–60.4). The settings are saved to `settings.json` on every change. |
| 5 | `menu_bar` | `uxdriver.py menus` on Windows clicks every item through the real menu bar's window procedure (`PostMessage WM_COMMAND`). `win-home.png` shows the native bar. It hides in fullscreen (F11 or the menu). From a controller, the pause menu has Layout, Pixels and How to play, and Settings has everything else. |
| 6 | `widescreen_spike` | `docs/design/M10-widescreen-spike.md`: the emulator hack gives a pixel-identical picture. True FOV is blocked by VRAM (the framebuffers would overlap the stage textures). Recommendation: drop it, and use the 16:9 bars for co-op info. |
| 7 | `stranger_playtest` | `docs/playtest/M7b-stranger.md`: 15 friction items, 11 fixed, including **a silent crash when the installer starts the launcher** and a lobby crash with real controllers. README rewritten. |
| 8 | `net_profiles` | `docs/design/M7b-netcode.md`: before/after across 6 profiles, and `link/test_connect.py` (16 router pairings). Stutter: transatlantic 24.7% → 1.7%, bad Wi-Fi 36% → 1.8%. Bandwidth 841 → about 250 kbit/s. No hand-over on a 0.4 s blip. The host never waits (under 0.4 ms per frame, p99). |
| 9 | No regressions | 61/61 harness scenarios, `launcher/smoke.py`, `patcher/test_patcher.py` (final run: see the PR). |

**Changed from the design while building**
- **Pixels:** *Sharp* is "sharp bilinear": enlarged by whole pixels, then smoothed only the last fraction, at the true 4:3 shape. Integer multiples with borders can't also be 4:3 at most window sizes. *Smooth* is plain filtering. No stretch, ever.
- **Layouts:** added **Automatic**, the default. It picks side by side or stacked, whichever gives each game the bigger picture.
- **Game menu:** Pause, Report a problem, Leave. Reset and "Joint save now" were left out: the coffins are the save points by design, and a reset of one game mid-co-op has no clear meaning.
- **Debug starts and network simulation:** under Help › Developer. *Simulate a network* runs couch play through the network simulator (`link/netsim.py`), to feel it.
**Why:** M7 works in the harness, but a stranger can't actually get it. The README links to a release that doesn't exist, the launcher is a fixed-size window with a flat menu, and couch and online play are mixed together on one home screen.

## What I found
- **No release.** `gh release list` on `tucker-bower/sotn-coop` is empty. The installer (`SOTN-Coop-setup-0.7.0.exe`) only exists on Tucker's PC. STATUS also says the M7 PRs are open, but there are none: M7 landed on `main` directly. I'll fix STATUS.
- **No "built-in" emulator menus to reuse.** The launcher is our own pygame frontend around the SwanStation *libretro core* (D36). A core is only the emulation engine. The File/Options/Help menus you're picturing belong to frontends (DuckStation, RetroArch), and we don't use those. So we build menus ourselves. The core's settings (renderer, aspect ratio, widescreen hack) are exposed to us as options we can show.
- **The window is fixed at 1032×532.** Each game is drawn at 2× with square pixels, which is slightly the wrong shape (the PS1 shows 4:3).
- **Online already shows only your own game.** The partner's picture never leaves their PC. Showing it would mean video streaming, which is out of scope. So "hide the second screen" only applies to couch play.
- **Installer metadata points at the old repo** (`AppPublisherURL` = `sotn-decomp-coop`).

## Scope (five parts)

### 1. A real release
- `scripts/release.py`:
  - builds the installer
  - checks that the installer contains no game data (allow-list of file types, plus a scan for disc-sized blobs)
  - writes SHA-256 sums and runs `gh release create vX.Y.Z`
  - uploads the installer under a fixed name, `SOTN-Coop-setup.exe`, so the README can link straight to `releases/latest/download/SOTN-Coop-setup.exe`
- Release notes cover what's new, the known gaps, and what you need (your own disc).
- **Publishing is outward-facing:** I build the release as a **draft**, and Tucker publishes it after testing it (D76).
- **Unsigned-installer warnings (shipped unsigned, D76).** A non-technical user will hit two of them: the browser's "this file isn't commonly downloaded", then Windows SmartScreen's "Windows protected your PC". The README shows exactly what to click.

### 2. Launcher flow: pick a mode first, then a lobby
```
Home:  Couch co-op  |  Online co-op  |  Settings  |  Quit        (Debug starts → Help ▸ Developer)
Couch: Lobby ──► Playthrough (Continue <name> / New game / Savestates) ──► Play
Online: Host or Join (code) ──► Lobby (you + partner's slot) ──► host picks Playthrough ──► Play
```
- **Couch lobby (one screen for both players).** There are two player cards. Each says *"Press any button to join"* until someone does:
  - the first controller pressed becomes P1, the next becomes P2, and the keyboard can join either slot
  - each card shows the controller's name, a character picker (Alucard selectable; Richter/Maria greyed out as "Coming later"), and a Ready state
  - play starts when both players are Ready
  - **Back** on a card un-joins that player, so swapping controllers needs no Settings menu
  - this replaces the first-run "Player 1: press a button" wizard step
- **Online lobby.** Your card on one side. On the other: the partner's card showing *Waiting / Connected (name, ping)*, with the room code shown big plus a **Copy** button.
- **Mid-game controller unplug:** that player's game pauses and shows *"Player 2: controller disconnected. Press any button to reconnect."*
- Character choice is saved per playthrough (Alucard only for now), so M8 just has to unlock the picker.

### 3. A proper window: menu bar, resizing, layouts
**Menu bar options**
| Option | Idea | Verdict |
|---|---|---|
| **A. Native Windows menu bar on the SDL window** (via ctypes `SetMenu` on the pygame HWND; clicks come back as `SYSWMEVENT`) | A real File / Game / View / Controllers / Help bar that looks like any Windows app. Hidden in fullscreen. Every item is also reachable from the controller pause menu, for couch players on a TV. | ✅ **Recommended.** Exactly what you asked for, about 200 lines, no new dependencies. Android (M9) would use its own touch UI anyway. |
| B. A menu bar we draw in pygame | Same items, our own look, works on Linux and Android | Fallback if A fails the spike. It looks less native. |
| C. Rewrite the launcher in Qt (PySide6) | Native menus, docking, dialogs | ❌ Adds about 80 MB to the installer, means rewriting app.py and gameview.py, and makes the M9 Android port harder. |

**Menus:**
- **File:** New game, Continue, Savestates, Open data folder, Quit
- **Game:** Pause, Reset, Joint save now, Report a problem (F9)
- **View:** Layout ▸, Scaling ▸, Fullscreen (F11 / Alt+Enter), Widescreen ▸ (see part 4)
- **Controllers:** Lobby, Keyboard keys
- **Help:** How to play, Online troubleshooting, Developer ▸ (Debug starts, logs), About / version

**Resizing and scaling.**
- The window can be resized and maximized, and it remembers its size, position and monitor.
- Scaling modes:
  - *Sharp* (integer multiples, black borders), the default
  - *Fit, 4:3* (the correct shape, smooth)
  - No stretch mode (owner, D76)
- Drawing moves to pygame's SDL2 GPU renderer (`pygame._sdl2.video`), so scaling two games to 4K costs nothing on the CPU.

**Layouts (View ▸ Layout):**
- **Couch:** *Side by side* (default) · *Stacked* (vertical monitor) · *Separate windows* (one per monitor or TV; pygame 2 supports several windows) · *Player 1 only* / *Player 2 only* (e.g. P2 on a second window you've hidden)
- **Online:** your game only, with the status bar showing partner state and ping

### 4. Widescreen / expanded FOV: research and a spike only
| Option | What it is | Verdict |
|---|---|---|
| A. SwanStation "widescreen hack" | Widens *3D (GTE) geometry* | ❌ SOTN is almost all 2D sprites and tiles, so expected result: no wider view, only stretched 3D bits. I'll check in the spike (about 30 min). |
| B. Stretch to 16:9 | Distorts the picture | ❌ Never offered (owner, D76). |
| C. **True expanded FOV in the game** | Wider PS1 display mode (e.g. 384 px instead of 256), plus wider camera, tile-layer drawing, enemy spawn/despawn and culling windows, HUD anchoring and VRAM framebuffer layout | The real thing, and it's M10's job. The constraints: VRAM is tight; DRA changes must be size-neutral (D33); and shared rooms need both players on the **same** width, because spawn windows change gameplay. |

**M7b deliverable for widescreen:** a one-session spike (A tested, plus a count of hard-coded 256-wide constants and culling sites in DRA and stage code, plus a VRAM layout check). It ends in a short go/no-go and cost estimate added to the M10 design. No widescreen code ships in M7b.

### 5. The "stranger" playtest
I play the part of a non-technical Windows user, starting from nothing:
1. **Clean slate:** uninstall, then delete `%LOCALAPPDATA%\Programs\SOTN Co-op`, `Documents\SOTN Co-op` and the settings.
2. **Read only the README:**
   - download from the real release link with a Windows browser download (not my build folder)
   - note every warning dialog and every unexplained term (".cue", "BIOS", "endpoint code", "ip:port")
3. **Install interactively and start the launcher.** A new `launcher/uxdriver.py` feeds scripted controller and keyboard input and saves a screenshot of every launcher screen, so each step is reproducible and checkable. Game frames are shown only in the private report and never committed (they're ROM-derived).
4. **Couch:** two pads join the lobby → New game → both reach the Castle Entrance.
5. **Online:** two installs on one PC host and join through the real code flow. Then join from WSL across its NAT as the closest stand-in for a second home.
6. **Output:** `docs/playtest/M7b-stranger.md`. It lists each step, the time taken, the clicks needed and any friction found, each item marked *fixed* or *left (why)*. The friction fixes are part of M7b.

What I can't do is a real internet session between two homes. That stays your playtest, ideally with a friend who has never seen the project.

### 6. Networking review: real-world ping, jitter and loss
The M7 online code (`link/`) has only been tested on loopback, plus one MTU and loss scenario. Online feel matters as much as the visuals, so this part checks it under realistic network conditions:
- **Review** the transport, snapshot, reliable-message and rendezvous code. That means checking framing, retransmit timing, sequence wrap, stale and out-of-order packets, what happens on bursty loss, and bandwidth per second.
- **Network simulator** in the test harness, between the two hosts. It adds configurable one-way delay, jitter, loss (random and bursty), reordering, duplication and a bandwidth cap. It's seeded, so runs are reproducible. Profiles:
  - *LAN* (1 ms)
  - *same city* (20 ms ±5, 0.1% loss)
  - *cross-country* (40 ms ±10, 0.5%)
  - *transatlantic* (75 ms ±15, 1%)
  - *bad Wi-Fi* (30 ms ±40, 3% loss in bursts)
  - *cellular hotspot* (60 ms ±30, 2%, 1 Mbit/s cap)
- **Measure what players feel:**
  - how smooth the partner puppet looks (position error vs. truth, and how far it teleports when it catches up)
  - shared-enemy correctness and how stale the guest's view of them is
  - time to apply relic, item and flag grants
  - joint save, Continue and both-dead reload completing
  - boss pull-in time
  - recovery after a 2–5 s connection drop
  - the local game must **never** stall waiting for the network
- **Optimize** where the numbers say so, for example puppet interpolation or extrapolation, snapshot rate and delta encoding, retransmit timeouts tuned to the measured round-trip time, and a ping and connection-quality readout in the status bar. Each change is checked against the simulator, before and after.
- **Output:** `docs/design/M7b-netcode.md`, with findings, the before/after table per profile, and the changes made.

## Acceptance criteria
1. **`release_draft`:** `scripts/release.py` makes a draft GitHub release with `SOTN-Coop-setup.exe` and SHA-256 sums. The game-data scan passes. The README's download link resolves once the release is published.
2. **`ux_couch_lobby`:** uxdriver: from a fresh install, two pads join → Ready → New game → both games in play. Screenshots of every screen, under 10 inputs after the disc is picked. Back un-joins a player. Unplugging a pad mid-game pauses that player's game, and re-plugging resumes it.
3. **`ux_online_lobby`:** two installs host and join through the code flow, both lobbies show Connected, the host starts, and both are in play.
4. **`window_layouts`:** each layout (side by side, stacked, separate windows, single) and each scaling mode is shown at 1280×720, 1920×1080, 1080×1920 and after a resize. The games run at 60 fps at 4K on the GPU renderer. The settings survive a restart.
5. **`menu_bar`:** every menu item works through the native menu and through the controller pause menu (uxdriver), and the bar is hidden in fullscreen.
6. **`widescreen_spike`:** findings and an estimate are added to the M10 design.
7. **`stranger_playtest`:** report committed. Every friction item is fixed or justified. README rewritten from it (plain words, warning-dialog screenshots, a disc-ripping pointer).
8. **`net_profiles`:** with every network profile, the online scenarios pass (connect, shared room, grants, joint save, Continue, both-dead reload, boss pull-in, 5 s drop and recover). The local game never misses a frame because of the network. The puppet error and grant times are in `M7b-netcode.md`, and *transatlantic* feels smooth (bounds set once the baseline numbers are in).
9. **No regressions:** 61/61 harness scenarios, `launcher/smoke.py`, `patcher/test_patcher.py`.

## Defaults I'll take unless you object
- Branch `coop-m7b-polish`, version **0.7.1**.
- Richter and Maria shown greyed out as "Coming later" in the lobby, not hidden.
- Default layout: Automatic (built; see above), *Sharp* pixels.
- Debug starts move out of the home screen and into Help ▸ Developer.

## Decisions (resolved 2026-10-20, D76)
- Ship unsigned. Tucker publishes the release after testing it. No stretch mode.

## Risks
- **Native menu (A):** SDL's `SYSWMEVENT` might not pass `WM_COMMAND` through cleanly. The spike settles it on day 1, and option B is the fallback.
- **Separate windows:** with two windows, focus and keyboard input go to only one. Controllers are fine. The keyboard player has to stay on the focused window.
- **Moving drawing to the GPU renderer** touches the frame loop. Determinism is unaffected (drawing is host-side), but F9 report screenshots need re-checking.

## Budget
About 4–5 usage windows:
- release, lobby and menus: about 2
- layouts and scaling: about 1
- widescreen spike plus stranger playtest and fixes: about 1
- networking review and optimization: about 1
