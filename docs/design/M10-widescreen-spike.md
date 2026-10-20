# Widescreen / expanded FOV: spike findings (for the M10 design)

**Status:** spike done 2026-10-20 (M7b part 4). No widescreen code was written. Input for the M10 design.

## Summary
- **The emulator's widescreen option does nothing for SOTN.** SwanStation's `GPU_WidescreenHack` with a 16:9 display gives a picture pixel-identical to normal in the entrance hall. The hack widens 3D (GTE) projection; SOTN draws its world as 2D sprites and tiles. All that's left is stretching, which is ruled out (D76).
- **True expanded FOV means changing the game.** The blocker is video memory, not the camera. It's a multi-week, high-risk job, and I recommend **not doing it**. A cheaper alternative is to use the 16:9 side bars for co-op information (a partner mini-map, the partner's status).

## Test A: SwanStation widescreen hack
`swanstation_GPU_WidescreenHack=true` with `swanstation_Display_AspectRatio=16:9`, on the `entrance` savestate, 30 frames later: the core still outputs 256×240, and `ImageChops.difference` against the normal run is empty. Script: the M7b session's `ws.py` (not kept; easy to recreate from the harness `Emu` options).

## Test B: what the game would need
| What | Where | Size of the change |
|---|---|---|
| **The two framebuffers.** Each is 256×240, side by side at VRAM x 0–511 (`SetDefDispEnv(..., DISP_STAGE_W, ...)`, `src/dra/42398.c`). At 384 wide they need x 0–767. | VRAM x 512+ holds the stage's texture pages, and y 240–511 under the framebuffers holds Alucard's sprites (the puppet uses 0x1C1,0x101). There's no free 768×240 strip. | **Blocker.** Every stage's VRAM layout (its graphics upload rects) would have to move: dozens of overlays, hundreds of hard-coded rects. |
| Display width | `DISP_STAGE_W` (256): 17 uses in DRA, plus the bo6 cutscene | Small. Constants are size-neutral (D33). |
| Tilemap drawing | `RenderTilemap` (`src/dra/4CE2C.c`) and its 17-column loops (`src/dra/8BEF8.c`: `i < 0x11`) | Medium: a replacement in COOP.BIN, called through a retargeted DRA call. |
| Enemy culling / despawn windows | `0x120` / `0x140` / `-0x20` / `-0x40` screen-space checks: 183 hits of `0x140` in 93 stage files (some false positives); `st_common.h` alone has the entity-near-screen test | Large: per stage overlay. Our stage-overlay patching (`overlay_table.c`) could reach them, but each is its own case. |
| Layout spawner window | `scrollX + 320` / `+ 288` (spawner, mirrored in `module/shared.c` `ResyncSpawner`) | Small. |
| Room edges | Rooms are multiples of 256 px wide. A 384 view of a one-screen room shows past its edge. | Medium: clamp or black out the edges per room. |
| HUD | Drawn at fixed screen positions (left-anchored) | Small. Leave it left-anchored, or offset it. |
| **Co-op** | Spawn windows change what exists, so both players must use the same width in a shared room | Forced setting per session. |

Estimate: the framebuffer/VRAM relayout alone is the riskiest single change the project would have made: it touches every stage, and graphics glitches can appear anywhere. Realistically 3–6 weeks of agent time with a long tail of per-room bugs. That's well beyond the month budget.

## Recommendation for M10
- **Drop true expanded FOV.** Show the game at 4:3 (sharp scaling, M7b).
- **If the AYN Thor's 16:9 top screen should feel used:** draw co-op information in the side bars. For example, the partner's mini-map position, HP and area name, from data we already have (presence). That's host-side drawing only: cheap, no game changes, no co-op risk.
