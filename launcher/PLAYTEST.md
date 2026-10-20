# SOTN Co-op playtest 2

Double-click a numbered `.bat` file. Both games open side by side: the **left** game is the first controller, the **right** game the second (or the keyboard: the controls are in the window's bottom bar).
- **Sound:** you now hear both games. Music comes from the left game; **F1** switches it between auto, left and right.
- **F9:** press it the moment something looks wrong. It saves a bookmark (both games' state, and the last 20 s of inputs) in `bookmarks\`, which I can load and replay. No need to describe the bug in detail.
- **ESC** quits; memory cards are kept in `cards\`.

## What changed since playtest 1
- **Trees and bushes:** they no longer jump when the other player moves.
- **Killed enemies:** they stay dead when the other player leaves the room.
- **Drops:** kills by either player drop items.
- **Candles:** both players can break them.
- **Hearts and subweapons:** whoever picks one up gets it.
- **The rainbow flash on hit enemies** is the game's own: the original disc does it too. Enemies now flash when either player hits them.
- **Sound:** both games' sound effects play, and the music keeps going after the prologue.
- **Messages in the game's text box** (bottom right): "Partner is saving" / "Game saved", "Joined partner", "Revived by partner", "Partner out of reach".
- **Teleports and respawns:** the screen flashes on arrival. Dying fades to black first.
- **New:** bosses and cutscenes together (5, 6).

| # | Preset | Try this | Tell me |
|---|---|---|---|
| 1 | Shared room fight | Fight in the hall together. Break candles, kill wolves, walk away from each other. | Anything off on either screen? Did enemies or candles come back when they shouldn't? |
| 2 | Teleport and respawn | Right player: SELECT, then ✕. Then let one player die. | Do the flash, the fade and the messages feel right? |
| 3 | Save room | Left player: coffin, UP. | Did "Partner is saving" / "Game saved" show on the right? |
| 4 | Resume from Load menu | As before. | |
| 5 | **Boss fight together** | Left player walks left into the Doppleganger. | Was the right player pulled in? Is the boss tough enough at 2× HP? Does it go after both of you? Die once: do you stay down until it's beaten? |
| 6 | **Cutscene together** | Left player walks right (jump the step) into Maria's room. | Was the right player pulled in, and did both see the scene? |
| 7 | Explore apart | Pick things up, open the map. | Does your partner get what you find? |
| 8 | New game from scratch | The real thing. | Anything weird, anywhere: just press F9. |

**Known gaps (no need to report):**
- Moving platforms don't carry the guest.
- Big rooms share only while your screens overlap.
