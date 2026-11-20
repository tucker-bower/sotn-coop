// The game <-> host mailbox (design/M1-link-presence.md, part 2). The host reads and writes it
// only between frames, while the emulator is paused, so neither side needs locking.
// The Python side mirrors this layout in link/mailbox.py: keep the two in sync and bump
// COOP_LINK_VERSION on any change.
#ifndef LINK_H
#define LINK_H

#define COOP_LINK_VERSION 17

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
// Bit 5: this player voted to skip the cutscene (arrive.c).
#define FLIP_SKIP_VOTE 0x20
// Bits 4, 3: this player is a bat in flight that can be held, and is being carried (carry.c).
#define FLIP_BAT 0x10
#define FLIP_CARRIED 0x08
// Bit 2: this game is between stages or mid-teleport. Its presence is half old, half new then
// (the new stage, the old room and scene flags, a mid-load position): never a place to be pulled to.
#define FLIP_LOADING 0x04

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
#define WEAPON_ARM 0x200    // CoopSprite.weapon: Alucard's punching arm, animCurFrame his frame (issue 123)

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
// M17: banks 1-3, one per partner body (partner k's is k + 1: design/M17-more-players.md). Uploads
// take the bank in y bits 9-10, textures in tpage bits 14-15, palettes CLUT bit 15 with bank - 1
// in its x bits 4-5 (a banked palette's x is under 0x100). Bank 1 is the three above.
#define VRAM_BANK_OF(b) ((b) << 9)
#define TPAGE_BANK_OF(b) ((b) << 14)
#define CLUT_BANK_OF(b) (CLUT_BANK | (((b) - 1) << 4))
#define TPAGE_BANKS 0xC000                 // a tpage's bank bits
#define TPAGE_BANK_IS(t) (((t) >> 14) & 3) // ...and its bank

// M13: the partner's status (g_Status from spellsLearnt to statsTotal, and from subWeapon to the elements:
// stats, level, equipment), for the partner's body (partner.c). The host reads it from the
// partner's game and writes it here, magic last, when it changes.
#define STATUS_PARTNER_ADDR 0x80730000
#define STATUS_MAGIC 0x53544154 // 'STAT'
#define STATUS_A 0x80097B9C     // g_Status.spellsLearnt (a spell only casts if it's learnt), then hp
#define STATUS_A_SIZE 0x4C
#define STATUS_B 0x80097BFC     // g_Status.subWeapon
#define STATUS_B_SIZE 0x34
typedef struct {
    /* 0x00 */ u32 magic; // STATUS_MAGIC once written
    /* 0x04 */ u8 a[STATUS_A_SIZE];
    /* 0x50 */ u8 b[STATUS_B_SIZE];
} CoopStatus; // size = 0x84

// M13 step 4: a player's familiar, for the partner to draw it (familiar.c): each game copies its
// familiar's overlay, tile sheet and palettes here when it loads; the host sends the copy when its
// seq changes and writes the partner's at FAMILIAR_PARTNER_ADDR.
#define FAMILIAR_SELF_ADDR 0x807C0000
#define FAMILIAR_PARTNER_ADDR 0x807E0000
// (0x807D8000: Co-op Maria's HUD set, 8 KB, kept while a familiar loads over it: character.c)
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
    /* 0x28 */ u8 role;        // ROLE_* (design/M4)
    /* 0x29 */ u8 standSlot;   // a guest: 1 + the stage slot of the solid it stands on, or 0 (issue 98)
    /* 0x2A */ u16 aggroSwitches; // bits 0-13: bosses switching to/from the partner so far (tests);
                                  // 14-15: the player's screen shape (OPT_WIDE_*, widescreen.c)
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

// M17 (3+ players, design/M17-more-players.md step 2): what the host writes for each partner after
// the first (partner 0 is CoopLink's partner fields: PARTNER_* below reads either). Partners' bodies,
// weapons and familiars read them all (step 4); the rest of the module, partner 0 only (step 5).
#define COOP_PARTNERS 3
typedef struct {
    /* 0x00 */ CoopPresence presence;
    /* 0x2C */ u32 age; // as partnerAge
    /* 0x30 */ u32 pad; // as partnerPad
    /* 0x34 */ u32 spriteCount;
    /* 0x38 */ CoopSprite sprites[COOP_SPRITES];
    /* 0x218 */ u32 primCount;
    /* 0x21C */ u8 prims[COOP_PRIMS][COOP_PRIM_SIZE];
    /* 0x81C */ u32 hitCount;
    /* 0x820 */ CoopHit hits[COOP_HITS];
} CoopPartnerIn; // size = 0x8E0
// ...and their copies in the 8 MB (docs/research.md "8 MB RAM": the gaps that hold them), for
// partner k = 1 or 2. Each hand's weapon copy is apart: no gap holds two for partner 2.
#define WEAPON_MORE_ADDR(k, hand) \
    ((k) == 1 ? 0x80731000 + (hand) * 0x7400 : (hand) ? 0x80572000 : 0x806F2000)
