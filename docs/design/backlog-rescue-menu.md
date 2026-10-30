# Backlog design: a rescue menu for playtesters

**Status:** on the backlog (Tucker, 2026-10-28): an idea, not yet a milestone. Tucker moves it into one when he wants it.

## The problem
A playtester who hits a co-op bug today has two ways out: quit and lose everything since the last save, or stop playing. Either way the playthrough stops there, so we learn less from the rest of the game. They need a way past the problem that still sends us the bug.

## What goes wrong in playtests (from playtests 1–3 and the M12 coverage)
- **Stuck in place:** in a wall or floor, below the camera, or on the wrong side of a door that won't open (D107's red doors).
- **Story stuck:** a scene that doesn't start, or doesn't give control back; a boss that doesn't come in or doesn't die; a door that stays sealed after the boss.
- **Apart:** the partner is somewhere you can't reach, or the pull-in keeps moving you back and forth.
- **Out of step:** shared progress differs between the two games, such as a relic, a flag or the map.
- **Lost:** a crash, a freeze or a bad load, so neither game can go on.

## Recommendation: "I'm stuck" in the pause menu (option A)
Six rescues, each one confirmed first. Online, the partner sees "Your partner used: …".

| Rescue | What it does | Built from |
|---|---|---|
| Back to the door | Puts you at the door you last came through, in this room or the one before | the host records each door from presence; `CMD_ARRIVE` |
| Go to my partner | Moves you to your partner (already exists in M3, made visible here) | teleport |
| Back to the last save | Both players reload the joint save, as when both die | `JointSave.resume` |
| Back to a moment | The castle's last event savestate (new area, boss), both games | savestates; online, both agree first |
| Skip this boss / scene | Marks it beaten or seen, opens its doors and gives control back | the boss and scene tables in `bossstarts.py` (flags, events) |
| Warp to a save room | Any save room or teleporter you've visited | the castle map, `CMD_ARRIVE` |

**Rules:**
- **Every rescue saves a bug report** (the F9 snapshot, marked with the rescue used). Its log tells us what broke and what got the tester past it.
- **No cheats:** no items, stats or gold.
- **Determinism:** each rescue is a launcher command between frames, like `CMD_ARRIVE`, so no new timing-dependent code goes into the game.
- **Couch:** either player can use it from their pause.

## Other options
- **(B) A developer console:** a flags editor, warp anywhere, set any stat. It's powerful but easy to break a playthrough with, and testers would need to know the game's internals. It could sit behind the Developer menu later, for us.
- **(C) Automatic detection:** "no progress for 3 minutes in one room" or "a scene for 2 minutes" offers the rescue on its own. This is a good later addition to A, but risky alone, because it would fire during normal play.

## Risks
- **Skip this boss / scene** must set every flag the game sets. A missed one can break the story later, which is worse than the original problem. Each needs a test like the M12 boss tests: both fine afterwards, the same flags.
- **Online rewinds** (a moment or the last save) need both players to agree, or one player's progress is lost.

## Size
About 1–2 usage windows. Back to the door, Go to my partner, Back to the last save and Warp reuse what exists. Skip this boss / scene is most of the work and the testing.
