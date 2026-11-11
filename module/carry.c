// Hanging onto Bat Alucard (design/bat-carry.md): a player presses Up beside the partner's bat and
// hangs on. Each game keeps its own player: the carried one's follows the bat's position in
// presence, with its buttons off, and the bat's game flies slower while presence says it's
// carrying. Cross drops off (their own jump still works), and so does a hit, the bat landing or
// changing form. Through a door, the carried player follows by the teleport path.
#define COOP_MODULE
#include <game.h>
#include "arrive.h"
#include "carry.h"
#include "character.h"
#include "link.h"

void CheckCollision(s32 x, s32 y, Collider* res, s32 unk); // DRA

#define REACH_X 32        // px from the bat to grab it
#define REACH_Y 48
#define HANG_Y 20         // px below the bat, when there's room
#define RAISE_Y 44        // px above that the player can be lifted, over a floor
#define RAISE_STEP 4
#define HEAD 20           // px from the hanging player's center to their head and feet
#define FEET 24
#define BAT_SPEED_PCT 60  // of the bat's speed while carrying
#define FRESH_FRAMES 30   // the partner's presence no older than this
#define DOOR_FRAMES 60    // in different rooms this long: follow (their own door may take them too)
#define LOST_FRAMES 300   // in different rooms this long: let go
#define LANDED_FRAMES 30  // still on the ground this long, the bat has landed: flying up stairs hasn't

static bool s_Carried;
static u16 s_Apart;
static s32 s_Hp;
static s32 s_BatX, s_BatY; // the bat's place in the room before this frame's update, 16.16
static bool s_BatMoved;
static u8 s_OnGround;
static s16 s_LandX, s_LandY;

static bool InPlay(void) {
    return g_GameState == Game_Play && g_GameStep == Play_Default && g_GameEngineStep == Engine_Normal;
}

static bool SameRoom(const CoopPresence* p) {
    return p->stage == g_CoopStage && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top;
}

static bool Clear(s32 x, s32 y) {
    Collider col;

    CheckCollision(x, y, &col, 0);
    return !(col.effects & EFFECT_SOLID);
}

static bool BodyFits(s32 x, s32 y) { return Clear(x, y - HEAD) && Clear(x, y) && Clear(x, y + FEET); }

// Under the bat, or as far above that as the floor needs: a bat flies lower than a player stands.
// False if there's no room for a body, as in a gap only the bat fits through.
static bool Follow(const CoopPresence* p) {
    s32 x = p->x - g_Tilemap.scrollX.i.hi;
    s32 y = p->y - g_Tilemap.scrollY.i.hi + HANG_Y;
    s32 up;

    for (up = 0; !BodyFits(x, y); up += RAISE_STEP, y -= RAISE_STEP) {
        if (up >= RAISE_Y) {
            return false;
        }
    }
    PLAYER.posX.val = x << 16;
    PLAYER.posY.val = y << 16;
    g_PlayerX = p->x; // the camera's copy: without it the game puts the player back
    g_PlayerY = y + g_Tilemap.scrollY.i.hi;
    PLAYER.velocityX = 0;
    PLAYER.velocityY = 0;
    return true;
}

static void Grab(const CoopPresence* p) {
    s32 dx = p->x - (PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi);
    s32 dy = p->y - (PLAYER.posY.i.hi + g_Tilemap.scrollY.i.hi);

    if ((g_pads[0].tapped & PAD_UP) && (p->flipX & FLIP_BAT) && SameRoom(p) && dx >= -REACH_X && dx <= REACH_X &&
        dy >= -REACH_Y && dy <= REACH_Y && !(g_Player.status & (PLAYER_STATUS_TRANSFORM | PLAYER_STATUS_DEAD)) &&
        !ArriveBusy()) {
        s_Carried = true;
        s_Apart = 0;
        s_Hp = g_Status.hp;
    }
}

static void Carried(const CoopPresence* p) {
    if ((g_pads[0].tapped & PAD_CROSS) || g_Status.hp < s_Hp || (g_Player.status & PLAYER_STATUS_DEAD) ||
        ArriveBusy() || g_CoopLink.partnerAge > FRESH_FRAMES || (p->flags & PRESENCE_DEAD)) {
        s_Carried = false;
        return;
    }
    if (SameRoom(p)) {
        // A door walks the bat along the floor: only out in the room does that mean it landed.
        if (!(p->flipX & FLIP_BAT) && !(p->flags & PRESENCE_BUSY)) {
            s_Carried = false;
            return;
        }
        s_Apart = 0;
        if (!Follow(p)) {
            s_Carried = false;
            return;
        }
    } else if (++s_Apart > LOST_FRAMES) {
        s_Carried = false;
        return;
    } else if (s_Apart >= DOOR_FRAMES) {
        ArriveFollow();
    }
    s_Hp = g_Status.hp;
    g_pads[0].pressed &= PAD_START | PAD_SELECT;
    g_pads[0].tapped &= PAD_START | PAD_SELECT;
}

void CarryBefore(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    s_BatMoved = false;
    if (!(g_CoopLink.rulesOff & RULE_BAT_CARRY)) {
        s_Carried = false;
        return;
    }
    if (!InPlay()) {
        return;
    }
    if (s_Carried) {
        Carried(p);
    } else if (g_CoopLink.partnerAge <= FRESH_FRAMES) {
        Grab(p);
    }
    if (p->flipX & FLIP_CARRIED && g_CoopLink.partnerAge <= FRESH_FRAMES && SameRoom(p)) {
        s_BatX = PLAYER.posX.val + g_Tilemap.scrollX.val;
        s_BatY = PLAYER.posY.val + g_Tilemap.scrollY.val;
        s_BatMoved = (g_Player.status & PLAYER_STATUS_BAT_FORM) != 0;
    }
}

// The bat's own code sets its speed and moves it inside UpdateGame, so the share comes off after.
void CarryAfter(void) {
    s32 dx, dy, x, y;

    if (!s_BatMoved || !InPlay()) {
        return;
    }
    dx = PLAYER.posX.val + g_Tilemap.scrollX.val - s_BatX;
    dy = PLAYER.posY.val + g_Tilemap.scrollY.val - s_BatY;
    if (dx < FIX(-16) || dx > FIX(16) || dy < FIX(-16) || dy > FIX(16)) {
        return; // a room change, not a flight
    }
    x = PLAYER.posX.i.hi;
    y = PLAYER.posY.i.hi;
    PLAYER.posX.val -= (dx >> 8) * (100 - BAT_SPEED_PCT) / 100 << 8;
    PLAYER.posY.val -= (dy >> 8) * (100 - BAT_SPEED_PCT) / 100 << 8;
    g_PlayerX += PLAYER.posX.i.hi - x;
    g_PlayerY += PLAYER.posY.i.hi - y;
}

u8 CarryPresence(void) {
    u8 out = s_Carried ? FLIP_CARRIED : 0;

    if ((g_Player.vram_flag & 1) && PLAYER.posX.i.hi == s_LandX && PLAYER.posY.i.hi == s_LandY) {
        s_OnGround = MIN(s_OnGround + 1, LANDED_FRAMES);
    } else {
        s_OnGround = 0;
    }
    s_LandX = PLAYER.posX.i.hi;
    s_LandY = PLAYER.posY.i.hi;
    if ((g_CoopLink.rulesOff & RULE_BAT_CARRY) && CharacterLoaded() == CHAR_ALUCARD &&
        (g_Player.status & PLAYER_STATUS_BAT_FORM) && s_OnGround < LANDED_FRAMES) {
        out |= FLIP_BAT;
    }
    return out;
}
