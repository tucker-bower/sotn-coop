# M19 design: widescreen

**Status:** approved by Tucker (2026-10-27) as "spike, then stage by stage"; 21:9 and 32:9 added (Tucker, 2026-11-11), with the questions below taken as recommended (D201). In progress on `coop-widescreen-spike`. Updates `M10-widescreen-spike.md` (2026-10-20), which recommended dropping it.

## Goal
A wider view of the castle, not a stretch (D76), optional and off by default: 16:9 and 21:9, mostly for players filling a monitor in online co-op. The game's pixels keep the shape they have at 4:3 (1.25 times as wide as tall), and only the 207 lines the game draws its stage in are shown (it letterboxes itself), so the picture fills the screen exactly.

| Shape | View (px) | Shown |
|---|---|---|
| 4:3 (the default) | 256 | the game's whole 240 lines, as ever |
| 16:9 | 294 | 294 × 207: 1.775, a 1920×1080 screen |
| 21:9 | 392 | 392 × 207: 2.37, a 2560×1080 screen |
| 32:9 | later | needs a third VRAM bank |

## Not doing
Zoom of any kind (fitting the view to each room, a camera that zooms in and out): it would rescale the pixel art. Tucker, 2026-11-11 (D201).

## How it works
- **Framebuffers in the second bank.** Our core (`patches/swanstation.patch`) takes a display width (GP1 0x2F) and the lines to show (GP1 0x2E). While the width is set, drawing, fills, screen copies and read-backs in the area of the two wide framebuffers (the top band, left of twice the width) go to VRAM's second bank, so no stage texture moves. A copy of a whole wide screen gets its middle 256 (the game copying "the screen" for the Game Over). Turning it off copies the middle of the last picture into the game's own framebuffers.
- **The game's camera is unchanged** (D201). It keeps its 256-wide view; the wide window is centred on it and slides to stay inside the room, so entering a room you see what's ahead, and it follows once you pass the middle. A room narrower than the view sits in the middle with its background around it. Everything moves by the slide through the drawing offset (`module/widescreen.c`).
- **Screen things stay on the screen:** offset commands in the ordering table draw the HUD (layer 0x1EE) without the slide, and dialogue, message boxes and the fade (0x1F1 up) centred on the view. The fade's tiles are made as wide as the view.
- **The tilemap is the module's** while wide (`module/widescreen_tilemap.c`: the game's `RenderTilemap` with as many columns as needed, from a pool of 2,048 tiles per framebuffer; the game's holds 640).
- **Entity windows:** each stage's `Update` and spawner bounds are widened by the extra width at each stage load (`module/widescreen_stage.c`), for the wider of the two players' views in co-op. Most stages compile Update's windows unsigned (`addiu 64; sltiu 385`), others signed (`slti 321` with its `-64`): both are widened. Missing the unsigned form left the spawner wider than Update, so a red door spawned in the extra width was destroyed the next frame and never came back (#260; `widescreen_stage_windows_every_stage`, `widescreen_red_door_comes_back`). Each player's shape travels in presence (`aggroSwitches`' top bits).
- **Only in normal play:** the title, menus, the map's own screens and the Game Over are drawn as the game draws them.
- **The app:** "Screen shape" in Options and Your settings (two bits of the player's options), each picture fitted to its shape, and fullscreen gives the games the whole screen (the status line over them for a few seconds when it changes).

## Not done
- **32:9** needs a third VRAM bank (two 688-wide framebuffers don't fit in one), and the partner's textures moving there.
- **The per-stage tail:** `harness/widescreen_edges.py` over the 37 debug starts, now over all the stage's slots (64-255; it saw only 64-191 before #260) and with both window forms widened: at 16:9, 7 pop-ins and 3 vanishes in the extra width; at 21:9, 77 and 77 (2026-11-12), most in boss fights (their projectiles and particles near the edge). Some rooms park things just off the 4:3 screen that a wide view shows (a red block in the Castle Keep's scene at 21:9).
- **The Game Over's picture** is partly garbled in wide mode: it copies a frame the game draws after the state changes.
- **Summon Spirit's** ripple copies its patch of screen from slightly the wrong place while the window is slid.

## Acceptance criteria
1. Off (the default), the game is unchanged: the gate passes with the new core, and the core shows 256 × 240. ✅
2. Each shape shows its width and the 207 lines; the pause menu as the game draws it; off again in play: `widescreen_shape_option`. ✅
3. The fade covers the whole view: `widescreen_fade`. ✅
4. Co-op: each player's own shape, and enemies alive across the wider view: `widescreen_partner_wider`. ✅
5. Edges: measured, not zero (above). Shipped as experimental.
6. Windows and Android cores built with the patch. ✅
