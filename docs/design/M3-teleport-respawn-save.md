# M3 design: Teleport, respawn, pause rules, joint save

**Status:** approved 2026-10-18. Save files may live in the launcher (D36), and save + resume must be in the test suite (criterion 7).
**Budget:** 11% of the month (now includes the joint save, moved from M2). Target: 2026-10-30.
**Context:** D24 (death), D30 (teleport, pause), D31 (joint save), M1/M2 designs.

## Goal
- A player can jump to their partner from the map screen.
- A player who dies reappears next to their partner instead of getting Game Over.
- Pausing in a room both players share freezes that room for both.
- Saving in either game saves both, and a session can be resumed later. If both players are dead at once, both go back to that save.

The boss-fight exception to respawning (the dead player waits until the boss dies) needs boss detection, so it lands with bosses in M5.

## Part 1: one way to put a player somewhere
Teleport, respawn, resume and (in M5) the boss pull-in all reduce to **Arrive(stage, room, x, y)**.

| Option | Idea | Verdict |
|---|---|---|
| **A. The game's own in-play stage load** | Set `g_StageId` and the room cell (`g_Tilemap.left/top`), then `D_8003C730 = 1` and `g_GameStep = Play_PrepareNextStage`. That's the sequence DRA itself uses to apply a save and jump (the end of a demo, `src/dra/5087C.c`). It loads the stage overlay if the stage differs, builds the room and places the player at (0x80, 0xA4) in its first screen. On the first frame in play, the module moves the player to the exact target and snaps the camera. | ✅ **Recommended.** It's the game's own path, keeps the player's status, and works across stages and into the inverted castle. |
| B. The debug-module warp (`Game_NowLoading`) | What the harness uses | ❌ Outside NO3 it applies a debug loadout (`InitStatsAndGear`). The harness has to patch around that. |
| C. A RAM transplant from a snapshot | Copy state | ❌ It drags the partner's world state along. |

- **Landing spot:** the partner's position, if they're standing on ground. Otherwise their last grounded position, which the module tracks and adds to `CoopPresence`.
- **Where you can't teleport to:** a partner who's loading, in a cutscene, or in the prologue. You then get "Partner busy" and nothing happens.
- **Bosses:** teleporting into a boss room is allowed, and M5 decides the auto pull-in.

## Part 2: teleport UI
Teleport is **✕ on the map screen.**
- The map screen is a pause screen that already shows the partner's cursor (M1).
- Only Start and Select are used there (`src/dra/5087C.c`, `Engine_Map`), so ✕ is free.
- A one-line prompt ("✕ Go to partner") is drawn in the debug font while the partner is reachable.

This is easier and less risky than adding a pause-menu entry. The menu is DRA code, and DRA can't grow (D33).

## Part 3: death and respawn
Death plays its normal animation, and then the engine enters `Engine_10`. Its first step calls `SetGameState(Game_GameOver)`.
- The module already runs before `UpdateGame` every frame. When it sees `Engine_10` at `MENU_STEP_INIT` and the partner is in play:
  1. it revives the player (clears the dead status, sets HP to max, returns the engine to `Engine_Normal`);
  2. it Arrives at the partner.
- This needs no new DRA hook.
- The player who died still sees their death animation, then appears next to the partner ("oh hi Mike").
- **Both dead** (the partner is also in `Engine_10` or Game Over): both games reload the last joint save (part 5) through the same Arrive path.
- **Boss exception (D24):** the hook point is the same, and M5 adds the condition.

## Part 4: pause rules
Pausing works as normal in each game. The new rule covers the shared room.
- `CoopPresence` gains a **paused** bit (the engine is in the menu, the map, or the status-pause step).
- If the partner is paused **and in my room**, my `UpdateHook` returns 0. DRA then skips `UpdateGame`: the world freezes and keeps being drawn, and "PARTNER PAUSED" shows in the debug font.
- It unfreezes when the partner resumes.
- Pausing in different rooms has no effect.
- No deadlock: a frozen game isn't "paused", so two players can't freeze each other.

