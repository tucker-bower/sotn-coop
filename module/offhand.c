// Off-hand weapons for Richter and Maria (D105, design/M12b): ○ uses what's in a hand.
//
// Richter keeps his whip and Maria her guardians. In Alucard's equip menu they put any weapon,
// food or potion in a hand, and ○ uses it:
// - a weapon works exactly as in Alucard's hands: its own overlay's code, sprites, hitboxes and
//   specials, timed by Alucard's own attack animation run on a virtual Alucard (see below);
// - potions heal as Alucard's do (Potion, High potion, Elixir, Manna prism: DRA's amounts),
//   and food heals by its value, at once. The other potions (resists, stats): not yet;
// - shields only add their DEF (the equipment totals do that); thrown items: not yet.
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
Entity* CreateEntFactoryFromEntity(Entity* source, u32 factoryParams, s16 arg2);
void EntityFactory(Entity* self);
void PlayAnimation(s8* frameProps, AnimationFrame** frames);
extern s8 D_800B0130[];              // Alucard's animation frame properties (src/dra/692E8.c)
extern AnimationFrame* D_800B01B8[]; // ...and his animations
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
#define WBANK 0x17 // the weapon's sprites (stage sprite bank 0x17 is free; Richter uses 0x10-0x13, familiars 0x14, Maria 0x10-0x16)

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

bool OffhandLoading(void) { return s_Loading >= 0; }

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
            g_LoadFile == CdFile_None && LoadWeaponPrg(hand)) {
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

// --- D105: the weapon's own overlay, as for Alucard (design/M12b) ----------------------------
// ○ starts what Alucard's attack starts (src/dra/6E42C.c): the weapon's blueprint through DRA's
// factory, whose children (0xE0+ / 0xF0+) Richter's and Maria's entity loops send here. Alucard's
// attack animation runs on a virtual Alucard (s_Alu), advanced by DRA's PlayAnimation; while a
// weapon entity updates, PLAYER's animation is that one, so the overlay draws, times and hits as
// in Alucard's hands. Richter's or Maria's own body is untouched.
static Entity s_Alu;
static bool s_Swinging;
static u16 s_Unk46;
static bool s_Grounded; // the swing started on the ground

static void AluSwing(s32 hand) {
    u32 item = g_Status.equipment[hand];
    Equipment* eq = &g_EquipDefs[item];
    Entity* f;
    Entity* cur = g_CurrentEntity;

    f = CreateEntFactoryFromEntity(&PLAYER, FACTORY(eq->unk13 + ((hand + 1) << 12),
                                                    ((eq->unk14 & 0x7F) + (hand << 7))), item);
    if (!f) {
        return;
    }
    __builtin_memset(&s_Alu, 0, sizeof(s_Alu));
    s_Grounded = g_Player.vram_flag & 1;
    s_Alu.ext.player.anim = eq->playerAnim + (s_Grounded ? 0 : 4); // in the air: his jump swing
    s_Unk46 = eq->unk11 + 0x7FFF + 2;
    s_Swinging = true;
    s_Hand = hand;
    g_CurrentEntity = &s_Alu; // DRA advances Alucard's animation in the frame of the press too
    PlayAnimation(D_800B0130, D_800B01B8);
    // Their loops take entity 1 (E_FACTORY) as their own factory while its step is 0: DRA's
    // starts now, so it keeps DRA's update.
    g_CurrentEntity = f;
    EntityFactory(f);
    f->pfnUpdate = EntityFactory;
    g_CurrentEntity = cur;
    ReduceWeapon(hand);
}

static void AluAnimate(void) {
    Entity* cur = g_CurrentEntity;

    if (!s_Swinging) {
        return;
    }
    // As Alucard: on the ground, no walking or turning until the swing ends (his attack step)
    if (s_Grounded) {
        g_pads[0].pressed &= ~(PAD_LEFT | PAD_RIGHT);
        g_pads[0].tapped &= ~(PAD_LEFT | PAD_RIGHT);
    }
    g_CurrentEntity = &s_Alu;
    PlayAnimation(D_800B0130, D_800B01B8);
    g_CurrentEntity = cur;
    if (s_Alu.poseTimer < 0) {
        s_Swinging = false;
    }
}

void CoopWeaponEntity(Entity* self) {
    s32 hand = self->entityId >= 0xF0;
    PfnEntityUpdate fn = ((PfnEntityUpdate*)WEAPON_PRG(hand))[self->entityId - (hand ? 0xF0 : 0xE0)];
    SpriteParts** banks = (SpriteParts**)g_api.o.spriteBanks;
    SpriteParts* own[4];
    u8 anim = PLAYER.ext.player.anim;
    u16 pose = PLAYER.pose;
    s16 timer = PLAYER.poseTimer;
    u16 unk46 = g_Player.unk46;
    u16 drawFlags = PLAYER.drawFlags;
    s16 scaleY = PLAYER.scaleY;
    s32 i, set;

    for (i = 0; i < 4; i++) {
        own[i] = banks[0x10 + i];
    }
    if (s_Swinging) {
        PLAYER.ext.player.anim = s_Alu.ext.player.anim;
        PLAYER.pose = s_Alu.pose;
        PLAYER.poseTimer = s_Alu.poseTimer;
        g_Player.unk46 = s_Unk46;
        PLAYER.drawFlags = 0; // the overlay copies these: Alucard's, not Richter's or Maria's
        PLAYER.scaleY = 0x100;
    } else {
        g_Player.unk46 = 0; // the swing is over: the weapon's entities end themselves
    }
    fn(self);
    set = self->animSet & 0x7FFF;
    if (self->entityId && (self->animSet & ANIMSET_OVL_FLAG) && set >= 0x10 && set < 0x14) {
        banks[WBANK] = banks[set]; // the overlay put its sprites in a body bank: ours instead
        self->animSet = ANIMSET_OVL(WBANK);
    }
    if (self->entityId && !(self->palette & PAL_UNK_FLAG) && self->palette >= PAL_WEAPONS &&
        self->palette < PAL_WEAPONS + N_PAL && s_Slot[hand] >= 0) {
        self->palette = PAL_UNK_FLAG | s_Slot[hand]; // the player's own palettes are there
    }
    for (i = 0; i < 4; i++) {
        banks[0x10 + i] = own[i];
    }
    PLAYER.ext.player.anim = anim;
    PLAYER.pose = pose;
    PLAYER.poseTimer = timer;
    g_Player.unk46 = unk46;
    PLAYER.drawFlags = drawFlags;
    PLAYER.scaleY = scaleY;
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
    AluAnimate();
    if (!(g_pads[0].tapped & PAD_CIRCLE) || s_Swinging) {
        return;
    }
    for (hand = 0; hand < 2; hand++) { // the right hand first, as Alucard's ○
        c = Category(hand);
        if (IsWeapon(c) && Loaded(hand) && s_Loading < 0) {
            AluSwing(hand);
            return;
        }
        if (c == ITEM_FOOD || (c == ITEM_MEDICINE && WeaponOvl(hand) == 0xFF)) {
            Use(hand);
            return;
        }
    }
}
