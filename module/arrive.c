// Putting a player somewhere, and what builds on it: teleport, respawn, the shared-room pause
// freeze, and joint saves (design/M3-teleport-respawn-save.md).
//
// Arrive(stage, room, x, y) uses the game's own door transition: one entry of the stage
// teleport table D_800A245C is borrowed, filled with the target, and selected through
// D_8006C374; then Play_PrepareNextStage loads the stage if needed, places the player on the
// right screen of the room, starts the music and the familiar, exactly as a door would.
#define COOP_MODULE
#include <game.h>
#include <sfx.h>
#include "arrive.h"
#include "boss.h"
#include "message.h"
#include "link.h"

extern RoomTeleport D_800A245C[]; // DRA: stage teleports (doors between stages)
extern RoomLoadDef* D_801375BC;   // DRA: the current room's RoomLoadDef (first member)
void HideMap(void);
s32 ApplySaveData(SaveData* save);
void StoreSaveData(SaveData* save, s32 block, s32 cardIcon);
void SetGameState(GameState gameState);
void PlaySfx(s32 sfxId);
void SetFadeMode(FadeModes fadeMode);
void UpdateFade(bool skipFollowup);
s32 func_801025F4(void); // the fade's progress: nonzero once a fade to black is complete

// The save room's memory card state machine (src/dra/62DEC.c, static: called by address; the
// size-neutral hooks keep DRA's addresses identical to retail's). State 6 = saved, 7-11 = errors.
#define SaveCardReset ((void (*)(void))0x80103EAC)
#define SaveCardStep ((void (*)(void))0x80103ED4)
#define SAVE_CARD_OK 6
extern s32 D_80137E4C;  // its state
extern s32 D_80137E54;  // its mode (0: save to D_8006C378)
extern s32 D_80097924;  // memory card port
extern s32 D_8006C378;  // memory card block
extern bool D_80137598; // the player is in a save room
extern s32 D_801379BC;  // the save room's own sequence: 0 = idle (by the coffin, not saving)
#define MENU_STEP_INIT 0 // src/dra/menu.h (first value of the menu step enum)
// Entry 7: Play_LoadStageChr reloads the target stage's tile graphics only for a few entries
// (src/dra/game_handlers.c), and 7 is one. A normal door gets them from the CD room on the way.
#define BORROWED_TELEPORT 7
#define ARRIVE_TIMEOUT 600    // frames to get back into play before giving up

typedef enum { ARRIVE_IDLE, ARRIVE_PENDING, ARRIVE_LOADING } ArriveState;

static ArriveState s_State;
static u16 s_Stage, s_RoomId;
static s16 s_X, s_Y;
static u16 s_Timer;
static RoomTeleport s_Saved;

// Respawn and both-dead state
static bool s_WaitingForHost; // dead, partner dead too: the host decides (reload or Game Over)
static s32 s_DeathFade;       // frames into the fade to black before a respawn
#define DEATH_FADE_MAX 180    // the slow fade takes 128 frames
static bool s_AllowGameOver;
static bool s_SaveLoaded; // a save was applied: clear the load mode once back in play
static s32 s_BusyWait;    // dead, waiting for a busy partner to become reachable
#define PARTNER_BUSY_WAIT 1800 // then the game's own Game Over (the partner seems stuck)
static bool s_DownForBoss; // dead while the partner fights a boss: respawn once it's over (D24)

// Pulled into the partner's boss fight / cutscene (design/M5): once per fight or cutscene
static bool s_BossPulled, s_CutscenePulled;

// The partner saved at a save room: this game writes its own memory card save for the same
// save room, through the game's own card code, frozen while it does (D46, D49).
static bool s_CardSaving;
static CoopCommand s_CardCmd;
static s32 s_PrevPort, s_PrevBlock;

static bool InNormalPlay(void) {
    return g_GameState == Game_Play && g_GameStep == Play_Default;
}

static bool IsPausedEngine(s32 step) {
    return step == Engine_Menu || step == Engine_Map || step == Engine_0x70;
}