## Part 5: joint save and resume

| Option | Idea | Verdict |
|---|---|---|
| **A. Host-managed session file** | When either player saves at a save room, both modules build a `SaveData` in RAM with the game's own `StoreSaveData`. The partner's copy is re-pointed to the saver's save room. Both hosts write `session.coop` with both saves plus the merged shared state from M2. Resume and the both-dead reload `ApplySaveData` in each game, then Arrive. | ✅ **Recommended.** No memory-card writes in the middle of play, and the same on every emulator. Each player's normal card save still happens too, so the game works single-player as before. |
| B. Also write the partner's save to their memory card | The partner's game writes its card through the game's card code, so "Load game" works in both | Later, maybe. It means card I/O in the middle of play, and per-emulator card files. |

- **Detecting a save:** the save-room code calls `StoreSaveData` directly from DRA (`src/dra/62DEC.c`), so it gets a **5th size-neutral hook**, `StoreSaveData → CoopStoreSaveData` (D33). The hook calls the original, then posts the save to the outbox.
- **Resume:** both games boot to the title, and the launcher (the harness for now) offers "Continue co-op". Each module applies its save and enters play the way the file-select screen does after loading a card (a spike checks the exact steps in `src/st/sel`). Both players start in the saver's save room, side by side.
- **Which save:** the most recent joint save. Each save also stays on its saver's memory card as a normal single-player save.

## Defaults (reversible, logged when built)
- Teleport is ✕ on the map. There's no cooldown, and the load fade plays as for any room change.
- A respawn gives full HP and full MP. Hearts are kept.
- During a shared-room pause, the frozen player sees "PARTNER PAUSED", and music keeps playing.
- `session.coop` lives next to the launcher's saves. It holds one joint save, overwritten by each save.

## Acceptance criteria (two-game harness tests)
1. **Teleport across the test route:** for each pair of test stages (NO3, NZ0, NO0, NO1, including the same stage), A teleports to B. A ends up in play in B's room within 16 px of B (or B's last grounded spot), the camera is on A, and nothing else changes in A's status.
2. **Teleport fuzz:** 200 teleports while both games explore at random. No softlock or crash, and A is in play within 5 s of every teleport.
3. **Map UI:** on A's map screen, ✕ teleports and the prompt is visible (pixel check). With the partner busy, ✕ does nothing and shows "Partner busy".
4. **Respawn:** A dies (harness: HP set to 1, then a hit). The death animation plays, then A appears at B with full HP and no Game Over. B is unaffected.
5. **Both dead:** both die. Both reload the last joint save, in its save room, with status, flags and map equal to the save.
6. **Pause:** B pauses in A's room. A's world freezes (player, enemies and RNG unchanged over 120 frames), "PARTNER PAUSED" shows, and it resumes when B unpauses. B pausing in another room doesn't affect A.
7. **Joint save:** A saves at a save room. `session.coop` holds both saves, and B's has B's status and A's save room. After a fresh boot of both games and "Continue co-op", both are in that save room with their own status and the merged flags and map.
8. **No regressions:** the M1 and M2 suites pass. A 10-minute soak with random teleports and deaths: no crash, and shared state converges.

## Risks
- **Reviving from `Engine_10`:** the player entity may hold death state that clearing the status bit doesn't undo. A spike comes first. Fallback: catch the death earlier, at HP 0 before the animation, and skip the animation.
- **Rooms with scripted entrances** (elevators, boss doors, cutscene triggers) may softlock a teleport. Mitigation: target the partner's last safe position, a list of rooms where you can't arrive (the partner counts as busy there), and the fuzz test.
- **Entering play from the title for resume** follows the file-select overlay's steps, not yet traced. A spike comes first. Fallback: the player starts a new game, and the module applies the save on the first frame in play, through the in-play Arrive path that's already proven.
- **A 5th DRA hook:** it must stay size-neutral like the other 4, which `build_disc.sh` checks.
