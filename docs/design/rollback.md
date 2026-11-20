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

## Recommendation
B, then C. Measure after each with `netplay_partner_lag` and a new drift measurement; keep A as an option only for two-player castles if C isn't enough.

## Acceptance criteria
1. On the playtest link (`netsim` "playtest": 30 ms, jitter, loss, spikes), a guest's mirrored enemies are within 8 px of the authority's (median) and never jump more than 16 px in a frame outside a real teleport; today's numbers measured first (`shared_room_drift_on_lag`).
2. On a LAN link, nothing changes: same positions as today, frame for frame.
3. C: the partner's body is shown within 1 frame of the partner's own timing on the playtest link (median), and a misprediction never moves it more than 8 px in a frame (`netplay_partner_lag`, extended).
4. No extra missed frames: `crowd_four_in_the_hall` and `mixed_soak_10min` stay within their budgets.
5. The gate passes.

## Risks
- Extrapolating an enemy that turns or stops overshoots, then blends back. Bosses with big sudden moves (Olrox's dash) may look worse, so a per-entity opt-out list may be needed.
- A guest-side position that differs from the authority's could make a guest's hit look like a miss on the guest's screen (the authority decides). The blend keeps them within a few pixels.
- C hides the partner's lag, so "where the partner really is" and "where you see them" differ by up to half a round trip: PvP keeps the victim's verdict (D132), unchanged.

## Budget
B: 3-4 days with measurements. C: about a week.