#define FAMILIAR_MORE_ADDR(k) ((k) == 1 ? 0x806D0000 : 0x806E1000)
#define STATUS_MORE_ADDR(k) (0x80730000 + (k) * 0x100)

// Rollback (#86, design/rollback.md): online, the host writes each partner's buttons by frame as
// they arrive, ahead of the played-out presence, and the frame the partner is at now. Partner
// k's body runs to that frame on the buttons it has and guesses the rest, and runs again from where
// a guess was wrong (partner.c). With each frame's buttons comes the partner's HP after that frame,
// so a hit in its own game lands on its body at the frame it happened. A guess is the partner's
// own suggestion when one came (its buttons as its app read them, before its game ran the frame:
// Slippi's input suggestions), else the last buttons held. In the 16 MB (our SwanStation build),
// with the bodies' snapshots after it. No ROLL_MAGIC (a LAN, the couch): the body runs on the
// presence's buttons, as before.
#define ROLL_ADDR 0x80800000
#define ROLL_MAGIC 0x4C4C4F52 // 'ROLL'
#define ROLL_PADS 32          // frames of buttons kept, a power of two
#define ROLL_GUESSES 16       // frames of suggestions kept past the newest, a power of two
typedef struct {
    /* 0x00 */ u32 magic;  // ROLL_MAGIC: the rest is good this frame (the host writes it last)
    /* 0x04 */ u32 newest; // the partner's newest frame whose buttons came
    /* 0x08 */ u32 target; // the frame the partner is at now (the body runs up to it)
    /* 0x0C */ u32 played; // the frame of the presence written this frame (the partner's spot then)
    /* 0x10 */ u32 known;  // bit f % ROLL_PADS: pads[] and hps[] hold frame f's, f in (newest - ROLL_PADS, newest]
    /* 0x14 */ u16 pads[ROLL_PADS];
    /* 0x54 */ u16 hps[ROLL_PADS];       // the partner's HP after that frame (0xFFFF: not said)
    /* 0x94 */ u32 guessed;              // bit f % ROLL_GUESSES: guesses[] holds a suggestion for f > newest
    /* 0x98 */ u16 guesses[ROLL_GUESSES];
    /* 0xB8 */ u32 spriteFrame;          // the partner's frame its sprites (weapons.c) are from
    /* 0xBC */ s16 spriteX, spriteY;     // and where it stood then (the room's pixels)
} CoopRollIn; // size = 0xC0
#define ROLL_SIZE 0xC0
#define ROLL_HP_NONE 0xFFFF
#define ROLL_IN(k) ((volatile CoopRollIn*)(ROLL_ADDR + (k) * 0x100))
// ...and for a guest's copies of a shared room (#292): the authority's frame the snapshot written
// this frame was taken at, and the authority's frame now, by its clock (0, 0: not online).
#define ROLL_SNAP_ADDR (ROLL_ADDR + 0x3F0)
#define ROLL_SNAP ((volatile u32*)ROLL_SNAP_ADDR)

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
    /* 0x225B8 */ u32 rulesOff;     // host writes every frame: RULE_* bits, the castle's rules (D162)
    /* 0x225BC */ u16 expPct;       // XP from a kill, % (0: 100)
    /* 0x225BE */ u16 dealtPct;     // damage the player deals, % (0: 100)
    /* 0x225C0 */ u16 takenPct;     // damage the player takes, after defense, % (0: 100)
    /* 0x225C2 */ u16 enemyHpPct;   // enemies' HP for one player, % (0: 100); more players multiply it (#316)
    /* 0x225C4 */ u16 rulesPad2;
    /* 0x225C6 */ u16 rulesPad;
    /* 0x225C8 */ CoopPartnerIn more[COOP_PARTNERS - 1]; // host writes: partners 1 and 2 (M17)
} CoopLink; // size = 0x23788

