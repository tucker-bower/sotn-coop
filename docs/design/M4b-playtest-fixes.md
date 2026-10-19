# M4b: playtest 1 fixes (notes in `docs/playtest_notes/playtest_1.md`)

**Status:** in progress, approved by Tucker 2026-10-19 ("address my feedback as m4b").

## Causes found so far
| Note | Cause | Fix |
|---|---|---|
| Background trees bounce on one screen when the other player jumps | Trees are parallax entities (`unk68`) that build their primitives from their own position in their update. The guest doesn't run that update, and only shifted primitives of camera-locked entities, so the trees kept the authority's camera. | Shift every copied entity's primitives by the same amount as the entity, including the parallax case. |
| Wolves respawn after the authority leaves the room | The layout spawner skips killed entities using `g_unkGraphicsStruct.D_80097428[8]`, a per-room killed bitfield in DRA globals that isn't in the snapshot. | Add `D_80097428` to the snapshot. |
| A "strange save" loaded after the prologue | The launcher's both-dead rule fired at the end of the Richter fight and reloaded `session.coop`, left over from the save-room test. Also, a dying player waits for the host whenever the partner is busy, which could freeze the game. | Only count deaths in Alucard play outside ST0. Hold only when the partner is really dead. Only reload a joint save made during this launcher run; otherwise each game gets its own Game Over. The New Game preset clears `session.coop`. |
| No sound after P1's fight ended / no sounds of P2's hits | The launcher plays one game's sound only. Enemy hurt and death sounds come from the authority's game. | Mix both games' sound. Mute music (the SPU CD-audio volume) in all games but one: P1's, unless P1 isn't in play (cutscene, loading), then P2's. |

## Still to investigate (harness reproductions first)
- Wolves flash a rainbow texture when hit. Suspect: the puppet's VRAM page overlaps a palette written only during hit flashes, so the earlier VRAM scan missed it. Check against the puppet switched off.
- Candles respawn, or one player can't break them. Check relayed hits on breakables, in both roles.
- A visual glitch when an enemy hit by both dies.

## Polish requested
- **Death:** a proper beat (the death animation, then a fade) before respawning.
- **Teleport:** a visible effect, such as a white flash and fade, which the game already uses for special transitions.
- **"GAME SAVED" on the partner's screen.** In-game text, possibly via DRA's bottom-corner text, would also cover D42.
- A launcher preset that starts right next to a pickup.

## Also planned
- **Bug-hunting myself (Tucker's ask):**
  - Long harness runs that fight across stages.
  - An automatic glitch detector: the guest's screen against the authority's, aligned by the camera difference, with the players and HUD masked.
  - Review of any frames it flags.
- **Launcher recording:** both pads' inputs from a deterministic start, plus an F9 "something's wrong here" bookmark. I can then replay a session exactly in the harness. Replays need the launcher's frame order to be deterministic: both games step, then both exchange messages.
