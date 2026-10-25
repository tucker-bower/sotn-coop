# M9 design: Android

**Status:** Tucker delegated the design (2026-10-21: "I'll leave it all up to your best judgement"). Decisions are logged as agent-defaults (D93+). Branch `coop-m9-android`, stacked on M8.

## Goal
An Android app that plays SOTN Co-op **online**, against another Android device or a PC, with the same features as the PC's online mode:
- room codes
- shared rooms
- joint saves
- Richter and Maria
- controller-first menus

Couch co-op on one device isn't a goal (Tucker).

## Options
| Option | Idea | Verdict |
|---|---|---|
| **A. The same Python, packaged with python-for-android** | The game, link and host code (`harness/emu.py`, `harness/session.py`, `link/*`) run unchanged on Android: CPython + pygame (SDL2) + ctypes loading the SwanStation core built for Android. A slim front end replaces the PC launcher's windows and menu bar. | ✅ **Chosen.** One protocol implementation, so Android and PC play each other by construction. Most of the code is already tested by the harness. |
| B. A native Kotlin app with a C libretro frontend | Rewrite the link, host and joint saves in Kotlin | ❌ About 3–4k lines to port and keep in sync with the PC forever; a protocol drift breaks cross-play |
| C. A RetroArch core plus a companion app | Players run RetroArch with our disc; a separate app does the link | ❌ Two apps to set up, and RetroArch doesn't expose the RAM mailbox per frame |

## How (A)
- **Packaging:** python-for-android (`p4a`), SDL2 bootstrap, `python3,pygame` (p4a's recipe: pygame 2.1, SDL2). Our PC launcher uses pygame-ce, so the Android front end sticks to the APIs both share.
- **One game, in the app's own process:** Android apps can't start Python worker processes, so the game runs in-process (`OnlineSession(in_process=True)`, `harness/session.py`'s `_Worker`/`InProcessGame`). The PC paths are unchanged.
- **The core:** `swanstation_libretro_android.so` from the libretro buildbot (arm64-v8a for phones, x86_64 for the test emulators), shipped in the APK.
- **The disc:** the player picks their SOTN disc image in the app, which copies it into the app's own storage. The patch is applied there, as on the PC (`patcher/`). Maria: the DXC .iso, the same way.
- **The BIOS:** the bundled OpenBIOS, as on the PC.
- **Input:** a Bluetooth or USB controller through SDL's game controller API. Handhelds like the AYN Thor appear as one. Touch controls aren't in M9 (the roadmap says controller-first); they're a backlog item.

## Testing
- Two headless Android emulators (x86_64 images, KVM in WSL) on the dev PC: nothing appears on Tucker's desktop.
- **Session tests:**
  - **The protocol, without Android:** `session_m9.online_in_process`. An in-process game (as on Android) and a PC worker game connect by room code and share a room.
  - **On Android:** an instrumented run of the APK in each emulator. A test mode plays scripted inputs and writes its presence and mailbox state to logcat. A driver on the PC reads both and asserts: connected, each sees the other, a shared room, a joint save.
  - **Cross-play:** one emulator against a PC game.
- No couch tests (Tucker).

## Acceptance criteria
1. **The APK builds** reproducibly from a clean checkout (`android/build.sh`) for arm64-v8a and x86_64, with no game data in it (the same check as the PC installer).
2. **Two Android devices play together** (`android_pair`): two emulators connect by room code, see each other's puppets, share a room, and make a joint save.
3. **Android and PC play together** (`android_pc`): an emulator and a PC launcher game do the same.
4. **Setup on the device:** picking the SOTN disc (and optionally the DXC disc) patches it and shows the lobby. Wrong files get the PC's plain errors.
5. **Real time:** the game runs at full speed on the x86_64 emulator, with frame times logged. Real arm64 phones: Tucker's spot check.
