#ifndef BOSS_H
#define BOSS_H

void BossUpdate(void); // per frame, before the game's update
bool BossHere(void);   // a living boss is in this room
bool IsBossEnemy(u16 enemyId);
u16 BossSwitches(void); // aggro target switches so far
PfnEntityUpdate BossRealUpdate(const Entity* e); // the boss's own update, under the aggro wrapper

#endif
