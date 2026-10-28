# M18 design: Mac and Linux

**Status:** proposal for Tucker's review (2026-10-27).

## Goal
The same launcher, the same features and the same cross-play on macOS (Apple Silicon and Intel) and Linux, **the Steam Deck included**. The stack already runs on Linux in development (Python, pygame-ce, libretro.py, SwanStation), so this is mostly packaging and testing.

## Packaging
| | Option | Verdict |
|---|---|---|
| **Linux** | **A. AppImage (recommended)** | ✅ One file, runs on the Steam Deck's desktop mode and most distributions. A "Add to Steam" note for Game Mode. |
| | B. Flatpak (Flathub) | Later: more reach, more review and sandbox work |
| **Mac** | **A. A `.app` with its own Python (python-build-standalone) and a universal SwanStation dylib, in a `.dmg` (recommended)** | ✅ Same shape as the Windows build |
| | B. Homebrew formula | ❌ Players aren't developers |

## Signing (decision for Tucker)
An unsigned Mac app is blocked on first open (right-click › Open, or System Settings › Open Anyway). Options:
1. **Unsigned, with the steps in the README (recommended for now):** free; like our unsigned Windows installer.
2. **Apple Developer ID and notarization:** $99/year, opens normally.

## Testing without a Mac
We have no Mac. GitHub's macOS runners are free for public repositories: CI builds the `.app` there and runs the harness's smoke and a two-game session headless. A real-Mac check by a community tester before release. Linux runs the full suite as now (WSL), plus a Steam Deck-like check (Gamescope, a controller only).

## Acceptance criteria
1. CI builds the AppImage and the `.dmg` from a clean checkout, with the licence folder and the game-data check.
2. On a macOS runner: `launcher/smoke.py` and a two-game couch session pass.
3. On Linux: the full suite, `smoke.py`, and the launcher's uxdriver couch/online flows.
4. Cross-play: Mac or Linux with Windows and Android online (`online_*` across platforms, via natsim).
5. Controller-only use on Linux (Steam Deck mode): every screen reachable without a keyboard.
6. A community tester's report from a real Mac and a Steam Deck.

## Risks
- **Mac security prompts** (the local network permission, the unsigned app): each needs a line in the README.
- **SwanStation on Apple Silicon:** the libretro core builds for arm64, but its CPU recompiler may not; the interpreter is slower. Measured in CI.

## Budget
About 3–5 usage windows.
