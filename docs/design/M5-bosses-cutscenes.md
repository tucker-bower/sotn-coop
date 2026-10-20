# M5 design: Bosses and cutscenes together

**Status:** proposal, awaiting Tucker's approval. Build after M4b.
**Context:** D24 (dead stays dead during a boss fight), D25 (bosses have 2× HP and pull the partner in), D26 (cutscenes together), D47 (aggro switching), playtest 1 (Doppleganger in the Outer Wall didn't pull P1 in).

## Goal
- When either player enters a boss room, the partner is teleported in, and both fight the same boss.
- The boss has 2× HP and switches targets between players.
- A player who dies stays dead until the boss falls, then respawns next to the survivor.
- Story cutscenes are watched by both, and count for both.

## Part 1: noticing a boss fight
- Boss rooms are listed in DRA's `g_RoomBossTeleports`, right after the stage teleport table. A boss fight runs its own overlay (`BO*`/`RBO*`) once you're inside.
- Presence gains a **BOSS** flag: the stage is a boss overlay, or the room is a boss-teleport room.
- **Pull-in:** when the partner sees BOSS, it Arrives at the boss-entering player's spot (M3's Arrive). The guest of a shared room becomes the guest of the boss room.
- **Not available:** inside a boss room, ✕ on the map can't leave, and the partner can't be teleported elsewhere.

## Part 2: one boss, both players
- The boss room is an M4 shared room, and the boss is a stage entity there. The player who entered first is the authority. The boss is mirrored to the other player, hits are relayed, and the boss's attacks hurt both.
- **2× HP:** when a boss entity first appears in the authority's game, the module doubles its `hitPoints` (and its parts', for bosses made of several entities). A per-boss table comes from the boss overlays' enemy definitions.
- **Aggro (D47):**
  - Bosses get the M4 targeting patch (all boss overlays are already in the table), but with a **sticky target** instead of "the nearer player".
  - After each boss attack, there's a 50% chance the target switches. An "attack" is the boss entering an attack step; the step lists are per boss and generated or hand-written, starting with the bosses on the test route.
  - The switch chance is a launcher setting, so it can be tuned in playtests.
  - Bosses that read the player directly need per-boss patches, listed in a report.

## Part 3: death in a boss fight (D24)
- A player who dies in a boss fight plays the death animation, then stays down: hidden, with no input, and the partner sees a marker.
- When the boss dies (its defeated flag is set), the fallen player respawns next to the survivor.
- If both die, both reload the joint save. This uses the M4b both-dead rules.

## Part 4: cutscenes (D26)
- When a cutscene starts in one game (a `g_CutsceneHasControl` rising edge, or a cutscene entity starting), the partner is pulled into that room, and its own copy of the cutscene runs. Both have the same flags, so it plays identically.
- **Credit:** the flags are already shared (M2).
- **While the cutscene runs:** the puppet is hidden, the partner can't be teleported to, and the shared-room freeze applies.

## Acceptance criteria (two-game harness tests, plus one manual)
1. **Pull-in:** A walks into the Doppleganger room (Outer Wall), the boss on the test route. B arrives inside within 5 s.
2. **2× HP:** the boss's HP in both worlds is twice the retail value. Regular enemies are unchanged.
3. **Both damage the boss.** It dies once, and its defeat flag is shared.
4. **Aggro:** over 60 boss attacks, the target switches about half the time (between 20 and 40 switches), and both players get attacked.
5. **Death mid-fight:** A dies and stays down. B kills the boss. A respawns next to B with full HP. If both die, both reload the joint save.
6. **Cutscene:** a story cutscene on the route starts for A. B is pulled in and sees it too, and the flags match afterwards.
7. **Manual (Tucker):** the Doppleganger fight, and the first cutscene, in the launcher.

## Risks
- **Multi-part bosses,** and bosses that keep state outside entities: the mirroring may miss parts. Mitigation: mirror the boss overlay's BSS too (already done for stages), and a per-boss check.
- **Aggro hooks are per boss.** Start with the route's bosses and widen in later milestones.
- **Bosses with scripted intros** may break when the partner arrives mid-intro. Mitigation: the pull-in waits until the intro ends.

## Implementation notes (built 2026-10-19, after Tucker approved the design)
- **Boss detection** (`module/boss.c`) is by enemy definition, not by stage: 31 boss `enemyId`s. Slogra and Gaibon fight in an ordinary stage, and `MAR` is a boss *overlay* that holds a cutscene. `PRESENCE_BOSS` means a living boss is in the room.
- **2× HP:** the module doubles those entries of the in-RAM enemy table while a partner's game has been heard from in the last 10 s, and never mid-fight (D61).
- **Aggro:** each boss's update is wrapped (D62).
  - While the target is the partner, `PLAYER`'s position and facing (and `g_PlayerX/Y`) are swapped for the partner's during the boss's update. That works for every boss, including the ones that never call the targeting helpers.
  - The target re-rolls (50%) when the boss's `step` changes, at least 2 s after the last roll.
  - Snapshots carry the boss's real update function, never the wrapper.
- **Boss kills:** the time-attack records (and their "visited" bits), which the boss-room teleport checks, are shared like the castle flags (`EV_RECORD`).
- **Pull-in** (`module/arrive.c`): once per fight, when the partner's presence shows `BOSS` and the partner isn't busy, so not mid-intro. Cutscenes pull the partner in the same way, once per cutscene, on `PRESENCE_CUTSCENE` (`g_CutsceneHasControl`). The arriving game runs its own copy of the scene.
- **Death in a boss fight:** the usual fade to black, then the player stays down with "Partner fights on alone" while the partner's presence shows `BOSS`, then respawns at the partner. If both are down, the joint-save reload applies.
- **Tests:** `harness/session_m5.py`.
