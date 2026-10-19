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
} OverlayInfo;

extern const OverlayInfo g_Overlays[];
const OverlayInfo* FindOverlay(s32 stage);

#endif