// Couch play: all games' sound goes to one speaker, and only one game may play music.
#define OPT_NO_TINT 0x20000000 // options: two of a kind aren't told apart by a tint (partner.c)
#define OPT_SPELL_TRIGGERS 0x40000000 // options: spells on R2 or L2 and a face button (spells.c)
#define OPT_PARTNER_HP 0x80000000 // options: the partner's health under this player's (issue 106)
#define CONTROL_MUTE_MUSIC 1
#define CONTROL_NO_AGGRO 2 // bosses only ever chase this game's player (tests, tuning)
#define CONTROL_AGGRO_SHIFT 8 // bits 8-15: a boss's chance (of 256) to switch target, 0 = 128
#define CONTROL_PARTNER_VOL_SHIFT 16 // bits 16-23: the partner's sounds, % of their volume (0 = 60)
#define CONTROL_PVP 0x1000000 // the host's PvP setting: the partner's attacks hurt (M15, pvp.c)
#define CONTROL_HOLD 0x2000000 // the app has a box up (F9's report): the game holds still, as paused (#192)

// The castle's rules (D162, design/M-castle-rules.md): each bit turns a co-op change to the game
// off, so all zero is the game as we built it. Bits 24 and up also go to the player overlays
// through g_CoopOptions (OPT_NO_*, characters/richter-ps1/coop_ric.h).
#define RULE_NO_SHARED_LEVEL 0x001  // no XP split, no XP sent to the partner
#define RULE_NO_SHARED_GOLD 0x002   // each player keeps their own gold
#define RULE_NO_REVIVE 0x004        // a fallen player stays down until both are
#define RULE_NO_FAERIE_REVIVE 0x008 // a partner's faerie doesn't revive
#define RULE_NO_BOSS_PULL 0x010     // a boss fight doesn't bring the partner
#define RULE_NO_SCENE_PULL 0x020    // a cutscene doesn't bring the partner
#define RULE_NO_NEAR_TARGET 0x040   // enemies aim at this game's player, not the nearer one
#define RULE_NO_MAP_TELEPORT 0x080  // Cross on the map doesn't go to the partner
#define RULE_NO_OFFHAND 0x100       // Richter and Maria: Circle doesn't use the off-hand item
#define RULE_NO_FAMILIARS 0x200     // Richter and Maria: no familiars
#define RULE_BAT_CARRY 0x400        // on, unlike the others: a partner can hang onto the bat (carry.c)
#define RULE_NO_GEAR_EFFECTS 0x800  // Richter and Maria: Healing Mail, Blood Cloak do nothing for them (character.c, progress.c)
#define RULE_OVERLAY_MASK 0xFF000000
#define OPT_NO_GROWTH 0x01000000      // Richter and Maria: no levels
#define OPT_NO_RELIC_MOVES 0x02000000 // Richter and Maria: every move from the start (#168)
#define OPT_NO_AIR_JUMPS 0x04000000   // Richter and Maria: their own jumps only (D122 off)
#define OPT_NO_ALUCARD_STATS 0x08000000 // Richter and Maria: their own damage, given and taken (#160)
#define OPT_NO_GEAR_EFFECTS 0x10000000  // to the overlays only: RULE_NO_GEAR_EFFECTS, for their sub-weapons (#202)
void WidescreenFrame(void); // widescreen.c (design/M19)
void WidescreenAfterPrims(void);
u16 WidescreenShape(void);
extern u16 g_CoopWideWidth;
extern u16 g_CoopStage; // the stage that's loaded, for anything about the partner (coop.c, #179)
#define RULE_OFF(bit) (g_CoopLink.rulesOff & (bit))
#define RULE_PCT(field, otherwise) (g_CoopLink.field ? (s32)g_CoopLink.field : (otherwise))