static bool PartnerFresh(void) {
    return g_CoopLink.partnerAge <= 30 && (g_CoopLink.partner.flags & PRESENCE_IN_PLAY);
}

static bool PartnerReachable(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return PartnerFresh() && !(p->flags & (PRESENCE_BUSY | PRESENCE_DEAD)) &&
           p->character == g_PlayableCharacter;
}

static bool SameRoomAsPartner(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top;
}

static bool PartnerInBossFight(void) {
    return PartnerFresh() && (g_CoopLink.partner.flags & PRESENCE_BOSS) &&
           !(g_CoopLink.partner.flags & PRESENCE_DEAD);
}

u16 CurrentRoomId(void) {
    if (!D_801375BC || !g_api.o.rooms) {
        return 0;
    }
    return (u8*)D_801375BC - 4 - (u8*)g_api.o.rooms; // RoomHeader is {left, top, right, bottom, load}
}

bool ArriveBusy(void) { return s_State != ARRIVE_IDLE; }

static const char* s_ArriveText; // shown once arrived (with a flash: Richter's Cross Crash fade)

void Arrive(u16 stage, u16 roomId, s16 x, s16 y) {
    s_ArriveText = NULL;
    s_Stage = stage;
    s_RoomId = roomId;
    s_X = x;
    s_Y = y;
    s_Timer = 0;
    s_State = ARRIVE_PENDING;
}

static void ArriveStart(void) {
    RoomTeleport* tele = &D_800A245C[BORROWED_TELEPORT];
    RoomHeader* room;
    s32 width, height;

    s_Saved = *tele;
    tele->x = s_X;
    tele->y = s_Y;
    if (s_Stage & STAGE_INVERTEDCASTLE_FLAG) {
        // The game mirrors teleport positions in the inverted castle (func_800F14CC): pre-mirror.
        // Its rooms aren't loaded yet, so use the room header from our own copy of the target:
        // the partner's room offset indexes the same table once the stage is loaded, and the
        // fine placement after arrival corrects anything this gets wrong.
        room = (RoomHeader*)((u8*)g_api.o.rooms + s_RoomId);
        width = ((room->right - room->left) + 1) << 8;
        height = ((room->bottom - room->top) + 1) << 8;
        if (s_Stage == g_StageId) {
            tele->x = width - s_X;
            tele->y = height - s_Y;
        }
    }
    tele->roomId = s_RoomId;
    tele->unk6 = g_StageId;
    tele->stageId = s_Stage;
    if (g_GameEngineStep == Engine_Map) { // teleporting from the map screen
        D_800974A4 = 0;
    }
    HideMap();
    g_GameEngineStep = Engine_Normal;
    D_8003C730 = 0;
    D_8006C374 = BORROWED_TELEPORT;
    g_GameStep = Play_PrepareNextStage;
    s_State = ARRIVE_LOADING;
}

// First frame back in play: put the table entry back, then move the player to the exact spot.
// The door path already put the camera on the right screen, so this is a small move.
static void ArriveFinish(void) {
    s32 dx, dy;

    D_800A245C[BORROWED_TELEPORT] = s_Saved;
    dx = s_X - (PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi);
    dy = s_Y - (PLAYER.posY.i.hi + g_Tilemap.scrollY.i.hi);
    if (dx > -256 && dx < 256 && dy > -256 && dy < 256) {
        PLAYER.posX.i.hi += dx;
        PLAYER.posY.i.hi += dy;
    }
    s_State = ARRIVE_IDLE;
    if (s_ArriveText) {
        CoopMessage(s_ArriveText);
        SetFadeMode(FADE_NONE); // the screen flashes as the player appears
    }
}

