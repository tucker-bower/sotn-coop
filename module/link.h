// The game <-> host mailbox (design/M1-link-presence.md, part 2). The host reads and writes it
// only between frames, while the emulator is paused, so neither side needs locking.
// The Python side mirrors this layout in link/mailbox.py: keep the two in sync and bump
// COOP_LINK_VERSION on any change.
#ifndef LINK_H
#define LINK_H

#define COOP_LINK_VERSION 2

#define PRESENCE_IN_PLAY 1 // in a stage, in control (not title, loading, or game over)
#define PRESENCE_SPRITE 2  // the body sprite is drawable this frame

typedef struct {
    /* 0x00 */ u8 flags;     // PRESENCE_*
    /* 0x01 */ u8 character; // g_PlayableCharacter
    /* 0x02 */ u8 flipX;     // effective flip (bit 1), as RenderEntities computes it
    /* 0x03 */ u8 blendMode;
    /* 0x04 */ u16 stage; // g_StageId
    /* 0x06 */ u16 zPriority;
    /* 0x08 */ s16 roomLeft; // g_Tilemap.left/top: the room's map cell
    /* 0x0A */ s16 roomTop;
    /* 0x0C */ s16 x; // position in the room, in pixels
    /* 0x0E */ s16 y;
    /* 0x10 */ s16 animSet;
    /* 0x12 */ u16 animCurFrame;
    /* 0x14 */ u16 palette;
    /* 0x16 */ u16 drawFlags;
    /* 0x18 */ u32 frame; // sender's g_Timer when captured
} CoopPresence; // size = 0x1C

typedef struct {
    /* 0x00 */ u32 magic; // COOP_MAGIC
    /* 0x04 */ u32 version;
    /* 0x08 */ u32 heartbeat;      // frames since install
    /* 0x0C */ CoopPresence self;  // game writes, every frame
    /* 0x28 */ CoopPresence partner; // host writes
    /* 0x44 */ u32 partnerAge;     // game increments every frame; host zeroes it with each write
} CoopLink; // size = 0x48

extern CoopLink g_CoopLink;

#endif
