# M3b design: the game's own save rooms, end to end

**Status:** proposal, awaiting Tucker's approval.
**Budget:** 4% of the month. Target: 2026-10-21 (before M4's build).
**Context:** M3 (D31, D43), Tucker 2026-10-19: "using the game's built-in save rooms and being able to resume from those saves all in-game would be ideal". Launcher saves are the backup.

## Goal
- A player saves at a save room through the game's own coffin and memory-card dialog. Both players then have a normal save on their own memory card, pointing at that save room.
- Later, each player picks **Load** on their own title screen and chooses that save. Both start in the save room side by side, each with their own stats, and the shared map, flags and gold.
- No launcher step is needed. `session.coop` stays as a backup, and still handles "both players dead".

## What already works, and what's missing
- ✅ The save room's `StoreSaveData` call is hooked (the 5th size-neutral hook). When a player saves, the module posts the save and the launcher asks the partner's game to build its own save for the same save room (M3).
- ❌ **The partner's save only goes to `session.coop`, not to the partner's memory card.** So the partner can't pick it from the game's Load menu.
- ❌ **The real coffin and card dialog has never been driven in a test** (D43).

## Part 1: writing the partner's save to the partner's memory card

| Option | Idea | Verdict |
|---|---|---|
| **A. The partner's game writes its own card, using the game's card code** | When asked to save (`CMD_SAVE_NOW`), the module builds the save as now, then writes it to its own memory card. It uses the same functions the save room uses (`MakeMemcardPath`, `MemcardWriteFile`, then polling the card events, in `src/save_mgr.h`), run as a small state machine over a few frames while the game keeps playing. The block is the one the saver picked (`D_8006C378`), on the partner's card. | ✅ **Recommended.** It's a real save on a real (emulated) card, so the game's own Load menu reads it, on any emulator. |
| B. The launcher writes the partner's card file | The launcher puts the save bytes into the emulator's memory-card file | ❌ It depends on the emulator: SwanStation keeps the card in memory and may overwrite the file. That's fine as the backup. |

**Details:**
- The card is busy for a few frames during the write. Only menus and save rooms use the card, so the write waits if the partner is in a menu or save room at that moment, and retries.
- If the partner's card is missing, full or unformatted, the save still lands in `session.coop`, and the module reports the failure. That's no worse than today.
- Card writes are asynchronous in the PsyQ library, so the game keeps running during the write. A test checks this.

## Part 2: resuming in-game
- **Nothing new is needed in the game:**
  - Each player loads their own save from the title, as in single-player.
  - Both saves resume in the same save room.
  - Shared state is already identical in both saves (the flags, map and gold are merged).
- **When the link connects,** M2's merge on entering play reconciles anything that drifted. The partner was mid-run when the save was made, so a pickup made between the two save moments would otherwise be missing from one save.

## Acceptance criteria (two-game harness tests)
1. **Real save room:**
   - A walks into a save room on the test route and goes through the coffin, the "Save?" prompt and slot selection with scripted inputs.
   - A's card holds the save.
   - Within 5 s, B's card holds a save in the same block, pointing at A's save room, with B's status.
   - B keeps playing throughout (its frame counter never stalls more than 2 frames).
2. **Resume in-game:**
   - Both games boot fresh with the same memory cards. Each goes title → Load → that slot with scripted inputs.
   - Both end up in play in the save room with their saved status, and the shared flags, map and gold are identical.
3. **No partner card:** with B's card removed, the save still reaches `session.coop`, and the module reports the card failure. No crash, no hang.
4. **No regressions:** all M1–M3 tests pass, including both-dead reload from `session.coop`.

## Risks
- **Card I/O in the middle of play** could collide with the game's own card polling, for example the "memory card inserted" checks. Spike first: write a card from the module while in normal play, and confirm the card reads back on a fresh boot.
- **The harness needs persistent card files** across sessions (today every game gets a fresh, empty card). The fix is an `Emu(card_dir=…)` option.
