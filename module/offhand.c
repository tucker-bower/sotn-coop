// Off-hand weapons for Richter and Maria (design/M8b §4.1): ○ uses what's in a hand.
//
// Richter keeps his whip and Maria her guardians. In Alucard's equip menu they put any weapon,
// food or potion in a hand, and ○ uses it:
// - a weapon swings: the weapon's own sprite (its frame reaching furthest forward, from the
//   weapon overlay the game loaded for that hand) sweeps an arc in front of them, or thrusts for
//   a fist. It hits with the weapon's own numbers (GetEquipProperties: ATK + STR, element, hit
//   effect), through the game's normal damage, as Alucard's does;
// - potions heal as Alucard's do (Potion, High potion, Elixir, Manna prism: DRA's amounts),
//   and food heals by its value, at once. (Alucard's item entities are DRA's, which Richter's
//   entity loop doesn't run; food is dropped and picked up by its weapon overlay, which would
//   take Richter's sprite bank.) The other potions (resists, stats): not yet;
// - shields only add their DEF (the equipment totals do that); thrown items: not yet.
// No new art: the swing is the weapon's frame, turned (design/M8b §4.1, option A).
//
// The weapon overlays (0x8017A000, 0x8017D000) are loaded by the game when the menu closes;
// after a load (where the game skips them for Richter's player code) the module loads them.
//
// Palettes: a weapon's 24 palettes load over 0x110-0x13F, where Richter's and Maria's own are
// (Alucard has his elsewhere). In their games, the module keeps their palettes there: each time
// weapon palettes load (the menu closing, or the module's own load), the one the weapon is drawn
// with moves to a palette they don't use, and theirs are put back.
#define COOP_MODULE
#include <game.h>
#include <disk.h>
#include <sfx.h>
#include "coop_api.h"
#include "link.h"
#include "character.h"
#include "offhand.h"

// DRA (src/dra/menu.c, 5D5BC.c, 7879C.c)
bool LoadWeaponPrg(s32 equipIndex);
void InitWeapon(s32 itemSlot);
void GetEquipProperties(s32 handId, Equipment* res, s32 equipId);
void func_80118894(Entity* self);
int ReduceWeapon(s32 hand);
s32 GetStatusAilmentTimer(s32 statusAilment, s32 timer);
#define STATUS_AILMENT_POTION 4      // src/dra/dra.h: STATUS_AILMENT_UNK04
#define STATUS_AILMENT_HIGH_POTION 5 // STATUS_AILMENT_UNK05
void PlaySfx(s32 sfxId);
void DestroyEntity(Entity* entity);
extern Equipment g_EquipDefs[];
extern s32 g_EquippedWeaponIds[2];

#define WEAPON_PRG(hand) ((hand) ? 0x8017D000 : 0x8017A000)
#define WEAPON_ANIMSET(hand) ((SpriteParts**)(WEAPON_PRG(hand) + 0x40)) // every w0_/w1_ overlay
#define WEAPON_SIZE 0x3000
#define BANK 0x14 // stage sprite banks 0x14-0x15 are free in every stage (Richter: 0x10-0x13)
#define E_OFFHAND 0x7E
#define SLOT_FIRST 0x18
#define SLOT_LAST 0x2F
#define SWING_FRAMES 14
#define HAND_X 6   // where Richter's and Maria's hand is, from their middle (facing right)
#define HAND_Y -10

static s8 s_Loading = -1; // the hand whose weapon is being loaded
static u8 s_Hand;         // the hand of the swing now

#define PAL_WEAPONS 0x110 // a hand's 24 palettes from here (src/weapon/shared.h)
#define N_WEAPON_PAL 24  // include/weapon.h
#define N_PAL 48
static u16 s_Own[N_PAL * COLORS_PER_PAL]; // the player's palettes 0x110-0x13F, as loaded
static bool s_HaveOwn;
static s16 s_Slot[2];   // where each hand's weapon palette goes (one the player doesn't use)
static u32 s_SlotsFor = 0xFF; // the character they were picked for
static u16 s_WeaponPal[2][COLORS_PER_PAL];
static u8 s_PrevEngine; // g_GameEngineStep last frame

static bool InPlay(void) {
    return g_GameState == Game_Play && g_GameEngineStep == Engine_Normal && g_StageId != STAGE_ST0 &&
           CharacterLoaded() != CHAR_ALUCARD;
}

