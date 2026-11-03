# Netplay suite: the 0.13 playtest, reproduced

**Status:** in progress (2026-11-01). Tests: `harness/session_netplay.py`.

## Why
The 2026-11-01 online session on 0.13 froze, got stuck and slowed down, while the suite passed. The tests start in a room by savestate, stay in one room for network checks, and only check what they were written to check. These tests play the game's own route over a connection like the playtest's (`link/netsim.py` profile `playtest`: 60–120 ms, with hitches), and they measure what players feel.

## What the playtest's reports showed
- **The freeze was a crash in Alucard's game.** His afterimage slot had lost its primitives while his afterimages stayed on, so `func_801093C4` took a DR_ENV pointer from a primitive that was now another entity's, and `SetDrawEnv` wrote through it each frame. Those pointers were colours (0x101, 0x201...), so the packets landed at 0x104, 0x204... and at low addresses, and they overwrote the kernel's data and the exception vector. The CPU then looped at 0x80000080.
- **What took his primitives is not proven.** The slot's flags are what `Drop()` leaves. `Swap()` skipped slots 1-3 whenever both ids were 0, and slot 1's id is a counter, against what its comment says: fixed. Forcing that counter at every value did not reproduce the loss, so `KeepAfterimages()` also repairs the state, and counts it in `g_CoopAfterimagesRepaired`.
- **Stuck at the gate:** D153.
- **The slowdown:** the body's CPU cost, not the network: D154. No room on the route needs over 420 kbit/s.

- **A second hang, found by `harness/realtime.py`:** entities keep pointers into their primitive chain, in the authority's numbering. A guest's copy that ran after a hand-over walked another entity's chain, and an Axe Knight's walk never ended. They now travel as places in the chain (`PrimPointersOut`/`In`, `module/shared.c`). The Marble Gallery route stopped at the same moment every run, and no longer does. This may also be what took Alucard's afterimages, and the corrupted graphics: not shown yet. The lockstep runner never reproduced it, so `harness/realtime.py` is the check for it.
- **Not bugs:** the Outer Wall route's room loop is the bot riding the lift (solo too). Both players down at a black screen is a test without a joint save. Richter's dark HUD on routes that switch character in play is known (only tests do that).

## Tests
- `CrashGuard` (`harness/session.py`): every two-game test fails if a game's exception vector changes.
- `netplay_gate_*`: both players run the forest and pass the castle door, keeping 95% of their game frames in every room, under 1.5 Mbit/s.
- `netplay_lost_afterimages_repaired`: the crash's state, made on purpose.
- `netplay_comings_and_goings_*`: the body made and dropped 30 times.

## Left
- The real cause of the lost primitives, if `g_CoopAfterimagesRepaired` ever rises. It was 0 in all 20 reports from the 0.14 playtest.
- Buttons and lifts driven by a guest (#98).
