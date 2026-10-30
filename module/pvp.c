// M15 (design/M15-pvp.md): PvP, the host's option. The victim's game decides every hit (D132):
// each game sends its player's attacks' hitboxes with presence (hand weapons, subweapons, spells,
// familiars: whatever hit detection would test against an enemy), and the partner's game tests
// them against its own player before that player's update, as the stage's hit detection does for
// an enemy's attack. The player's own damage code then does the rest: defence, resistances,
// knockback, invincibility frames, the voice. The attacker's game shows the hit on its copy of the
// victim from the victim's HP drop (partner.c).
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "boss.h"
#include "partner.h"
#include "pvp.h"

#define SLOT_LAST 63
#define SAFE_FRAMES 180 // no PvP in a player's first 3 s in a room (spawn protection)

u32 g_CoopPvpHits; // hits taken from the partner (tests read it: coop.map)
static Entity s_Hitter; // the attack, for the player's knockback (PLAYER.unkB8: its side)

// This game's attacks, for the partner: after RenderEntities, with presence.
void PvpCapture(void) {
    s32 i, n = 0;
    Entity* e;
    CoopHit* h;

    for (i = 1; i <= SLOT_LAST && n < COOP_HITS; i++) {
        e = &g_Entities[i];
        // hitboxState 4 is a weapon that only breaks things (its attack 0xFF: weapon/shared.h)
        if (!e->entityId || !(e->hitboxState & 0x3E) || (e->hitboxState & 0x80) || e->hitboxState == 4 ||
            e->attack <= 0 || !e->hitboxWidth || !e->hitboxHeight) {
            continue;
        }
        h = &g_CoopLink.selfHits[n++];
        h->x = e->posX.i.hi + (e->facingLeft ? -e->hitboxOffX : e->hitboxOffX) + g_Tilemap.scrollX.i.hi;
        h->y = e->posY.i.hi + e->hitboxOffY + g_Tilemap.scrollY.i.hi;
        h->w = e->hitboxWidth;
        h->h = e->hitboxHeight;
        h->hitboxState = e->hitboxState;
        h->facingLeft = e->facingLeft;
        h->attack = e->attack;
        h->element = e->attackElement;
    }
    g_CoopLink.selfHitCount = n;
}

static bool PvpNow(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    if (!(g_CoopLink.control & CONTROL_PVP) || g_CoopLink.partnerAge > PARTNER_STALE_FRAMES) {
        return false;
    }
    if (g_GameState != Game_Play || g_GameStep != Play_Default || g_GameEngineStep != Engine_Normal ||
        g_CutsceneHasControl || (g_Player.status & PLAYER_STATUS_DEAD) || BossHere()) {
        return false;
    }
    if (!(p->flags & PRESENCE_IN_PLAY) ||
        (p->flags & (PRESENCE_DEAD | PRESENCE_BUSY | PRESENCE_PAUSED | PRESENCE_BOSS | PRESENCE_CUTSCENE)) ||
        p->stage != g_StageId || p->roomLeft != g_Tilemap.left || p->roomTop != g_Tilemap.top) {
        return false;
    }
    return g_CoopLink.self.roomFrames >= SAFE_FRAMES && p->roomFrames >= SAFE_FRAMES;
}

// Before the game's update: the partner's attacks against this game's player.
void PvpUpdate(void) {
    const CoopHit* h;
    s32 i, n, px, py, x, y, w, hh;
    s16 dx = 0, dy = 0;

    if (!PvpNow() || !(PLAYER.hitboxState & 1) || (PLAYER.hitboxState & 0x80) || !PLAYER.hitboxWidth ||
        !PLAYER.hitboxHeight) {
        return;
    }
    if (PartnerSimulated()) { // where its body is drawn (and the swings with it: weapons.c)
        PartnerBodyOffset(&dx, &dy);
    }
    px = PLAYER.posX.i.hi + (PLAYER.facingLeft ? -PLAYER.hitboxOffX : PLAYER.hitboxOffX);
    py = PLAYER.posY.i.hi + PLAYER.hitboxOffY;
    n = g_CoopLink.partnerHitCount < COOP_HITS ? g_CoopLink.partnerHitCount : COOP_HITS;
    for (i = 0; i < n; i++) {
        h = &g_CoopLink.partnerHits[i];
        x = h->x + dx - g_Tilemap.scrollX.i.hi;
        y = h->y + dy - g_Tilemap.scrollY.i.hi;
        w = h->w - 1 + PLAYER.hitboxWidth;
        hh = h->h - 1 + PLAYER.hitboxHeight;
        if (px - x > w || x - px > w || py - y > hh || y - py > hh || PLAYER.hitPoints >= h->attack) {
            continue;
        }
        // As the stage's hit detection (src/st/collision.h) records an enemy's attack on the player
        s_Hitter.posX.i.hi = x;
        s_Hitter.posY.i.hi = y;
        s_Hitter.hitboxOffX = 0;
        s_Hitter.facingLeft = h->facingLeft;
        s_Hitter.velocityX = 0;
        PLAYER.unkB8 = &s_Hitter;
        PLAYER.hitFlags = (h->hitboxState & 8) ? 3 : 1;
        // Its elements (the victim's resistances apply); an enemy's low bits are its damage kind,
        // a player's attack has none: a plain hit, knocked back (DAMAGEKIND_1)
        PLAYER.hitParams = (h->element & ~0x1F) | DAMAGEKIND_1;
        PLAYER.hitPoints = h->attack;
        g_CoopPvpHits++;
    }
}
