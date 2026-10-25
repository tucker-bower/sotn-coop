# M8 design: playable Maria and Richter

**Status:** approved by Tucker 2026-10-21 (D85, D86). Every recommended option (1A–4A), plus §5 (both HUDs visible). Built on `coop-m8-maria-richter`; every criterion has a passing test (the PR lists them). Character balance and the ability mapping have their own design: `docs/design/M8b-character-balance.md`.
**Context:** D27 (character choice), D75 (M8 scope), D84 (Tucker's M8 decisions).

## Goal
1. **Each player picks Alucard, Richter or Maria every time they play**, in the launcher's lobby, in any combination (Alucard + Alucard, Maria + Maria, Richter + Alucard...).
   - The same playthrough can be continued with different characters: two hours as double Alucard today, Maria + Richter tomorrow.
   - The disc is never rebuilt for a character choice.
2. **Every character gets the full Alucard castle:** all bosses, relics, items, cutscenes and switches, and progression for Richter and Maria that keeps them as strong as Alucard at every point (M8b).
3. **Maria comes from the player's own *Dracula X Chronicles* (USA PSP) disc image**, which is optional. Without it, Maria shows as locked in the lobby, as now.
4. **Setting up the game files is clear to a first-time player:** the SOTN disc (required), the DXC disc (optional, adds Maria), and the BIOS (included, replaceable).
5. **Both players always see their own health, MP and hearts** (§5).

## Spike findings (`disks/sotn.pspus.iso`, 2026-10-19)
- **Richter is entirely on the US PS1 disc:** `BIN/RIC.BIN` and `VAB/SD_RIH.VH/.VB`, decompiled in `src/ric/`.
- **Maria's assets are on the USA DXC disc (`ULUS-10277`):**
  - In `PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin`, every asset sits at a constant `-0xB780` offset from the EU disc that `mods/mariapsp-forpsx` targets. So no EU disc is needed.
  - Her English and Japanese voice/SFX banks (`sd_mar2.spk`) build through `tools/maria-sfx`.
- **The game already switches characters at runtime:** one variable, `g_PlayableCharacter`, selects the player overlay (`game_handlers.c`, `cd.c`). Nothing in the save format depends on it, apart from the save name.

## 1. Richter and Maria alongside Alucard, chosen per session
| Option | Idea | Verdict |
|---|---|---|
| **A. Retail files untouched; Maria (and our Richter) loaded into the 8 MB expansion RAM by the launcher** | The disc stays as patched once. At boot, the launcher writes the chosen characters' player overlays and sound banks into expansion RAM (above `COOP.BIN`): `MARIA.BIN` + `SD_MAR`, and our `RIC.BIN` (built from the decomp with the M8b changes). The module then loads the player overlay from RAM instead of the CD. The character is a session setting, not part of the save. | ✅ **Recommended (Tucker: option A).** |
| B. Two patched discs | One for Richter, one for Maria | ❌ No mixed teams, and the disc rebuilds |

**Why the launcher loads the characters:**
- The disc never changes after the first patch.
- Adding a DXC disc later only extracts Maria into the data folder: no re-patching.
- Each game can load a different character.
- D34 holds: no retail file moves; `RIC.BIN` on the disc stays retail.

**Our own Richter:** M8b gates his moves behind relics, so we need a modified Richter. It's built from `src/ric/` with our changes and loaded like Maria. The retail `RIC.BIN` remains for the prologue.

**Saves:** joint saves keep working across characters, because the status, relics, items and flags are character-neutral. On Continue, each game gets the character its player picked in the lobby, not the one that saved.

**The prologue:** both games play it as retail Richter, as now. Characters take over at the castle entrance.

## 2. Partner puppets for mixed teams
| Option | Idea | Verdict |
|---|---|---|
| **A. Sprite cache in expansion RAM + per-frame upload of the partner's current pose** | The other characters' sprite sheets and palettes live in expansion RAM (< 512 KB of the 6 MB free). In a shared room, when the partner is a different character, the module uploads only the current pose (about 1–2 KB) into a reserved 64×64 VRAM slot and draws the puppet from it. | ✅ **Recommended (Tucker: option A, provided it doesn't cost performance).** |
| B. All three sheets in VRAM | — | ❌ No room: stage tiles and enemies fill VRAM |

**Performance guard (acceptance criterion 3):**
- The upload is one `LoadImage` of ≤ 2 KB per frame, only when the pose changes.
- Measured in a 10-minute mixed-team shared-room session: the game's own frame time and the host's per-frame time must stay within M7b's numbers.
  - no dropped emulated frames
  - host p99 < 1 ms
  - the launcher at 60 fps on Tucker's PC

## 3. Progression for Richter and Maria
| Option | Idea | Verdict |
|---|---|---|
| **A. One Alucard castle for every character, with Richter and Maria's growth tied to Alucard's progression** | The world always runs Alucard's rules: every relic, item, boss and cutscene, whoever plays. Relics, items, vessels, gold, map and flags are shared as now. Richter's and Maria's moves unlock with the same relics, and they gain power from levels and equipment, so no character is ahead or behind at any point. | ✅ **Recommended (Tucker: option A).** Details: M8b. |
| B. Vanilla Richter mode for Richter/Maria players | Their world skips relics and cutscenes | ❌ The two games' worlds would differ in shared rooms |

**The world sees Alucard:**
- About 50 places in the game check `g_PlayableCharacter`. Most skip Alucard's cutscenes, shops and events for Richter or Maria (`nz0`, `no3`, `dai`, `dre`, `top`, `cen` cutscenes, the Librarian's shop, a red door in `no1`). A few choose the player overlay and its graphics.
- The module keeps `g_PlayableCharacter = ALUCARD` for the world. Only the player-dispatch sites read the session's character, through size-neutral DRA hooks (D33).
- The M8 spike classifies every site first: the list is in M8b's appendix.

## 4. The DXC disc (Maria) and the game-files screen
| Option | Idea | Verdict |
|---|---|---|
| **A. Optional DXC disc in the launcher; Maria extracted from it locally** | The player points the launcher at their DXC `.iso`. Maria's overlay, graphics and voice/SFX are extracted into the data folder once. Nothing is distributed. | ✅ **Recommended (Tucker: option A).** |

**DXC dialogue and voice acting:** Tucker said "whatever is easiest; most users won't care". Swapping the 2007 script and voices means converting ATRAC3 audio and replacing cutscene scripts in 8 stages, which is weeks of work for an option few will use. **Dropped from M8, and on the roadmap's backlog** (D84, D85). Maria's own voice clips come with her either way.

**The game-files screen** (first run, and Settings › Game files), one row per file:

```
 Game files                                                    
                                                               
 ✓  Symphony of the Night (PS1, USA)        required           
    D:\Games\SOTN\Castlevania - SOTN (USA).cue      [Change]   
                                                               
 +  Dracula X Chronicles (PSP, USA)          optional          
    Adds Maria as a playable character.             [Choose]   
                                                               
 ✓  PlayStation BIOS                         included          
    OpenBIOS (free, built in). Your own BIOS works too. [Change]
```

- **Each row says what it's for, whether it's needed, and what's set.** It's checked when chosen (the disc's ID and size), with a plain error otherwise, e.g. "That's the European PSP version (ULES-00841): Maria needs the USA one (ULUS-10277)".
- **The lobby explains a locked Maria:** "Maria: add your *Dracula X Chronicles* disc in Settings › Game files". Pressing a button there opens that screen.
- **Only the SOTN disc blocks playing.** The DXC disc can be added at any time, and nothing is rebuilt.

## 5. Both HUDs fully visible
**The problem:** in footage of the 2026-10-20 couch playtest, Player 1's health and hearts readout (top left of the game picture) may be cut off.

**The suspects, in order:**
1. **The Windows menu bar** (`winmenu.py`) is attached after SDL creates the window. If SDL doesn't account for the smaller client area, the top rows of the window sit under the menu bar. That hits only the game drawn at the top, which is P1 in the stacked layout.
2. **The core's overscan crop:** SwanStation's crop mode can trim the top lines of the picture.
3. **Our own drawing over the game:** notices, or the partner markers.

**Fix:** find the cause, fix it in the launcher, and add a check for it, below.

**Found (2026-10-21):** none of the three. The launcher was maximized on Tucker's 3440×1440 ultrawide (its `settings.json`: 3440×1349, maximized), and the recording (`Videos/2026-10-20 20-49-30.mp4`) is 1280×720, a 16:9 view of that 21:9 window. That cuts both outer sides: P1's HP, hearts and name on the left, the right edge of P2's picture on the right. The status bar's text is cut at its left too. On the monitor itself, both HUDs were whole.
- Ruled out with evidence: the menu bar doesn't take rows from what we draw (the client area equals the size we render at, on Windows); the core's overscan crop leaves the HUD whole (the HP orb starts about 3 rows down in its 256×240 frame); our notices draw in the status bar, not over the games.
- **Check:** `uxdriver.py hud` on Windows: both games in play, then every layout (two windows too) × both pixel modes × 3 window sizes. Each game's top rows on screen (PrintWindow of the client area) match what we render, and match the core's own frame (144/144 checks).
- **Hardening:** a remembered window size is clamped to the biggest screen there is now, so a size from another monitor can't hang off the edges.

## Tucker's answers to the open questions (2026-10-20)
1. Every character gets the full Alucard castle.
2. Characters are picked in the launcher's lobby, as now.
3. DXC dialogue and voices: whatever is easiest. That means not in M8 (above).
4. **2026-10-21:** every recommended option (1A, 2A, 3A, 4A) is approved. The DXC voice and dialogue swap goes on the roadmap's backlog. New: §5 here, plus one-button moves and off-hand weapons in M8b.
5. **2026-10-21, final:** sending F9 reports moves to the backlog (D86, `docs/design/backlog-report-sending.md`). Off-hand weapons use option A with existing art only. Alucard's spell shortcuts are in M8, and every button shortcut is an option each player sets in the launcher.

## Acceptance criteria
1. **Maria from the USA DXC disc** (`test_pspus_extract`): her overlay, graphics, palettes and SFX are built from `disks/sotn.pspus.iso` alone, into the data folder.
2. **Any combination, every session, without re-patching** (`char_select_session`):
   - All 9 pairs start from the same save, each game as its chosen character, with working attacks, subweapons and moves.
   - Continuing that save with different characters works.
   - The patched disc's hash is unchanged throughout.
3. **Mixed-team puppets at full speed** (`mixed_party_shared_room`):
   - Alucard + Maria, Richter + Maria and Alucard + Richter draw each other's animated puppets correctly and fight shared enemies.
   - In a 10-minute shared-room session: no dropped emulated frames, host p99 < 1 ms, and 60 fps on Tucker's PC.
4. **One world for all** (`mixed_party_progression`):
   - A Richter or Maria player picks up relics and items, beats bosses, and sees Alucard's cutscenes and shops.
   - Everything they get is shared with the partner, as with Alucard, in every combination.
5. **Game files screen** (`ux_game_files`): a stranger following only the screen sets up both discs. Each wrong file (EU PSP disc, PS1 disc of another region, a random file) gets a plain error that says what's needed.
6. **M8b's criteria** (character balance) pass.
7. **Both HUDs visible** (`ux_hud_visible`):
   - Every layout (side by side, stacked, two windows, fullscreen), every scaling and three window sizes are covered.
   - In each, both games' HP, MP and hearts readout appears in full in the window, compared with the core's own frame.
   - The cause found is named in the PR.