static u8 Category(s32 hand) { return g_EquipDefs[g_Status.equipment[hand]].itemCategory; }

static bool IsWeapon(u8 category) {
    return category == ITEM_S_SWORD || category == ITEM_SWORD || category == ITEM_FIST ||
           category == ITEM_CLUB || category == ITEM_TWOHAND || category == ITEM_THROW_1;
}

// The weapon overlay of what's in that hand (0xFF: none, e.g. the empty hand).
static u8 WeaponOvl(s32 hand) { return g_EquipDefs[g_Status.equipment[hand]].weaponId; }

// The weapon in that hand is the one in its overlay slot.
static bool Loaded(s32 hand) { return WeaponOvl(hand) != 0xFF && g_EquippedWeaponIds[hand] == WeaponOvl(hand); }

static u16* Pal(s32 pal) { return (u16*)g_Clut + pal * COLORS_PER_PAL; }

static void Upload(void) {
    RECT rect;

    rect.x = 0;
    rect.y = 0xF1; // palettes 0x110-0x13F (src/weapon/shared.h)
    rect.w = 0x100;
    rect.h = 3;
    LoadImage(&rect, (u_long*)Pal(PAL_WEAPONS));
}

// The weapons' palettes, in their slots.
static void PutWeaponPals(void) {
    s32 h, k;

    for (h = 0; h < 2; h++) {
        if (s_Slot[h] >= 0) {
            for (k = 0; k < COLORS_PER_PAL; k++) {
                Pal(s_Slot[h])[k] = s_WeaponPal[h][k];
            }
        }
    }
    Upload();
}

// The player's own palettes, once in play after a load, and two they leave empty (picked once
// per character: a load keeps the weapons' palettes where they were).
static void KeepOwn(void) {
    s32 p, k, n = 0;

    s_HaveOwn = true;
    if (s_SlotsFor != CharacterLoaded()) {
        s_SlotsFor = CharacterLoaded();
        s_Slot[0] = s_Slot[1] = -1;
        for (p = N_PAL - 1; p >= 0 && n < 2; p--) {
            for (k = 0; k < COLORS_PER_PAL && !Pal(PAL_WEAPONS + p)[k]; k++) {
            }
            if (k == COLORS_PER_PAL) {
                s_Slot[n++] = PAL_WEAPONS + p;
            }
        }
    }
    PutWeaponPals();
    for (k = 0; k < N_PAL * COLORS_PER_PAL; k++) {
        s_Own[k] = Pal(PAL_WEAPONS)[k];
    }
}

static s32 Extended(SpriteParts** animset);

// Weapon palettes for that hand just loaded over the player's: its own goes to its slot, and
// the player's come back. Then the three palette rows are sent to VRAM, as the weapon does.
static void FixPalettes(s32 hand) {
    u16* block = Pal(PAL_WEAPONS + hand * N_WEAPON_PAL);
    u16* own = s_Own + hand * N_WEAPON_PAL * COLORS_PER_PAL;
    s32 k, frame, clut = 0;

    for (k = 0; k < N_WEAPON_PAL * COLORS_PER_PAL && block[k] == own[k]; k++) {
    }
    if (k == N_WEAPON_PAL * COLORS_PER_PAL) {
        return; // nothing loaded over them
    }
    s_Hand = hand;
    if (IsWeapon(Category(hand)) && Loaded(hand) && (frame = Extended(WEAPON_ANIMSET(hand))) != 0) {
        clut = WEAPON_ANIMSET(hand)[frame]->parts[0].clut;
    }
    for (k = 0; k < COLORS_PER_PAL; k++) {
        s_WeaponPal[hand][k] = block[clut * COLORS_PER_PAL + k];
    }
    for (k = 0; k < N_WEAPON_PAL * COLORS_PER_PAL; k++) {
        block[k] = own[k];
    }
    PutWeaponPals();
}

// After a load, the game didn't load Richter's or Maria's weapons: the module does, one hand at
// a time, the way the menu does when it closes.
static void LoadWeapons(void) {
    s32 hand;

    if (s_Loading >= 0) {
        if (!g_IsUsingCd) {
            InitWeapon(s_Loading);
            FixPalettes(s_Loading);
            s_Loading = -1;
        }
        return;
    }
    for (hand = 0; hand < 2; hand++) {
        if (IsWeapon(Category(hand)) && WeaponOvl(hand) != 0xFF && !Loaded(hand) && !g_IsUsingCd &&
            LoadWeaponPrg(hand)) {
            s_Loading = hand;
            return;
        }
    }
}

