# M4b: playtest 1 fixes (notes in `docs/playtest_notes/playtest_1.md`)

**Status:** built, approved by Tucker 2026-10-19 ("address my feedback as m4b"). Each fix has a harness test in `harness/session_m4b.py`.

## What was wrong, and the fix
| Playtest note | Cause | Fix | Test |
|---|---|---|---|
| Background trees bounce, and the bottoms of trees show, when the other player jumps | Trees and bushes draw from the camera with a 3D projection, a different amount per layer. The guest copied the authority's primitives, which only fit the authority's camera. | The guest runs scenery itself, from a per-overlay list generated from names: it copies each piece once, then its own camera drives it (D56). | `guest_scenery_matches_solo`: the guest's screen matches its own solo screen, apart from the partner's sprite. |
| Wolves respawn when P1 leaves | 1. The layout spawner's cursors came from the authority and point at its camera; at hand-over they swept everything in between. 2. A kill landed by the guest never set the room's "killed" bit in the authority's world. | 1. Re-seat the cursors for the new owner's camera (D58). 2. The authority sets the kill bit, and the guest ORs it in (D57). | `hand_over_keeps_dead_dead` (failed before the fix) |
| Rainbow, glitchy texture on hit wolves | It's the game's own hit flash: the unmodified disc looks the same. But an enemy the *guest* hit didn't flash at all. | The authority starts the flash for relayed hits (D54). | `guest_hit_flashes` |
| Candles only break for one player | Candles react to the hit's `hitParams`, which guest hits didn't carry. | Send `hitParams` with relayed hits (D57). | `guest_breaks_candle` |
| (Found while fixing) Kills by the guest never drop anything | The guest's hit detection rolls the drop, in the guest's world, and the next snapshot wiped it. | Entities the guest's hit detection creates (drops, blood, soul orbs, damage numbers) are created by the authority instead (D57). | `guest_kill_drops` |
| No sound for P2's hits or kills; all sound gone after P1's prologue fight | The launcher played only one game's sound. | Mix both games' sound. Only one game plays music: the left one while it's in play, otherwise the right; F1 switches (D55). | `music_mute` |
| A "strange save" loaded after the prologue | The end of the prologue counted as "both dead", and the launcher loaded `session.coop` from the save-room test. | Deaths count only in normal Alucard play. Only a joint save from the same run is reloaded. New Game deletes `session.coop` (D60). | `respawn_at_partner`, `both_dead_reloads` |
| Death: no death screen, just a short freeze | The respawn cut straight to the stage load. | A slow fade to black, then the respawn; on arrival, a flash and "Revived by partner" (D59). | `death_fades_out` |
| Teleport could use an animation | | On arrival: Richter's Cross Crash flash, and "Joined partner" (D59). | `teleport_flash_and_text` |
| "GAME SAVED" on the partner's screen | | "Partner is saving" while frozen, then "Game saved" (D59). | `partner_save_text` |
| Boss fight didn't pull P1 in | Not built yet (M5). | M5. | `design/M5-bosses-cutscenes.md` |
| Glitch when an enemy both players hit dies | The Warg burns away by render-to-texture (`PRIM_ENV`). The guest's copies pointed at its own, unrelated `DR_ENV` pool entries, so its screen showed leftover VRAM (a piece of the HUD). | Each mirrored `PRIM_ENV` gets the guest's own pool entry, with the authority's contents (D64). | `guest_sees_warg_death` (63 of 63 checks failed before the fix) |
| (Found in my playtests) The guest walked out of a boss room through its closed door | Doors and walls change the room's tiles in the authority's world only. | Mirror the foreground tile layer (D63). | `guest_blocked_by_closed_door` |
| (Known gap D51, fixed) A heart, or a subweapon, the guest picks up went to the authority's player | Drops are collected by the drop's own update, which only the authority runs. | The guest collects drops it touches itself; the authority removes them (D66). | `guest_takes_heart` |
| (Found in my playtests) A relic's "Obtained ..." box was empty on the guest's screen | The box's text is written into VRAM by the stage as it runs. | Mirror VRAM uploads made by stage code; screen-space UI isn't shifted by the camera (D65). | `guest_sees_pickup_text` |

## Bug hunting without Tucker
- **`harness/playtest.py`:** both games are played by bots for minutes at a time, through phases: together, apart, regroup by map teleport, room hops, and no healing (deaths).
  - **Flags raised automatically:** stuck, frozen screen, dropped events, role flapping, a guest whose enemies differ from the authority's, and diverged progress.
  - **Output:** each anomaly is saved with a screenshot of both screens, and contact sheets are saved for reviewing by eye.
- **Launcher F9 "bookmark":** saves both games' state now and from 5 and 10 seconds before, plus the last 20 seconds of inputs and a window screenshot, in `Emulators\SOTN-Coop\bookmarks\`. I read those directly; `harness/replay.py` replays them.
