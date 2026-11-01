// The game <-> host mailbox (design/M1-link-presence.md, part 2). The host reads and writes it
// only between frames, while the emulator is paused, so neither side needs locking.
// The Python side mirrors this layout in link/mailbox.py: keep the two in sync and bump
// COOP_LINK_VERSION on any change.
#ifndef LINK_H
#define LINK_H

#define COOP_LINK_VERSION 12

#define PRESENCE_IN_PLAY 1 // in a stage, in control (not title, loading, or game over)
#define PRESENCE_SPRITE 2  // the body sprite is drawable this frame
#define PRESENCE_PAUSED 4  // in the menu or on the map (design/M3: freezes a shared room)
#define PRESENCE_BUSY 8    // loading, in a cutscene, or arriving: can't be teleported to
#define PRESENCE_DEAD 16   // dying, or waiting for a respawn or a joint-save reload
#define PRESENCE_BOSS 32   // a living boss is in this room (design/M5)
#define PRESENCE_CUTSCENE 64 // a cutscene has control (design/M5)
#define PRESENCE_CS_FOLLOWER 128 // in a cutscene because the partner's pulled it in: never pulled into

// CoopPresence.flipX's bit 7 (it uses bit 1): this player just came in by teleport (a revive), so
// the partner's copy of it starts with its character's teleport-in (M13 step 4).
#define FLIP_TELEPORT_IN 0x80
// Bit 6: this player's one-button moves are on (OPT_SHORTCUTS): the partner's copy of it reads its
// buttons the same way (Richter's and Maria's moves check the option in their own code).
#define FLIP_SHORTCUTS 0x40

// One sprite of a player's own entities (sprites.c, M12): the partner's attacks drawn here.
#define COOP_SPRITES 24
// ...and their primitives (most attacks draw with them: Alucard's subweapons, Richter's whip):
// a Primitive without its next pointer, positions in the room.
#define COOP_PRIMS 32
#define COOP_PRIM_SIZE 0x30
#define PRIM_TAG (0x2B - 4)  // its p3 (a pad byte): FAMILIAR_TAG for a familiar's (M13 step 4)
#define FAMILIAR_TAG 0xFA
#define FAMILIAR_IDS 0xD0    // the familiars' entity ids, 0xD0-0xDF
typedef struct {
    /* 0x00 */ s16 animSet;
    /* 0x02 */ u16 animCurFrame;
    /* 0x04 */ s16 x; // in the room, in pixels
    /* 0x06 */ s16 y;
    /* 0x08 */ u16 palette;
    /* 0x0A */ u8 facingLeft;
    /* 0x0B */ u8 blendMode;
    /* 0x0C */ u16 zPriority;
    /* 0x0E */ u16 drawFlags;
    /* 0x10 */ u16 unk5A;
    /* 0x12 */ u16 weapon; // a hand weapon's sprite: WEAPON_SPRITE | hand (weapons.c), else 0
} CoopSprite; // size = 0x14
#define WEAPON_SPRITE 0x100 // CoopSprite.weapon: animSet is its bank (0x10-0x13), palette its own

// A player's attack that can hurt (M15, pvp.c): its hitbox in the room, as hit detection reads it.
#define COOP_HITS 16
typedef struct {
    /* 0x00 */ s16 x; // the hitbox's centre, in the room, in pixels
    /* 0x02 */ s16 y;
    /* 0x04 */ u8 w;  // half its width and height (Entity.hitboxWidth/Height)
    /* 0x05 */ u8 h;
    /* 0x06 */ u8 hitboxState;
    /* 0x07 */ u8 facingLeft;
    /* 0x08 */ s16 attack;
    /* 0x0A */ u16 element;
} CoopHit; // size = 0xC

// A player's hand weapons, for the partner to draw their swings (weapons.c, M12 note 2 phase 2):
// each game copies a weapon's overlay, tile sheet and palettes here when it loads; the host sends
// a hand's copy when its seq changes and writes the partner's at WEAPON_PARTNER_ADDR.
#define WEAPON_SELF_ADDR 0x80710000
#define WEAPON_PARTNER_ADDR 0x80720000
#define WEAPON_HAND_SIZE 0x8000 // per hand, from the address above
#define WEAPON_MAGIC 0x534E5057 // 'WPNS'
#define WEAPON_OVL_SIZE 0x3000    // the overlay, as at 0x8017A000 (hand 0) / 0x8017D000 (hand 1)
#define WEAPON_SHEET_SIZE 0x4000  // its tile sheet: 0x40 x 0x80 VRAM words (256 x 128, 4bpp)
#define WEAPON_CLUT_SIZE 0x300    // its 24 palettes (0x110 + hand * 24 on)
// M13: VRAM's second bank (lines 512-1023, our SwanStation build: patches/swanstation.patch),
// for the partner's graphics. An upload or fill with VRAM_BANK in its y goes there; a primitive
// with TPAGE_BANK in its tpage reads its texture from there, and one with CLUT_BANK in its clut
// its palette (rows 512 and up). Drawing and the display stay in the first bank.
#define VRAM_BANK 0x200
#define TPAGE_BANK 0x4000
#define CLUT_BANK 0x8000

