# Rollback and lag hiding (#86, #292)

## Goal
Online play should look and feel like one game on a normal connection (30-60 ms each way, some jitter). Players have noticed two things: desyncs in the trailer (Reddit, 2026-11-19), and enemies drifting apart on lag, with Richter "moon jumping" (#292, 1.1.1 playtest).

## Where the lag shows today (measured, D170 and `netplay_partner_lag`)
| What | Who runs it | What the other game sees |
|---|---|---|
| **Your own player** | your game, at once | nothing late |
| **The partner's body** | your game, from the partner's buttons as they arrive (M13) | the partner's moves late by half a round trip plus the jitter buffer (median 133 ms on the playtest link), pulled back to the presence past 48 px |
| **A shared room's enemies** | the room's authority; guests mirror its snapshots (M4) | late by the same amount; on a spike they jump, and a guest's hit lands on where the enemy was |

## Options
| Option | Idea | Cost | Verdict |
|---|---|---|---|
| **A. Partner-body rollback** | Run the partner's body on predicted buttons (the last ones held), keep 8 frames of its state, and when the real buttons arrive and differ, rewind and re-run | RAM: 8 copies of a body (15 KB each) for each partner = 120 KB, and we have about 130 KB free (M21). CPU: up to 8 body updates in one frame (45-60 scanlines each, so 360+): over the frame on a correction | ❌ Doesn't fit for 3-4 players; even for two it costs a frame on every misprediction |
| **B. Guests extrapolate the room (recommended first)** | A guest moves each mirrored enemy on by its own velocity for the frames the snapshot is old, and blends to the next snapshot instead of jumping. Hits a guest lands are already decided in the authority's game (M4), so nothing becomes unfair | Small: one pass over the mirrored entities a frame; no extra RAM | ✅ Fixes what #292 reports (drift, jumps), costs nothing to two-player castles on a LAN |
| **C. Partner-body prediction, no rewind** | Run the body ahead on the last buttons; when real buttons differ, correct its position smoothly over a few frames instead of rewinding | One body update a frame, as now | ✅ Second step: the partner looks on time; a wrong guess shows as a slight correction, not a jump |
| D. Whole-game rollback (GGPO) | Both games in lockstep, rewinding with core savestates | Needs the two games in lockstep, which co-op isn't by design: each game runs its own rooms, and timing lives in the host (AGENTS.md) | ❌ A different architecture |

## Decision (Tucker, 2026-11-20)
A and B. A's two costs went to the emulator (D226): our SwanStation gives 16 MB, so the snapshots fit for three partners (4.3 MB), and a copy engine takes each snapshot in about a scanline instead of twenty. Re-running is capped at 100 scanlines a frame; a body that couldn't catch up shows a frame or two short and catches up after. C isn't needed with A.

How A works (`module/partner.c` RollFrame, `link/rollback.py`): the host writes each partner's buttons by frame as they come (`CoopRollIn`, ahead of the playout), and the frame the partner is at now (the playout's fastest path plus half the round trip, at most 12 frames past the newest buttons). Before each frame the body runs, its state is kept: the body, its statics, its primitives. When buttons come that differ from a guess, the body goes back to before that frame and runs again, those frames' sounds dropped. The presence's pull works on where the body was at the presence's frame, and moves the kept frames after it too.

Inputs and hits (D227): the partner's host sends each frame's buttons and its HP after the frame (`INPT`, the last 8 frames each time), so a hit in its own game lands on the body at that frame. Guesses are the partner's suggestions (`SUGG`, Slippi's input suggestions: its buttons as its app reads them, and as they change while it waits for the next frame), else the last buttons held. A frame run again plays only the sounds its first run didn't. An Alucard body runs its partner's own weapons, so its swings roll back with it (D228, #343); Richter's and Maria's are still sent from their games, placed against where they stood at their own frame.

How B works (`module/shared.c` Extrapolate): with each snapshot the host gives its frame and the authority's frame now. A copy is moved on by what it moved between its last two snapshots (so a many-part enemy's parts move together) for the snapshot's age, and on through a gap of up to 8 frames; a new snapshot that puts it somewhere else is eased in over a few frames (a jump of more than 64 px is a real one).

## Acceptance criteria
1. B: on the playtest link (`netsim` "playtest": 30 ms, jitter, loss, spikes), a guest's mirrored enemies are within 8 px of the authority's (median), nearer than without, and never jump more than 16 px in a frame.
2. On a LAN link, nothing changes: same positions as today, frame for frame.
3. A: the partner's body is shown within 2 frames of the partner's own timing on the playtest link (best-fit delay), and a misprediction never moves it more than 24 px in a frame.
4. No extra missed frames: `crowd_four_in_the_hall` and `mixed_soak_10min` stay within their budgets, and A misses no more frames online than on a LAN.
5. The gate passes.

## Risks
- Extrapolating an enemy that turns or stops overshoots, then blends back. Bosses with big sudden moves (Olrox's dash) may look worse, so a per-entity opt-out list may be needed.
- A guest-side position that differs from the authority's could make a guest's hit look like a miss on the guest's screen (the authority decides). The blend keeps them within a few pixels.
- C hides the partner's lag, so "where the partner really is" and "where you see them" differ by up to half a round trip: PvP keeps the victim's verdict (D132), unchanged.

## Tests
`netplay_partner_on_time_alucard_and_richter` (A: the body's delay against Richter's own game, with and without; no step over 24 px; missed frames), `netplay_room_enemies_steady_on_lag` (B: copies against the authority's enemies, with and without; no jump over 16 px).
