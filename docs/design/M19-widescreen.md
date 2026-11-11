# M19 design: widescreen

**Status:** approved by Tucker (2026-10-27) as "spike, then stage by stage"; 21:9 and 32:9 added (Tucker, 2026-11-11), with the questions below taken as recommended (D201). In progress on `coop-widescreen-spike`. Updates `M10-widescreen-spike.md` (2026-10-20), which recommended dropping it.

## Goal
A wider view of the castle, not a stretch (D76), optional: 16:9, and 21:9 or 32:9 for ultrawide screens. The game's pixels keep the shape they have at 4:3 (each a little wider than tall), so nothing looks squashed: the extra width is more castle.

| Aspect | View (px) | VRAM for two framebuffers |
|---|---|---|
| 4:3 (today) | 256 | 512 × 240 |
| 16:9 | 352 | 704 × 240 |
| 21:9 | 448 | 896 × 240 |
| 32:9 | 688 | 1376 × 240: more than one bank's 1024 columns |

## What the spike showed
- **The VRAM blocker is gone.** Our core (`patches/swanstation.patch`) takes a display width through a new GPU command (GP1 0x2F). While it's set, drawing, fills and the display in VRAM's top band go to the second bank, so the two wider framebuffers sit there and no stage texture moves. The game's GPU library is untouched: the module only widens the stage's two framebuffer rectangles each frame (`module/widescreen.c`).
- **The tilemap is two numbers:** `RenderTilemap`'s 17-column loops (foreground and background) are patched to the width.
- **Result:** the Alchemy Lab and Marble Gallery draw correctly at 352 and 448, with no garbage and every texture intact (contact sheet kept locally: ripped art). Menus and the title run as before; the core is at 256 whenever the game isn't in its stage layout.
- **Measured limits:**
  - The tile sprite pool is 640. The Alchemy Lab uses 500 at 4:3, 596 at 352, and hits 640 at 448, so tiles drop. Wide views need a tile pool of our own.
- **The camera stays the game's.** Changing it would touch room transitions and cutscenes, which assume the player's screen x is under 256. Instead the game keeps its 256-wide view, and the wider window is centred on it and slid to stay inside the room (centred on a room narrower than it). Everything moves by the slide through the drawing offset; the tilemap is drawn from the slide further left; the HUD and anything over it are drawn without the slide (an offset command in the ordering table, at the HUD's layer).
- **The tilemap is the module's** while the view is wide (`module/widescreen_tilemap.c`, the game's `RenderTilemap` with as many columns as the view needs), with a pool of 2,048 tiles per framebuffer: the game's holds 640, and the Alchemy Lab needs more than that at 448.

## What's left
| Part | How | Size |
|---|---|---|
| Camera, narrow rooms, HUD, tile pool | Done (above). A narrow room shows its background layers past its edges (the entrance's sky), not black | Done |
| **Enemies at the edges** | Shared windows done: every stage's `Update` (destroy and freeze bounds) and spawner (`UpdateRoomPosition`, `InitRoomEntities`) are widened by the view's extra width at each stage load (`module/widescreen_stage.c`). `harness/widescreen_edges.py` walks each of the 37 debug starts: at 448, events in the extra width went from 86 pop-ins and 27 vanishes to 49 and 18, most of what's left in boss fights (their projectiles and particles near the edge) and a few enemies' own "on screen" checks (about 183 in 93 stage files). Those are the stage-by-stage tail | **Large: the long tail** |
| Screen copies | Effects that read the framebuffer (room fades, Richter's and Maria's death dissolve) read the second bank in wide mode: the core's copy and read paths | Medium |
| 32:9 | Two 688 framebuffers need more than one bank: a third bank in the core, and the partner's textures move there | Medium |
| The app | Width setting (4:3, 16:9, 21:9, 32:9) in Your settings; the window and fullscreen fit the wider picture; Windows and Android cores rebuilt | Medium |
| Co-op | See question 3 | Small |

## Options
| Option | Verdict |
|---|---|
| **A. 16:9 and 21:9 first, stage by stage; 32:9 after (recommended)** | ✅ 16:9 and 21:9 share one framebuffer layout. Each stage ships as "experimental" until it passes the edge check. 32:9 follows once the third bank is in |
| B. All three widths at once | ❌ The third bank and the partner's move come first, holding up 16:9 |
| C. 16:9 only | Smallest, but ultrawide players get nothing |

## Questions for Tucker
1. Widths 352 (16:9), 448 (21:9), 688 (32:9), keeping the game's pixel shape. Or square pixels (427 for 16:9), which look slightly thinner than at 4:3?
2. Option A (16:9 and 21:9 first)?
3. Co-op, when players pick different widths: each sees their own width. Enemies wake up for the widest view in the shared room, so nobody sees one frozen at the edge. Agreed?
4. Rooms narrower than the view: black bars, as above?

## Acceptance criteria
1. Off (the default), the game is unchanged: the gate passes, and the core outputs 256 wide.
2. At each width, in every stage that's marked done: no enemy despawns, freezes or pops in inside the view (an automatic check: every entity in view keeps updating), and no garbage at the edges (contact sheets per stage).
3. The camera keeps the player centred, and stops at a room's edge; a room narrower than the view is centred between black bars.
4. Couch and online: a shared room plays the same in both games whatever widths the players picked.
5. Width is a setting, saved per player, on Windows, Android and Linux; the window fits the picture without stretching it.

## Risks
- **The per-stage tail.** Mitigation: the automatic edge check names the entity and stage, and stages ship as "experimental" one by one.
- **Effects that read the screen** may show stale pictures in wide mode until the core's read paths follow the redirect.
- **Seeing farther makes the game easier.** It's optional.

## Budget
About 8–12 usage windows: camera, rooms, tile pool and the app 2–3; enemies at the edges stage by stage 4–7; 32:9 and the third bank 1–2.
