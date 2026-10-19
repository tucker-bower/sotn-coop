// The game <-> host mailbox (design/M1-link-presence.md, part 2). The host reads and writes it
// only between frames, while the emulator is paused, so neither side needs locking.
// The Python side mirrors this layout in link/mailbox.py: keep the two in sync and bump
// COOP_LINK_VERSION on any change.
#ifndef LINK_H
#define LINK_H

#define COOP_LINK_VERSION 6

#define PRESENCE_IN_PLAY 1 // in a stage, in control (not title, loading, or game over)
#define PRESENCE_SPRITE 2  // the body sprite is drawable this frame
#define PRESENCE_PAUSED 4  // in the menu or on the map (design/M3: freezes a shared room)
#define PRESENCE_BUSY 8    // loading, in a cutscene, or arriving: can't be teleported to
#define PRESENCE_DEAD 16   // dying, or waiting for a respawn or a joint-save reload

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
    /* 0x1C */ u16 roomId;   // RoomHeader offset in the stage's room table (Arrive needs it)
    /* 0x1E */ s16 groundX;  // where the player last stood on the ground, in room pixels
    /* 0x20 */ s16 groundY;
    /* 0x22 */ u16 roomFrames; // frames since entering this room (the earlier one is authority)
    /* 0x24 */ s16 scrollX;    // camera position in the room (shared rooms need cameras close)
    /* 0x26 */ s16 scrollY;
    /* 0x28 */ u16 role;       // ROLE_* (design/M4)
    /* 0x2A */ u16 pad;
} CoopPresence; // size = 0x2C

#define ROLE_NONE 0      // my own world
#define ROLE_AUTHORITY 1 // a shared room: I run its enemies
#define ROLE_GUEST 2     // a shared room: I show the authority's enemies

// Shared-progression events (design/M2-shared-progression.md). a/b by type:
#define EV_FLAG 1  // a: g_CastleFlags index, b: value to merge
#define EV_MAP 2   // a: g_CastleMap index, b: newly set bits
#define EV_ITEM 3  // a: item id, b: EquipKind (AddToInventory)
#define EV_GRANT 4 // a: func_800FE044 type (0x8000/0x4000/0x2000), b: amount / relic id
#define EV_GOLD 5  // b: gold delta (s32)
#define EV_HIT 6   // a: slot | entityId << 8, b: damage (s16) | hitFlags << 16 | dead << 24
#define EV_HIT2 7  // a: slot, b: nFramesInvincibility | stunFrames << 8 | hitEffect << 16

typedef struct {
    u8 type;
    u8 pad;
    u16 a;
    u32 b;
} CoopEvent; // size = 8

#define COOP_RING_SIZE 256 // power of two
typedef struct {
    u32 head;              // count written, by the writer
    u32 tail;              // count read, by the reader
    CoopEvent ev[COOP_RING_SIZE];
} CoopRing; // size = 0x808

// Commands from the host (design/M3-teleport-respawn-save.md).
#define CMD_ARRIVE 1    // go to stage / roomId / x, y (tests, and the launcher)
#define CMD_LOAD_SAVE 2 // apply saveIn and load it (resume, or both players dead)
#define CMD_SAVE_NOW 3  // save to my memory card block roomId (and saveOut), resuming in stage / x=roomX, y=roomY
#define CMD_GAME_OVER 4 // both dead and no joint save: let the Game Over happen

typedef struct {
    u32 seq; // the host bumps it to issue a command; the game copies it to cmdDone when done
    u16 type;
    u16 stage;
    u16 roomId;
    s16 x;
    s16 y;
    u16 pad;
} CoopCommand; // size = 0x10

#define SAVE_DATA_SIZE 0x11CC // sizeof(SaveData)
#define SNAP_MAX 0xF000      // a shared-room snapshot, at most (one UDP datagram)

typedef struct {
    /* 0x00 */ u32 magic; // COOP_MAGIC
    /* 0x04 */ u32 version;
    /* 0x08 */ u32 heartbeat;      // frames since install
    /* 0x0C */ CoopPresence self;  // game writes, every frame
    /* 0x38 */ CoopPresence partner; // host writes
    /* 0x64 */ u32 partnerAge;     // game increments every frame; host zeroes it with each write
    /* 0x68 */ CoopRing out;       // game writes, host reads
    /* 0x870 */ CoopRing in;       // host writes, game reads
    /* 0x1078 */ u32 dropped;      // events lost to a full out ring (should stay 0)
    /* 0x107C */ CoopCommand cmd;  // host writes
    /* 0x108C */ u32 cmdDone;      // game writes: seq of the last command it finished
    /* 0x1090 */ u32 saveSeq;      // game bumps it each time saveOut holds a new save
    /* 0x1094 */ u8 saveOut[SAVE_DATA_SIZE]; // game writes: this game's latest save
    /* 0x2260 */ u8 saveIn[SAVE_DATA_SIZE];  // host writes: the save CMD_LOAD_SAVE applies
    /* 0x342C */ u32 saveBlock;  // game writes: memory card block of its latest save
    /* 0x3430 */ u32 cardResult; // game writes: last CMD_SAVE_NOW card write: 6 = ok, 7-11 = card error
    /* 0x3434 */ u32 rank;       // host writes: 0 or 1, breaks authority ties (design/M4)
    /* 0x3438 */ u32 snapOutSeq; // game writes (authority): a new room snapshot is in snapOut
    /* 0x343C */ u32 snapOutSize;
    /* 0x3440 */ u8 snapOut[SNAP_MAX];
    /* 0x12440 */ u32 snapInSeq; // host writes (guest): the authority's latest snapshot
    /* 0x12444 */ u32 snapInSize;
    /* 0x12448 */ u8 snapIn[SNAP_MAX];
} CoopLink; // size = 0x21448

extern CoopLink g_CoopLink;

#endif
