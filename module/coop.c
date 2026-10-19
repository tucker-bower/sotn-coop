// SOTN Co-op per-frame entry point. M0: a heartbeat the harness asserts on.
#include <game.h>

bool DebugUpdate(void); // DRA; its result gates UpdateGame()

// Fixed layout the harness reads (harness/module.py): magic, version, frames since install.
typedef struct {
    u32 magic; // 'COOP'
    u32 version;
    u32 heartbeat;
} CoopState;

CoopState g_Coop = {0x504F4F43, 1, 0};

bool CoopMainLoop(void) {
    g_Coop.heartbeat++;
    return DebugUpdate();
}
