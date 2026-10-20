// VRAM uploads the stage makes on a shared room's authority, replayed on the guest (vram.c).
#ifndef VRAM_H
#define VRAM_H

#define VRAM_UPLOADS_MAX 0x2000 // bytes a frame (RECTs and pixels)

void VramPatch(void);            // once in play: LoadImage comes through the module
void VramRecord(bool on);        // authority: record this frame's stage uploads
s32 VramTake(u8* out, s32 room); // authority: move them into a snapshot; returns bytes
void VramApply(const u8* in, s32 size); // guest

#endif
