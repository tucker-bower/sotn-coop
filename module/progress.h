// Shared progression (design/M2-shared-progression.md).
#ifndef PROGRESS_H
#define PROGRESS_H

void ProgressUpdate(void); // once per frame, before UpdateGame
bool ProgressEmit(u8 type, u16 a, u32 b); // queue an event for the partner
void ProgressDamageTaken(void); // once per frame, after every hit is known

#endif