// Playable characters (design/M8). Richter and Maria both run in Richter's overlay slot.
#define CHAR_ALUCARD 0
#define CHAR_RICHTER 1
#define CHAR_MARIA 2
// Other mods' characters (docs/design/character-mods.md): they play as their mod built them, with
// none of the co-op characters' features (levels, Alucard's stats and gear, relic moves).
#define CHAR_ULT_MARIA 3 // SOTN Ultimate's PSP Maria (characters/maria-ultimate)
#define CHAR_SAT_MARIA 4 // SOTN Ultimate's Saturn Maria, a fork of Richter's code (characters/maria-saturn)
#define CHAR_ULT_RICHTER 5 // SOTN Ultimate's Richter: retail Richter in the Saturn's coat (launcher/saturn_richter.py)
#define CHAR_LAST CHAR_ULT_RICHTER
// The player's own settings (CoopLink.options), per player in the launcher.
#define OPT_SHORTCUTS 1 // one-button moves (design/M8b §3.2)
#define OPT_ALUCARD_HUD 4 // Richter and Maria: Alucard's health bar (character.c)
#define OPT_PARTNER_SIM 2 // M13 spike: the partner simulated by the game's own player code (partner.c)
// Alucard's spell on each right-stick direction (up, right, down, left): 4 bits each from this
// bit, SpellIds + 1 (0: none).
#define OPT_WIDE_SHIFT 3   // options: the screen's shape, 0 4:3, 1 16:9, 2 21:9 (widescreen.c)
#define OPT_WIDE_MASK 0x18
#define OPT_SPELL_SHIFT 8
// CoopLink.padExtra: what a modern pad has and a PlayStation pad doesn't.
#define PADX_RS_UP 1
#define PADX_RS_RIGHT 2
#define PADX_RS_DOWN 4
#define PADX_RS_LEFT 8
// The launcher writes the chosen character's overlay and sound bank into expansion RAM before
// the game boots: a CharBlob header, then the overlay, the .VH and the .VB. Without one (or for
// another character), Richter's retail files from the disc are used.
#define CHAR_BLOB_ADDR 0x80300000 // after the module (coop.ld checks it ends before)
#define CHAR_BLOB_MAGIC 0x52414843 // 'CHAR'
typedef struct {
    u32 magic;     // CHAR_BLOB_MAGIC
    u32 character; // CHAR_*
    u32 ovlSize;   // bytes, loaded at Richter's overlay address (0x8013C000)
    u32 vhSize;    // the sound bank, replacing SD_RIH (0: keep Richter's)
    u32 vbSize;
    u32 partnerSize; // her build as the partner (design/M13 step 3: MARIAP.BIN), 0: none
    u32 vh2Size;     // a second sound bank, replacing SD_MAR (vab 2; Saturn Maria's), 0: keep it
    u32 vb2Size;
} CharBlob; // size = 0x20, then the overlay, the .VH, the .VB, the partner build, the .VH and .VB of
            // vab 2, each 4-byte aligned
// One blob for each character in the session that needs one (the player's, the partner's), one
// after another; the first word after the last is not CHAR_BLOB_MAGIC.
#define CHAR_BLOB_ALIGN(n) (((n) + 3) & ~3)
#define CHAR_BLOB_VH2(b) \
    ((const u8*)((b) + 1) + CHAR_BLOB_ALIGN((b)->ovlSize) + CHAR_BLOB_ALIGN((b)->vhSize) + \
     CHAR_BLOB_ALIGN((b)->vbSize) + CHAR_BLOB_ALIGN((b)->partnerSize))
#define CHAR_BLOB_NEXT(b) \
    ((const CharBlob*)(CHAR_BLOB_VH2(b) + CHAR_BLOB_ALIGN((b)->vh2Size) + CHAR_BLOB_ALIGN((b)->vb2Size)))
#define CHAR_BLOBS_MAX 4 // Co-op Maria, Ultimate Maria, Saturn Maria, Ultimate Richter
#define CHAR_BLOBS_END 0x804C0000 // PARTNER_ULT_ADDR (module/coop_api.h): the blobs end before it (1.75 MB)
extern CoopLink g_CoopLink;
// M17: partner k's side of the link (0: CoopLink's partner fields; 1 and 2: more[k - 1])
#define PARTNER_PRESENCE(k) ((k) ? &g_CoopLink.more[(k) - 1].presence : &g_CoopLink.partner)
#define PARTNER_AGE(k) ((k) ? g_CoopLink.more[(k) - 1].age : g_CoopLink.partnerAge)
#define PARTNER_SPRITE_COUNT(k) ((k) ? g_CoopLink.more[(k) - 1].spriteCount : g_CoopLink.partnerSpriteCount)
#define PARTNER_SPRITES(k) ((k) ? g_CoopLink.more[(k) - 1].sprites : g_CoopLink.partnerSprites)
#define PARTNER_PRIM_COUNT(k) ((k) ? g_CoopLink.more[(k) - 1].primCount : g_CoopLink.partnerPrimCount)
#define PARTNER_PRIMS(k) ((k) ? g_CoopLink.more[(k) - 1].prims : g_CoopLink.partnerPrims)

#endif
