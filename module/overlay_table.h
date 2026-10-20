// Per-overlay facts (generated: overlay_table.c, scripts/gen_overlay_table.py).
#ifndef OVERLAY_TABLE_H
#define OVERLAY_TABLE_H

#define OVL_SIDE_TO_PLAYER 0
#define OVL_DISTANCE_X 1
#define OVL_DISTANCE_Y 2

typedef struct {
    u32 addr;      // where the helper is, once the overlay is loaded
    u32 firstWord; // its first instruction, to check before patching
} OverlayHelper;

typedef struct {
    s32 stage; // STAGE_xxx; -1 ends the table
    u32 bssStart;
    u32 bssSize;
    OverlayHelper helpers[3];
    u32 decor[16]; // scenery update functions (0 ends the list): guest runs them itself
    u32 layout[4]; // layout spawner cursors: horizontal, vertical, and their directions (0 = none)
    u32 bottomText; // BottomCornerText(u8* str, u8 leftAlign): the item-pickup text box, or 0
    OverlayHelper solid; // GetPlayerCollisionWith: patched to the module's copy (solid.c)
} OverlayInfo;

#define LAYOUT_H 0
#define LAYOUT_V 1
#define LAYOUT_POS_H 2
#define LAYOUT_POS_V 3

extern const OverlayInfo g_Overlays[];
const OverlayInfo* FindOverlay(s32 stage);

#endif