// M13: the partner's status (g_Status from hp to statsTotal, and from subWeapon to the elements:
// stats, level, equipment), for the partner's body (partner.c). The host reads it from the
// partner's game and writes it here, magic last, when it changes.
#define STATUS_PARTNER_ADDR 0x80730000
#define STATUS_MAGIC 0x53544154 // 'STAT'
#define STATUS_A 0x80097BA0     // g_Status.hp
#define STATUS_A_SIZE 0x48
#define STATUS_B 0x80097BFC     // g_Status.subWeapon
#define STATUS_B_SIZE 0x34
typedef struct {
    /* 0x00 */ u32 magic; // STATUS_MAGIC once written
    /* 0x04 */ u8 a[STATUS_A_SIZE];
    /* 0x4C */ u8 b[STATUS_B_SIZE];
} CoopStatus; // size = 0x80

// M13 step 4: a player's familiar, for the partner to draw it (familiar.c): each game copies its
// familiar's overlay, tile sheet and palettes here when it loads; the host sends the copy when its
// seq changes and writes the partner's at FAMILIAR_PARTNER_ADDR.
#define FAMILIAR_SELF_ADDR 0x807C0000
#define FAMILIAR_PARTNER_ADDR 0x807E0000
#define FAMILIAR_MAGIC 0x4C4D4146 // 'FAML'
#define FAMILIAR_OVL_SIZE 0xA000   // as at 0x80170000
#define FAMILIAR_SHEET_SIZE 0x6000 // (0x2C0, 0x100) 0x40 x 0x80 VRAM words, then (0x2C0, 0x180) 0x20 x 0x80
#define FAMILIAR_CLUT_SIZE 0x400   // palettes 0x140-0x15F
typedef struct {
    /* 0x00 */ u32 magic;   // FAMILIAR_MAGIC once written
    /* 0x04 */ u32 seq;     // bumped with each new copy
    /* 0x08 */ u32 servant; // g_ServantLoaded: 0 none
    /* 0x0C */ u32 bank;    // its sprite bank (g_api.o.spriteBanks[0x14]), as it ran
    /* 0x10 */ u32 pad[4];
    /* 0x20 */ u8 ovl[FAMILIAR_OVL_SIZE];
    /* 0xA020 */ u16 sheet[FAMILIAR_SHEET_SIZE / 2];
    /* 0x10020 */ u16 clut[FAMILIAR_CLUT_SIZE / 2];
} CoopFamiliar; // size = 0x10420

