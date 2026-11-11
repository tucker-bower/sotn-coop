# M19 design: widescreen

**Status:** approved by Tucker (2026-10-27) as "spike, then stage by stage". Spiked 2026-11-11 (`coop-widescreen-spike`); this revision adds 21:9 and 32:9 (Tucker, 2026-11-11) and is up for approval again. Updates `M10-widescreen-spike.md` (2026-10-20), which recommended dropping it.

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
  - The camera keeps the player at a fixed screen x (a variable, 128) and clamps to the room with a constant 256. Until that changes, all the extra view is to the player's right.
  - Rooms narrower than the view show what's past their edge (the entrance's gate room).

## What's left
| Part | How | Size |
|---|---|---|
| Camera | Player's screen x = width / 2; the 256 clamps = width (two immediates, as the tile loops) | Small |
| Rooms narrower than the view | Black bars past the room's edges, the room centred | Medium |
| Tile pool | `RenderTilemap`'s sprites from a pool in the module's memory when the view is wider than 16:9 | Medium |
| **Enemies at the edges** | Stage code checks "on screen" against 256 (about 183 checks in 93 stage files), and the spawner's window is `scroll + 320`. Widen the shared helpers first, then fix stage by stage what's left, found by an automatic check | **Large: the long tail** |
| Screen copies | Effects that read the framebuffer (room fades, Richter's and Maria's death dissolve) read the second bank in wide mode: the core's copy and read paths | Medium |
| HUD | Stays at the left | None |
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
