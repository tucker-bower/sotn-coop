// SOTN Co-op module entry. Same loading trick as tools/sotn-debugmodule (M0: proven path;
// M1 decides between this and a hook compiled into DRA):
// the module is shipped as the familiar overlay TT_000.BIN, which the game loads at 0x80170000.
// Its "servant init" copies the module to the 8MB expansion area and patches the main loop's
// call to DebugUpdate so it calls CoopMainLoop instead, every frame.
#include <game.h>

typedef struct {
    u32 fn[16];
} ServantDesc;

#define MODULE_ADDR 0x80280000U      // coop.ld
#define INJECT_MAIN_ADDR 0x80280040U // first function after the 0x40-byte header (coop.map)
#define LOAD_ADDR 0x80170000U        // where the game loads the familiar overlay
#define MODULE_SIZE 40960U           // size of the TT_000.BIN slot on disc
#define MAIN_LOOP_CALL 0x800E3D00U   // `jal DebugUpdate` in DRA's main loop (us)
#define JAL(addr) ((((u32)(addr) & 0x3FFFFFFU) >> 2) | 0x0C000000U)

static void Dummy(Entity* e) {}
void InjectMain(void);

// While still at LOAD_ADDR, the game calls fn[0] as the servant's Init.
ServantDesc g_ServantDesc __attribute__((section(".inject-head"))) = {{
    INJECT_MAIN_ADDR - (MODULE_ADDR - LOAD_ADDR), (u32)Dummy, (u32)Dummy, (u32)Dummy,
    (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy,
    (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy, (u32)Dummy,
}};

bool CoopMainLoop(void);
void FlushCache(void); // main.exe (PsyQ)

void __attribute__((section(".inject-func"))) InjectMain(void) {
    *(u32*)0x1F801060 |= 0xE00; // RAM_SIZE: expose 8MB
    __builtin_memcpy((void*)MODULE_ADDR, (void*)LOAD_ADDR, MODULE_SIZE);
    *(u32*)MAIN_LOOP_CALL = JAL(CoopMainLoop);
    // We just wrote code (the module copy and the patched call). Real hardware's instruction cache
    // and recompiling emulators (e.g. PCSX-Redux's dynarec) only see it after a flush.
    FlushCache();
}