static void ArriveUpdate(void) {
    switch (s_State) {
    case ARRIVE_IDLE:
        break;
    case ARRIVE_PENDING:
        if (InNormalPlay() && !g_IsUsingCd &&
            (g_GameEngineStep == Engine_Normal || g_GameEngineStep == Engine_Map)) {
            ArriveStart();
        } else if (++s_Timer > ARRIVE_TIMEOUT) {
            s_State = ARRIVE_IDLE;
        }
        break;
    case ARRIVE_LOADING:
        if (InNormalPlay() && g_GameEngineStep == Engine_Normal) {
            ArriveFinish();
        } else if (++s_Timer > ARRIVE_TIMEOUT) {
            D_800A245C[BORROWED_TELEPORT] = s_Saved;
            s_State = ARRIVE_IDLE;
        }
        break;
    }
}

// --- teleport: ✕ on the map screen goes to the partner

static void TeleportInput(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    if (!InNormalPlay() || g_GameEngineStep != Engine_Map || !(g_pads[0].tapped & PAD_CROSS) ||
        ArriveBusy()) {
        return;
    }
    if (BossHere()) { // no running from a boss fight (design/M5)
        PlaySfx(SFX_UI_ERROR);
        CoopMessage("Can't leave a boss fight");
        return;
    }
    if (!PartnerReachable()) {
        PlaySfx(SFX_UI_ERROR);
        CoopMessage("Partner out of reach");
        return;
    }
    PlaySfx(SFX_UI_CONFIRM);
    Arrive(p->stage, p->roomId, p->groundX, p->groundY);
    s_ArriveText = "Joined partner";
}

// --- death: respawn at the partner instead of Game Over (D24)

static void Revive(void) {
    g_Status.hp = g_Status.hpMax;
    g_Status.mp = g_Status.mpMax;
    // DEAD while dying; UNK80000 when the death animation is over and the engine goes to
    // Engine_10 (src/dra/5087C.c).
    g_Player.status &= ~(PLAYER_STATUS_DEAD | PLAYER_STATUS_UNK80000);
    g_GameEngineStep = Engine_Normal; // Arrive's stage load re-initializes the player entity
    g_MenuStep = MENU_STEP_INIT;
}

// Returns false to hold this frame's game update (dead, waiting for the host).
static bool DeathUpdate(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    if (g_GameState != Game_Play || g_GameEngineStep != Engine_10 ||
        g_MenuStep != MENU_STEP_INIT) {
        s_WaitingForHost = false;
        s_AllowGameOver = false;
        s_BusyWait = 0;
        s_DeathFade = 0;
        s_DownForBoss = false;
        return true;
    }
    // Engine_10 at MENU_STEP_INIT: this frame's update would start the Game Over.
    if (s_AllowGameOver || !PartnerFresh() || g_StageId == STAGE_ST0) {
        return true; // playing alone, the prologue, or the host said so: the game's own Game Over
    }
    if (!(p->flags & PRESENCE_DEAD)) {
        // First the screen fades to black (playtest 1: it used to cut straight to the load,
        // which looked like a freeze). The game is held meanwhile, so run the fade here.
        if (s_DeathFade < DEATH_FADE_MAX) {
            if (!s_DeathFade++) {
                SetFadeMode(FADE_TO_BLACK_SLOW);
            }
            UpdateFade(true);
            if (!func_801025F4()) {
                return false;
            }
            s_DeathFade = DEATH_FADE_MAX;
        }
        // The partner is fighting a boss: stay down until it's over (D24).
        if (PartnerInBossFight()) {
            if (!s_DownForBoss) {
                s_DownForBoss = true;
                CoopMessageNow("Partner fights on alone");
            }
            return false;
        }
    }
    if (!(p->flags & PRESENCE_DEAD) && PartnerReachable()) {
        s_DeathFade = 0;
        s_DownForBoss = false;
        Revive();
        Arrive(p->stage, p->roomId, p->groundX, p->groundY);
        s_ArriveText = "Revived by partner";
        // Start loading in this same frame: one more frame of the dying player entity would
        // set the death bits (and Engine_10) again. The load replaces the entity.
        ArriveUpdate();
        return true;
    }
    if (!(p->flags & PRESENCE_DEAD)) {
        // The partner is alive but busy (loading, a cutscene): wait for them a little, then
        // give up. Holding forever froze the game (playtest 1).
        if (++s_BusyWait > PARTNER_BUSY_WAIT) {
            s_BusyWait = 0;
            return true;
        }
        return false;
    }
    s_WaitingForHost = true; // both dead: hold until the host decides (reload, or Game Over)
    return false;
}

