// Mist Step: Richter and Maria through mist grates (design/M8b §3.1, mist.c).
#ifndef MIST_H
#define MIST_H

void MistStepUpdate(void); // once per frame, before UpdateGame
bool MistStepHidden(void); // the player isn't drawn this frame
void MistStepAfter(void);  // after the frame's update (RenderEntities hook)

#endif
