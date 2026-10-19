// Stage entities that read castle flags (generated: flag_gated.c, scripts/gen_flag_gated.py).
#ifndef FLAG_GATED_H
#define FLAG_GATED_H

#define FLAG_GATED_ANY 0xFFFF // indexes g_CastleFlags with an expression: any change counts

typedef struct {
    s16 stage; // STAGE_xxx; -1 ends the table
    u8 entityId;
    u8 nFlags;
    u16 flags[4];
} FlagGated;

extern const FlagGated g_FlagGated[];

#endif