// --- boss fights and cutscenes: the partner is pulled in (design/M5)

static bool CanBePulled(void) {
    return InNormalPlay() && g_GameEngineStep == Engine_Normal && !ArriveBusy() &&
           !(g_Player.status & PLAYER_STATUS_DEAD) && !g_CutsceneHasControl && !SameRoomAsPartner() &&
           !s_CardSaving && !D_80137598;
}

static void PullIn(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    if (!PartnerInBossFight()) {
        s_BossPulled = false;
    } else if (!s_BossPulled && CanBePulled() && !(p->flags & PRESENCE_BUSY)) { // not mid-intro
        s_BossPulled = true;
        Arrive(p->stage, p->roomId, p->groundX, p->groundY);
        s_ArriveText = "Partner is fighting a boss!";
        return;
    }
    if (!PartnerFresh() || !(p->flags & PRESENCE_CUTSCENE) || (p->flags & PRESENCE_DEAD) ||
        p->stage == STAGE_ST0) {
        s_CutscenePulled = false;
    } else if (!s_CutscenePulled && CanBePulled()) {
        // The partner is busy (the cutscene has control): arrive anyway. This game runs its
        // own copy of the scene; the flags it sets are shared, so it plays out the same.
        s_CutscenePulled = true;
        Arrive(p->stage, p->roomId, p->groundX, p->groundY);
    }
}

// --- commands from the host

static void LoadSave(void) {
    ApplySaveData((SaveData*)g_CoopLink.saveIn);
    D_8003C730 = 1; // as after loading a memory card save: keep the saved status
    g_GameEngineStep = Engine_Init;
    SetGameState(Game_NowLoading);
    g_GameStep = 2;
    s_WaitingForHost = false;
    s_SaveLoaded = true;
}

// Without a card (or if it fails before the save is built), still post a save for session.coop.
static void SaveToLinkOnly(const CoopCommand* c) {
    SaveData* save = (SaveData*)g_CoopLink.saveOut;

    StoreSaveData(save, 0, 0);
    save->info.stage = c->stage; // resume where the partner saved
    save->info.roomX = c->x;
    save->info.roomY = c->y;
    g_CoopLink.saveSeq++;
}

static void CardSaveStart(void) {
    s_PrevPort = D_80097924;
    s_PrevBlock = D_8006C378;
    D_80097924 = 0; // this game's own card, in slot 1
    D_8006C378 = s_CardCmd.roomId;
    D_80137E54 = 0;
    SaveCardReset();
    s_CardSaving = true;
}

// One step per frame, with the game frozen. Returns true when finished.
static bool CardSaveStep(void) {
    u32 seq = g_CoopLink.saveSeq;

    SaveCardStep();
    if (D_80137E4C < SAVE_CARD_OK) {
        return false;
    }
    g_CoopLink.cardResult = D_80137E4C;
    CoopMessage(D_80137E4C == SAVE_CARD_OK ? "Game saved" : "Saved; memory card error");
    if (D_80137E4C != SAVE_CARD_OK && g_CoopLink.saveSeq == seq) {
        SaveToLinkOnly(&s_CardCmd); // never got as far as building the save
    }
    D_80097924 = s_PrevPort;
    D_8006C378 = s_PrevBlock;
    s_CardSaving = false;
    return true;
}

