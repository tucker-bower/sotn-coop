# Roadmap

**Target:** P2 Lite playable start-to-finish of the opening areas, on stock emulators, within ~1 month (by 2026-11-18) on a Claude Pro subscription.

## Budget model
Pro usage limits are measured in rolling 5-hour windows (plus possible weekly caps), not published token counts, so the budget is expressed as a **share of the month's usage**. We track spend by elapsed days and by how often limits are hit.

**Realistic expectation:** M0–M4 ("P2 Lite") fits the month only if the scope stays tight. M5+ (full edge-case coverage and the stretch goals) almost certainly needs either more time or a plan upgrade. We'll know after M1, which is the first real read on how hard the engine fights a second player.

| # | Milestone | Budget (share of month) | Target date |
|---|---|---|---|
| M0 | Test harness | 15% | 2026-10-22 |
| M1 | Ghost P2 | 15% | 2026-10-27 |
| M2 | Combat | 20% | 2026-11-02 |
| M3 | Rooms & warps | 20% | 2026-11-09 |
| M4 | P2 Lite playable + netplay | 20% | 2026-11-16 |
| — | Reserve | 10% | — |
| M5+ | Edge cases & stretch | post-month | — |

## Acceptance criteria (draft, finalized in each milestone's design doc)

### M0: Test harness
- The matching `us` build is reproducible from a clean checkout with one script.
- The game runs headless and frame-stepped, with input injection, savestate load/save, and RAM reads by symbol name (from the decomp's map files).
- A bot walks Alucard from the castle entrance through the first 3 rooms, with RAM assertions on room ID and position.
- A lockstep check runs two instances on the same inputs and compares RAM every frame.

### M1: Ghost P2
- Pad 2 controls a second Alucard: walk, jump, crouch, turn, with correct animation.
- P2 renders with a palette tint so the players can be told apart.
- No crash or desync over a 10-minute scripted run of the entrance area.
- The memory and overlay budget impact is measured and documented.

### M2: Combat
- P2 attacks with P1's equipped weapons, and hits register on enemies.
- Enemies can damage P2, with knockback and invincibility frames. Shared HP (Lite rules).
- Enemy targeting considers both players, at least for the entrance and early enemies.

### M3: Rooms & warps
- When P1 takes a door, P2 warps to P1. Cutscenes and boss intros warp P2 to P1.
- P2 can't softlock off-screen. If P2 goes off-camera for longer than N frames, they warp to P1.
- Zero softlocks across a scripted route: entrance → Marble Gallery → Outer Wall.

### M4: P2 Lite playable
- A human playtest of the opening areas through the first few bosses.
- Boots and plays on DuckStation and RetroArch (Beetle PSX + SwanStation), with no emulator-specific code.
- RetroArch netplay runs 30 minutes with no desync (automated lockstep check plus one human session).
- A patch file is generated for distribution.
