// On-screen co-op messages (playtest 1, D42): "Partner saved the game", "Revived by partner"...
//
// They use the game's own text box, the one an item's name shows in when it's picked up
// (BottomCornerText, in every stage overlay), on the right-hand side and in green, like the
// Faerie Scroll's enemy names, so they don't read as a pickup.
#define COOP_MODULE
#include <game.h>
#include "message.h"
#include "overlay_table.h"

#define MESSAGE_WAIT 600 // frames a message waits for the game to be able to show it

static const char* s_Pending;
static s32 s_Wait;
static u8 s_Text[64];

void CoopMessage(const char* text) {
    s_Pending = text;
    s_Wait = MESSAGE_WAIT;
}

static void Show(const char* text, bool onTop) {
    Primitive* prim;
    const OverlayInfo* ovl = FindOverlay(g_StageId);
    void (*bottomText)(u8* str, u8 leftAlign);
    s32 i;

    if (!ovl || !ovl->bottomText) {
        return;
    }
    // The 8x8 font's encoding: ASCII - 0x20, ended by 0xFF 0x00 (src/st/popup.h)
    for (i = 0; text[i] && i < LEN(s_Text) - 2; i++) {
        s_Text[i] = text[i] - 0x20;
    }
    s_Text[i++] = 0xFF;
    s_Text[i] = 0;
    if (g_unkGraphicsStruct.BottomCornerTextTimer) { // what the game does before a new one
        g_api.FreePrimitives(g_unkGraphicsStruct.BottomCornerTextPrims);
        g_unkGraphicsStruct.BottomCornerTextTimer = 0;
    }
    bottomText = (void*)ovl->bottomText;
    bottomText(s_Text, false);
    if (onTop && g_unkGraphicsStruct.BottomCornerTextPrims > 0) { // above a fade (0x1FD)
        for (prim = &g_PrimBuf[g_unkGraphicsStruct.BottomCornerTextPrims]; prim; prim = prim->next) {
            prim->priority += 0x10;
        }
    }
}

// Now, whatever the engine is doing (in play: a stage overlay is loaded). A stage load clears
// the text box (func_800F2404), so one left up never outlives its primitives.
void CoopMessageNow(const char* text) {
    if (g_GameState == Game_Play) {
        Show(text, true);
    } else {
        CoopMessage(text);
    }
}

void MessageUpdate(void) {
    if (!s_Pending) {
        return;
    }
    if (g_GameState == Game_Play && g_GameStep == Play_Default && g_GameEngineStep == Engine_Normal) {
        Show(s_Pending, false);
        s_Pending = NULL;
    } else if (--s_Wait <= 0) {
        s_Pending = NULL; // stale by now
    }
}