// The frame of the weapon's sprites that reaches furthest forward: the blade held out.
static s32 Extended(SpriteParts** animset) {
    s32 best = 0, reach = -999, i, k, r;
    SpriteParts* parts;

    for (i = 1; i < 64; i++) {
        parts = animset[i];
        if ((u32)parts < WEAPON_PRG(s_Hand) || (u32)parts >= WEAPON_PRG(s_Hand) + WEAPON_SIZE ||
            parts->count == 0 || parts->count > 16) {
            break;
        }
        for (k = 0; k < parts->count; k++) {
            r = parts->parts[k].offsetx + parts->parts[k].width;
            if (r > reach) {
                reach = r;
                best = i;
            }
        }
    }
    return best;
}

// The hitbox around the frame, and the hilt (its end nearest the body) as the turning point.
static void Hitbox(Entity* self, SpriteParts* parts) {
    s32 k, x0 = 999, x1 = -999, y0 = 999, y1 = -999;
    SpritePart* p;

    for (k = 0; k < parts->count; k++) {
        p = &parts->parts[k];
        x0 = p->offsetx < x0 ? p->offsetx : x0;
        y0 = p->offsety < y0 ? p->offsety : y0;
        x1 = p->offsetx + p->width > x1 ? p->offsetx + p->width : x1;
        y1 = p->offsety + p->height > y1 ? p->offsety + p->height : y1;
    }
    self->hitboxOffX = (x0 + x1) / 2;
    self->hitboxOffY = (y0 + y1) / 2;
    self->hitboxWidth = (x1 - x0) / 2;
    self->hitboxHeight = (y1 - y0) / 2 + 12; // the arc sweeps above and below it
    self->rotPivotX = x0;
    self->rotPivotY = (y0 + y1) / 2;
    self->ext.weapon.unk82 = HAND_X - x0; // EntityOffhand: the hilt to the hand
    self->ext.weapon.unk90 = HAND_Y - (y0 + y1) / 2;
}

// The swing: the weapon's extended frame turns from raised to lowered in front of the player.
static void EntityOffhand(Entity* self) {
    s32 t = self->ext.weapon.anim; // frames since the swing began
    bool fist = self->params & 1;

    // The frame is placed for Alucard's arm: its hilt goes to their hand instead.
    self->posX.val = PLAYER.posX.val;
    self->posX.i.hi += PLAYER.facingLeft ? -self->ext.weapon.unk82 : self->ext.weapon.unk82;
    self->posY.val = PLAYER.posY.val;
    self->posY.i.hi += self->ext.weapon.unk90;
    self->facingLeft = PLAYER.facingLeft;
    self->zPriority = PLAYER.zPriority + 2;
    if (t >= SWING_FRAMES || !InPlay()) {
        self->hitboxState = 0;
        DestroyEntity(self);
        return;
    }
    if (fist) { // a punch: out and back
        self->rotate = 0;
        self->posX.i.hi += (PLAYER.facingLeft ? -1 : 1) * (t < SWING_FRAMES / 2 ? t : SWING_FRAMES - t);
    } else { // raised 70 degrees to lowered 30, around the hilt (either way it faces)
        self->rotate = -0x320 + t * 0x470 / SWING_FRAMES;
    }
    // It hits in the middle of the swing, where the blade is in front.
    self->hitboxState = (t >= 3 && t <= SWING_FRAMES - 3) ? self->ext.weapon.unk80 : 0;
    self->ext.weapon.anim = t + 1;
}

