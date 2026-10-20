// Solid entities for a shared room's guest (solid.c).
#ifndef SOLID_H
#define SOLID_H

#define SOLID_CALLS_MAX 48

typedef struct {
    u8 slot;  // stage slot (0..191)
    u8 flags; // GetPlayerCollisionWith's
    u16 w, h;
    u16 pad;
} SolidCall; // 8 bytes

u8 CoopPlayerCollision(Entity* self, u16 w, u16 h, u16 flags); // every overlay's, patched
void SolidRecord(bool on);                       // authority: record this frame's calls
s32 SolidTake(SolidCall* out, s32 room);         // into a snapshot; returns how many
void SolidApply(const SolidCall* calls, s32 n, const u8* mirrored); // guest, in its stage update

#endif
