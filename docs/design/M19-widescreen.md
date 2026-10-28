# M19 design: widescreen

**Status:** proposal for Tucker's review (2026-10-27). Updates `M10-widescreen-spike.md` (2026-10-20), which recommended dropping it. Depends on M13's VRAM layout.

## Goal
True widescreen: a wider view of the castle (about 352 px, 16:9), not a stretch (D76). Optional, in Settings.

## What changed since the spike
The spike's blocker was VRAM: two 384-wide framebuffers need a 768×240 strip, and the PS1's 1 MB is full, so every stage's layout would have moved (3–6 weeks, high risk). M13 gives our SwanStation build more VRAM. The framebuffers move into the new space, and **every stage's layout stays where it is**. M13's spike lays out VRAM for both (the partner banks of M17 and these framebuffers).

## What's still needed
| What | Size |
|---|---|
| Framebuffers in the new VRAM: draw and display settings (DRA constants, size-neutral, D33), and the core's draw-area and display coordinates past line 511 | Small, after M13 |
| Display width (`DISP_STAGE_W`, 17 uses) | Small |
| The tilemap drawn wider (`RenderTilemap`, the 17-column loops) | Medium |
| **Enemies despawning and freezing at the screen edges:** stage code checks for "on screen" against a 256-wide view (about 183 checks in 93 stage files) | **Large: the long tail**, per stage, through our overlay patching |
| The spawner window (`scrollX + 320`) | Small |
| Rooms narrower than the view: black bars at the room's edges | Medium |
| Effects that copy the screen (room transitions, some spells) | Unknown until the spike |
| HUD: left-anchored | Small |
| Co-op: everyone in a shared room uses the same width (it changes what spawns) | Small: the host's setting |

## Options
| Option | Verdict |
|---|---|
| **A. Spike, then stage by stage (recommended)** | ✅ A 1–2 window spike: the entrance and three stages at 352, count the edge problems and check the screen-copy effects. Then fix stage by stage, shipping widescreen as "experimental" per stage that passes |
| B. All stages at once | ❌ A big-bang change with bugs anywhere |
| C. Side bars with co-op information (the spike's fallback) | Kept as the fallback if the spike says the tail is too long |

## Acceptance criteria
1. The spike: framebuffers in the new VRAM, the entrance at 352 wide with no visual errors, and the count of edge problems in three stages.
2. Per stage: no enemy despawns, freezes or pops in inside the wider view (an automatic check: entities alive and updating across the full view width), and no garbage at the edges (contact sheets reviewed).
3. The whole suite passes at 4:3 (widescreen off is unchanged).
4. Couch and online: a shared room plays the same at 16:9 in both games.

## Risks
- **The per-stage tail** (about 3–6 weeks of the old estimate was the relayout; what's left is this). It ships as experimental until every stage passes.
- **Speedruns and balance:** seeing farther makes the game easier. It's optional.

## Budget
About 8–14 usage windows: the spike 1–2, the engine parts 2–3, the stages 5–9.