static void Swing(s32 hand) {
    Equipment equip;
    Entity* e;
    s32 slot, frame, item = g_Status.equipment[hand];

    // Attackers are slots 1-47 for the stage's hit detection (src/st/collision.h): the highest
    // free one, away from where the player's own attacks start.
    for (slot = SLOT_LAST; slot >= SLOT_FIRST; slot--) {
        if (!g_Entities[slot].entityId) {
            break;
        }
    }
    if (slot < SLOT_FIRST) {
        return;
    }
    s_Hand = hand;
    frame = Extended(WEAPON_ANIMSET(hand));
    if (!frame) {
        return;
    }
    ((SpriteParts**)g_api.o.spriteBanks)[BANK + hand] = (SpriteParts*)WEAPON_ANIMSET(hand);
    e = &g_Entities[slot];
    DestroyEntity(e);
    e->entityId = E_OFFHAND;
    e->pfnUpdate = EntityOffhand;
    e->step = 1; // the game never picks an update function for it (7879C.c)
    e->params = Category(hand) == ITEM_FIST;
    e->animSet = ANIMSET_OVL(BANK + hand);
    e->animCurFrame = frame;
    e->palette = s_Slot[hand] >= 0 ? PAL_UNK_FLAG | s_Slot[hand] : PAL_UNK_110 + (hand ? 0x18 : 0);
    e->unk5A = 0x64 + (hand ? 2 : 0);
    e->flags = FLAG_UNK_20000 | FLAG_POS_PLAYER_LOCKED;
    e->drawFlags = ENTITY_ROTATE;
    GetEquipProperties(hand, &equip, item);
    e->attack = equip.attack;
    e->attackElement = equip.element;
    e->ext.weapon.unk80 = equip.hitType ? equip.hitType : 2;
    e->nFramesInvincibility = equip.enemyInvincibilityFrames;
    e->stunFrames = equip.stunFrames;
    e->hitEffect = equip.hitEffect;
    e->entityRoomIndex = equip.criticalRate;
    e->ext.weapon.anim = 0;
    func_80118894(e);
    Hitbox(e, WEAPON_ANIMSET(hand)[frame]);
    e->posX.val = PLAYER.posX.val;
    e->posY.val = PLAYER.posY.val;
    PlaySfx(SFX_WEAPON_SWISH_A);
}

// Potions, with DRA's amounts (src/dra/7E4BC.c: GetStatusAilmentTimer adds the Bwaka knife's
// bonus), and food by its value (its ATK).
static void Use(s32 hand) {
    u32 id = g_Status.equipment[hand];
    s32 heal;

    switch (id) {
    case ITEM_POTION:
        heal = GetStatusAilmentTimer(STATUS_AILMENT_POTION, 50);
        break;
    case ITEM_HIGH_POTION:
        heal = GetStatusAilmentTimer(STATUS_AILMENT_HIGH_POTION, 100);
        break;
    case ITEM_ELIXIR:
        heal = g_Status.hpMax;
        break;
    case ITEM_MANNA_PRISM:
        g_Status.mp = g_Status.mpMax;
        PlaySfx(SFX_MAGIC_WEAPON_APPEAR_A);
        ReduceWeapon(hand);
        return;
    default:
        if (g_EquipDefs[id].itemCategory != ITEM_FOOD) {
            return;
        }
        heal = g_EquipDefs[id].attack;
    }
    g_Status.hp = g_Status.hp + heal < g_Status.hpMax ? g_Status.hp + heal : g_Status.hpMax;
    PlaySfx(SFX_HEALTH_PICKUP);
    ReduceWeapon(hand);
}

static bool Busy(void) {
    s32 i;
    for (i = SLOT_FIRST; i <= SLOT_LAST; i++) {
        if (g_Entities[i].entityId == E_OFFHAND) {
            return true;
        }
    }
    return false;
}

// Once per frame, before UpdateGame (the pads are this frame's).
void OffhandUpdate(void) {
    s32 hand;
    u8 c;

    if (g_GameState == Game_NowLoading) {
        s_HaveOwn = false;
    }
    if (!InPlay()) {
        s_PrevEngine = g_GameEngineStep;
        return;
    }
    if (!s_HaveOwn) {
        KeepOwn();
    }
    if (s_PrevEngine != Engine_Normal) { // the menu just closed: it loads the hands' weapons
        FixPalettes(0);
        FixPalettes(1);
    }
    s_PrevEngine = g_GameEngineStep;
    LoadWeapons();
    if (!(g_pads[0].tapped & PAD_CIRCLE) || Busy()) {
        return;
    }
    for (hand = 0; hand < 2; hand++) { // the right hand first, as Alucard's ○
        c = Category(hand);
        if (IsWeapon(c) && Loaded(hand) && s_Loading < 0) {
            Swing(hand);
            return;
        }
        if (c == ITEM_FOOD || (c == ITEM_MEDICINE && WeaponOvl(hand) == 0xFF)) {
            Use(hand);
            return;
        }
    }
}