static void CommandUpdate(void) {
    const CoopCommand* c = &g_CoopLink.cmd;

    if (c->seq == g_CoopLink.cmdDone) {
        return;
    }
    switch (c->type) {
    case CMD_ARRIVE:
        if (!InNormalPlay()) {
            return; // retry next frame
        }
        Arrive(c->stage, c->roomId, c->x, c->y);
        break;
    case CMD_LOAD_SAVE:
        if (g_GameState != Game_Play && g_GameState != Game_Title && g_GameState != Game_MainMenu) {
            return;
        }
        LoadSave();
        break;
    case CMD_SAVE_NOW:
        // In a menu or on the map, or this game is saving at a coffin itself: wait. Just standing
        // in a save room is fine (both players often are: the partner saving there used to wait
        // until this one left).
        if (!InNormalPlay() || g_GameEngineStep != Engine_Normal || (D_80137598 && D_801379BC != 0) ||
            s_CardSaving) {
            return;
        }
        s_CardCmd = *c;
        g_CoopLink.cardResult = 0;
        CardSaveStart();
        CoopMessage("Partner is saving"); // this game freezes while its card is written
        break;
    case CMD_GAME_OVER:
        s_AllowGameOver = true;
        break;
    }
    g_CoopLink.cmdDone = c->seq;
}

// --- the 5th DRA hook: saving at a save room (StoreSaveData in src/dra/62DEC.c)

void CoopSaveRoomStore(SaveData* save, s32 block, s32 cardIcon) {
    StoreSaveData(save, block, cardIcon);
    if (s_CardSaving) { // the partner's save: resume in the partner's save room
        save->info.stage = s_CardCmd.stage;
        save->info.roomX = s_CardCmd.x;
        save->info.roomY = s_CardCmd.y;
    }
    __builtin_memcpy(g_CoopLink.saveOut, save, SAVE_DATA_SIZE);
    g_CoopLink.saveBlock = block;
    g_CoopLink.saveSeq++;
}

// --- presence additions and the shared-room pause

void ArrivePresence(CoopPresence* p) {
    p->flags &= ~(PRESENCE_PAUSED | PRESENCE_BUSY | PRESENCE_DEAD);
    if (!(p->flags & PRESENCE_IN_PLAY)) {
        p->flags |= PRESENCE_BUSY;
        return;
    }
    p->roomId = CurrentRoomId();
    if (g_Player.vram_flag & 1) { // touching the floor
        p->groundX = p->x;
        p->groundY = p->y;
    }
    if (IsPausedEngine(g_GameEngineStep)) {
        p->flags |= PRESENCE_PAUSED;
    }
    // Only a death in normal play counts: not the prologue (it plays out solo), not a load.
    if (g_StageId != STAGE_ST0 && g_GameStep == Play_Default &&
        (g_GameEngineStep == Engine_10 || (g_Player.status & PLAYER_STATUS_DEAD) || s_WaitingForHost)) {
        p->flags |= PRESENCE_DEAD;
    }
    if (g_GameStep != Play_Default || ArriveBusy() || g_CutsceneHasControl ||
        g_StageId == STAGE_ST0 ||
        !(g_GameEngineStep == Engine_Normal || IsPausedEngine(g_GameEngineStep))) {
        p->flags |= PRESENCE_BUSY;
    }
}

// Once per frame, before UpdateGame. Returns false to skip this frame's game update.
bool ArriveFrame(void) {
    // Mode 1 (D_8003C730) places the player for a save load; only a save room's own code
    // clears it, and left set every later door would place the player the same way.
    if (s_SaveLoaded && InNormalPlay() && g_GameEngineStep == Engine_Normal) {
        D_8003C730 = 0;
        s_SaveLoaded = false;
    }
    if (s_CardSaving) {
        CardSaveStep();
        return false; // frozen while this game's card is written (D49)
    }
    CommandUpdate();
    TeleportInput();
    PullIn();
    ArriveUpdate();
    if (!DeathUpdate()) {
        return false;
    }
    // Shared-room pause: the partner is in their menu in my room, so my world waits too.
    if (InNormalPlay() && g_GameEngineStep == Engine_Normal && !ArriveBusy() && PartnerFresh() &&
        (g_CoopLink.partner.flags & PRESENCE_PAUSED) && SameRoomAsPartner()) {
        return false;
    }
    return true;
}