typedef struct {
    /* 0x00 */ u32 magic; // WEAPON_MAGIC once written
    /* 0x04 */ u32 seq;   // bumped with each new copy (the host sends on a change)
    /* 0x08 */ u32 item;  // the item in that hand
    /* 0x0C */ u32 pad[5];
    /* 0x20 */ u8 ovl[WEAPON_OVL_SIZE];
    /* 0x3020 */ u16 sheet[WEAPON_SHEET_SIZE / 2];
    /* 0x7020 */ u16 clut[WEAPON_CLUT_SIZE / 2];
} CoopWeapon; // size = 0x7320

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
    /* 0x2A */ u16 aggroSwitches; // bosses switching to/from the partner so far (tests)
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
#define EV_HIT2 7  // a: slot | hitParams << 8, b: nFramesInvincibility | stunFrames << 8 | hitEffect << 16
// An entity the guest's hit detection created (a drop, blood, a damage number), for the
// authority to create in its world; three events, in this order:
#define EV_SPAWN 8  // a: entityId, b: pfnUpdate
#define EV_SPAWN2 9 // a: params, b: world x | world y << 16
#define EV_RECORD 11 // a: time attack event (0xFFFF: b is D_8003CB00's bits), b: record
#define EV_TAKEN 12  // a: slot | entityId << 8: the guest collected that drop; remove it, no reward
#define EV_EXP 13    // b: XP this game gained from a kill (one shared level, design/M11)
#define EV_USED 14   // a: item id: used up here (M13's fairy revive: the Life Apple), gone in the shared bag too
#define EV_KILLED 15  // a: enemy definition: this game's final boss died (Richter, Dracula: no castle flag records it), the partner's dies too; b 1 | ending << 8: and this game entered that ending
#define EV_SPAWN3 10 // a: slot range (0: 160-191, 1: 224-255) | velocityY >> 14 << 8, b: castleFlag

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
    /* 0x21448 */ u32 control; // host writes: CONTROL_* bits (launcher settings)
    /* 0x2144C */ u32 character; // host writes: CHAR_* this game's player plays, from its next load (M8)
    /* 0x21450 */ u32 options;   // host writes: OPT_* the player's own settings (M8b)
    /* 0x21454 */ u32 padExtra;  // host writes every frame: PADX_* buttons a PlayStation pad lacks
    /* 0x21458 */ u32 selfSpriteCount;    // game writes every frame (sprites.c, M12)
    /* 0x2145C */ CoopSprite selfSprites[COOP_SPRITES];
    /* 0x2163C */ u32 partnerSpriteCount; // host writes
    /* 0x21640 */ CoopSprite partnerSprites[COOP_SPRITES];
    /* 0x21820 */ u32 selfPrimCount;      // game writes every frame (sprites.c, M12)
    /* 0x21824 */ u8 selfPrims[COOP_PRIMS][COOP_PRIM_SIZE];
    /* 0x21E24 */ u32 partnerPrimCount;   // host writes
    /* 0x21E28 */ u8 partnerPrims[COOP_PRIMS][COOP_PRIM_SIZE];
    /* 0x22428 */ u32 selfPad;    // game writes every frame: its player's buttons (M13: the partner's
    /* 0x2242C */ u32 partnerPad; // host writes with each presence   copy runs on them, partner.c)
    /* 0x22430 */ u32 selfHitCount;    // game writes every frame: its player's attacks (M15, pvp.c)
    /* 0x22434 */ CoopHit selfHits[COOP_HITS];
    /* 0x224F4 */ u32 partnerHitCount; // host writes
    /* 0x224F8 */ CoopHit partnerHits[COOP_HITS];
} CoopLink; // size = 0x225B8

// Couch play: all games' sound goes to one speaker, and only one game may play music.
#define CONTROL_MUTE_MUSIC 1
#define CONTROL_NO_AGGRO 2 // bosses only ever chase this game's player (tests, tuning)
#define CONTROL_AGGRO_SHIFT 8 // bits 8-15: a boss's chance (of 256) to switch target, 0 = 128
#define CONTROL_PARTNER_VOL_SHIFT 16 // bits 16-23: the partner's sounds, % of their volume (0 = 60)
#define CONTROL_PVP 0x1000000 // the host's PvP setting: the partner's attacks hurt (M15, pvp.c)

// Playable characters (design/M8). Richter and Maria both run in Richter's overlay slot.
#define CHAR_ALUCARD 0
#define CHAR_RICHTER 1
#define CHAR_MARIA 2
// The player's own settings (CoopLink.options), per player in the launcher.
#define OPT_SHORTCUTS 1 // one-button moves (design/M8b §3.2)
#define OPT_PARTNER_SIM 2 // M13 spike: the partner simulated by the game's own player code (partner.c)
// Alucard's spell on each right-stick direction (up, right, down, left): 4 bits each from this
// bit, SpellIds + 1 (0: none).
#define OPT_SPELL_SHIFT 8
// CoopLink.padExtra: what a modern pad has and a PlayStation pad doesn't.
#define PADX_RS_UP 1
#define PADX_RS_RIGHT 2
#define PADX_RS_DOWN 4
#define PADX_RS_LEFT 8
// The launcher writes the chosen character's overlay and sound bank into expansion RAM before
// the game boots: a CharBlob header, then the overlay, the .VH and the .VB. Without one (or for
// another character), Richter's retail files from the disc are used.
#define CHAR_BLOB_ADDR 0x80400000
#define CHAR_BLOB_MAGIC 0x52414843 // 'CHAR'
typedef struct {
    u32 magic;     // CHAR_BLOB_MAGIC
    u32 character; // CHAR_*
    u32 ovlSize;   // bytes, loaded at Richter's overlay address (0x8013C000)
    u32 vhSize;    // the sound bank, replacing SD_RIH (0: keep Richter's)
    u32 vbSize;
    u32 partnerSize; // her build as the partner (design/M13 step 3: MARIAP.BIN), 0: none
    u32 pad[2];
} CharBlob; // size = 0x20, then the overlay, the .VH, the .VB and the partner build, each 4-byte aligned
extern CoopLink g_CoopLink;

#endif
