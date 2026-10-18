# Roadmap

**Target:** Alucard + Richter "P2 Lite" playable through the opening areas, on stock emulators in 8MB mode, within about a month (by 2026-11-18), on a Claude Pro subscription.

## Budget model
Pro usage limits are measured in rolling 5-hour windows (plus possible weekly caps), not published token counts. So the budget is a **share of the month's usage**, tracked by elapsed days and by how often limits are hit.

**Realistic expectation:** making Richter P2 (D7) adds a relocation milestone. It's still the right call, but it makes the month tight. M1 and M2 are the checkpoints where we decide on scope cuts or a plan upgrade. Maria as P2 and full boss coverage are post-month.

| # | Milestone | Budget (share of month) | Target date |
|---|---|---|---|
| M0 | Test harness + 8MB verification | 12% | 2026-10-22 |
| M1 | Ghost P2 (Alucard) | 13% | 2026-10-26 |
| M2 | Richter as P2 | 20% | 2026-11-01 |
| M3 | Combat + targeting | 20% | 2026-11-07 |
| M4 | Rooms & warps | 15% | 2026-11-12 |
| M5 | P2 Lite playable + netplay | 12% | 2026-11-17 |
| — | Reserve | 8% | — |
| M6+ | Maria, bosses, inverted castle, independent P2 | post-month | — |

## Acceptance criteria (draft, finalized in each milestone's design doc)

### M0: Test harness + 8MB verification
- The matching `us` build is reproducible from a clean checkout with one script.
- The game runs headless and frame-stepped, with input injection, savestates, and RAM reads by symbol name.
- A bot walks Alucard through the first 3 rooms of the entrance, with RAM assertions.
- A lockstep check runs two instances and compares RAM every frame.
- 8MB mode is verified to boot a test build on DuckStation, Beetle PSX, SwanStation and PCSX-Redux. The results are recorded.

### M1: Ghost P2 (Alucard)
- Pad 2 controls a second Alucard (walk, jump, crouch, turn) via the context-swap approach.
- P2 is palette-tinted, and there's no crash or desync over a 10-minute scripted run.

### M2: Richter as P2
- `RIC.BIN` is relinked into the 8MB area and loads alongside Alucard.
- Pad 2 controls Richter, with his own sprites and moves, alongside P1 Alucard.
- Character-specific engine branches (`g_PlayableCharacter` and similar) are swapped correctly per player.

### M3: Combat + targeting
- Both players' attacks damage enemies, and enemies can damage both players.
- The shared targeting helpers in `st_common.h` pick the nearest player. Direct `PLAYER` reads are fixed for every stage on the test route.

### M4: Rooms & warps
- P2 warps to P1 on doors, cutscenes and boss intros, and never softlocks off-screen.
- Zero softlocks across the scripted route: entrance → Alchemy Lab → Marble Gallery → Outer Wall.

### M5: P2 Lite playable
- Human playtest of the opening areas through the first few bosses, on PC.
- Runs on all verified emulators. RetroArch netplay runs 30 minutes with no desync.
- The bring-your-own-disc build script produces the patched image (D9).
