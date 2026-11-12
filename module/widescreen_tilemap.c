// The tilemap drawn wide (design/M19-widescreen.md): RenderTilemap (src/dra/4CE2C.c), as it is,
// but with as many columns as the view needs, and its 16x16 sprites from a pool of the module's
// own: the game's holds 640, and a 448-wide view of the Alchemy Lab needs more. Only used while the
// view is wide (widescreen.c); otherwise the game's own runs.
#define COOP_MODULE
#include <game.h>
#include "link.h"

#define WIDE_TILES 2048 // per framebuffer: a 448-wide view of the busiest rooms with room to spare

static SPRT_16 s_Tiles[2][WIDE_TILES];

typedef struct {
    u16 x, y, flags, clutAlt, order, isSemiTrans, tpage, roomTileWidth, roomTileHeight;
    u16* tiles;
    u8 *page, *gfx, *clut;
    OT_TYPE* ot;
    SPRT_16* sp16;
    DR_MODE* dr;
    RECT rect;
} Renderer;

static void DrawModes(Renderer* r) {
    s32 i, tpage;

    for (i = 0; i < 24; i++) {
        if (g_GpuUsage.drawModes >= MAX_DRAW_MODES) {
            break;
        }
        tpage = i + 8 + r->tpage;
        if (r->flags & LAYER_TPAGE_ALT) {
            tpage += 0x80;
        }
        SetDrawMode(r->dr, 0, 0, tpage, &r->rect);
        AddPrim(&r->ot[i + r->order], r->dr);
        r->dr++;
        g_GpuUsage.drawModes++;
    }
}

// One layer's tiles: the room's foreground (layout fg, wrap false) or a background layer.
static void Layer(Renderer* r, SPRT_16* sp16, u16* layout, s32 scrollX, s32 scrollY, bool wrap, s32 columns,
                  SPRT_16* end) {
    s32 subX = scrollX & 0xF, startTx = scrollX >> 4, subY = scrollY & 0xF, startTy = scrollY >> 4;
    s32 i, j, tx, ty, row, x0, y0, page;
    u16 tile, clut;

    if (wrap) {
        startTx &= TILE_SIZE - 1;
        startTy &= TILE_SIZE - 1;
    }
    r->tpage = 0;
    r->isSemiTrans = false;
    if (r->flags & LAYER_SEMI_TRANS) {
        r->isSemiTrans = true;
        r->tpage = r->flags & LAYER_TPAGE_ID;
    }
    y0 = r->y - subY;
    for (i = 0; i < N_VERTI_TILES; i++, y0 += TILE_SIZE) {
        x0 = r->x - subX;
        ty = startTy + i;
        if (wrap) {
            ty &= TILE_SIZE - 1;
        }
        if (ty < 0) {
            continue;
        }
        if (ty >= r->roomTileHeight) {
            break;
        }
        row = ty * r->roomTileWidth;
        r->tiles = &layout[startTx + row];
        for (j = 0, tx = startTx; j < columns; j++, x0 += TILE_SIZE, tx++) {
            if (wrap) {
                tx &= 0xF;
                r->tiles = &layout[tx + row];
            }
            if (tx < 0) {
                r->tiles++;
                continue;
            }
            if (tx >= r->roomTileWidth) {
                break;
            }
            tile = *r->tiles++;
            if (tile == 0) {
                continue;
            }
            page = r->page[tile];
            clut = g_ClutIds[r->clut[tile] + (r->clutAlt ? 0x100 : 0)];
            if (r->sp16 >= end) {
                continue;
            }
            *sp16 = (SPRT_16){0};
            setSprt16(sp16);
            sp16->clut = clut;
            sp16->x0 = x0;
            sp16->y0 = y0;
            sp16->u0 = r->gfx[tile] << 4;
            sp16->v0 = r->gfx[tile] & 0xF0;
            setSemiTrans(sp16, r->isSemiTrans);
            setShadeTex(sp16, true);
            *r->sp16 = *sp16;
            addPrim(r->order + page + r->ot, r->sp16);
            r->sp16++;
        }
    }
    DrawModes(r);
}

void WideTilemap(s32 columns) {
    SPRT_16 one, *end;
    Renderer rr, *r = &rr;
    Tilemap* t = &g_Tilemap;
    BgLayer* bg;
    s32 l;

    r->ot = g_CurrentBuffer->ot;
    r->sp16 = s_Tiles[g_CurrentBuffer == &g_GpuBuffers[1]];
    end = r->sp16 + WIDE_TILES;
    r->dr = &g_CurrentBuffer->drawModes[g_GpuUsage.drawModes];
    r->rect.x = r->rect.y = 0;
    r->rect.w = r->rect.h = 255;
    r->x = g_cameraOffsetX;
    r->y = g_cameraOffsetY;
    if (t->hideTimer > 0) {
        t->hideTimer--;
    } else {
        r->flags = t->flags;
        if (r->flags & LAYER_SHOW) {
            r->clutAlt = r->flags & LAYER_CLUT_ALT;
            r->page = t->tileDef->gfxPage;
            r->gfx = t->tileDef->gfxIndex;
            r->clut = t->tileDef->clut;
            r->order = t->order;
            r->roomTileWidth = t->hSize * 16;
            r->roomTileHeight = t->vSize * 16;
            Layer(r, &one, t->fg, t->scrollX.i.hi, t->scrollY.i.hi, false, columns, end);
        }
    }
    for (l = 0, bg = g_BgLayers; l < MAX_BG_LAYER_COUNT; l++, bg++) {
        if (bg->hideTimer > 0) {
            bg->hideTimer--;
            continue;
        }
        r->flags = bg->flags;
        if (!(r->flags & LAYER_SHOW)) {
            continue;
        }
        r->clutAlt = r->flags & LAYER_CLUT_ALT;
        r->page = bg->tileDef->gfxPage;
        r->gfx = bg->tileDef->gfxIndex;
        r->clut = bg->tileDef->clut;
        r->order = bg->order;
        r->roomTileWidth = bg->w * 16;
        r->roomTileHeight = bg->h * 16;
        Layer(r, &one, bg->layout, bg->scrollX.i.hi, bg->scrollY.i.hi, (r->flags & LAYER_WRAP_BG) != 0, columns,
              end);
    }
}
