# Roadmap

**Final goal (D19):** two players explore the castle **independently** over couch co-op or online with android-pc-linux-mac crossplay capabilities, each on their own screen, with **shared progression**. Boss fights and cutscenes are sync'ed and experienced together.

## Now
_Updated 2026-10-31._

- **Latest release:** v0.12.0, the public beta of 1.0 (D121). Everything since is only on `main` (0.13.0-dev): the partner as a real second player (M13), Slippi-style connecting (M14), PvP (M15), inverted castle coverage and boss rush.
- **Tests:** everyday 211 of 212 (the failure is under "Known issues"); last `--full` 283 of 283.
- **Next:** by the priority order (D109), M16. v1.0 follows playtesters' feedback (D121) and the first-castle playthrough in segments (D114), so a new beta probably comes first.

## Decisions needed
- **New beta first, or M16?** M13–M15 haven't reached players. A beta needs `--full`, the boot check and a playtest before release; M16 would otherwise build further on unplaytested work. The agent's recommendation: beta first.

## Known issues
**Bugs**
- **Karasuman:** in the first-castle chain, 15 frames into his fight, B is re-placed and stays in his room with no boss and no shared room, so A fights on alone. Possibly a co-op bug. The chain passes only because the test wears down each game's own boss.
- **Slow joiner in boss rush:** under full load, the joiner stays at the title after the host's first rush load (`ui_online_boss_rush`). A slow phone could hit it.
- **Maria in the Center:** her scene gives control back 93 frames in, without its last step or the Holy Glasses, even in one game (`session_m12.OPEN_SCENES`).
- **Richter's HUD name box** is blank after a save load (retail Richter too).
- **Partner's body:** Alucard afterimages use some of DRA's 16 DR_ENV entries; the VRAM-to-CPU copy doesn't read bank 2, so a partner's death dissolve starts from player 1's frame.
- **Off-hand weapons:** some frames' palette is wrong (a raised blade blue instead of white).
- **Android:** sound underruns on the emulators (7–38%, CPU-bound); not yet checked on the Thor.

**Not covered by a test**
- Shaft, and the inverted castle's scenes.
- Three first-castle bosses have no time-attack record after a scripted kill: the Lesser Demon, Olrox, Richter.
- Hit tests check the reaction, not its sound.
- Power of Wolf and Skill of Wolf; the blue door live (world relics are checked in code only).
- Leaving the Librarian's shop through his menu; the Succubus pairings (no saving in the Nightmare).
- `android_pair` and `android_pc_join`: they fail from the emulators' test setup; the real Thor hosting the PC works.
- A real two-home online test.

## Milestones
Each milestone's acceptance criteria are in its design doc, in `design/`.

| # | Milestone | State | Design |
|---|---|---|---|
| M0 | Test harness, 8 MB verified | Done | `M0-harness` |
| M1 | Link and presence | Done | `M1-link-presence` |
| M2 | Shared progression, live | Done | `M2-shared-progression` |
| M3 | Teleport, respawn, pause rules, joint saves in the game's save rooms | Done | `M3-teleport-respawn-save`, `M3b-save-rooms` |
| M4 | Shared rooms: same enemies, fight together | Done | `M4-shared-rooms`, `M4b-playtest-fixes` |
| M5 | Bosses and cutscenes together | Done | `M5-bosses-cutscenes` |
| M6 | Playable Windows build | Done | `M6-playable-build` |
| M7 | Its own repository, online PC co-op, netcode, release | Done | `M7-repo-and-online`, `M7b-netcode`, `M7b-polish` |
| M8 | Richter and Maria playable | Done | `M8-maria-and-richter`, `M8b-character-balance` |
| M9 | Android | Done | `M9-android` |
| M10 | Thor dual screen: moved to the backlog; widescreen is M19 (D111) | Moved | `M10-widescreen-spike` |
| M11 | Castles: drop-in saves, solo, shared level | Done | `M11-castles` |
| M12 | Coverage, then v1.0 | 0.12.0 beta released. **Left:** the first-castle playthrough in segments, playtesters' feedback, v1.0 | `M12-coverage`, `M12-v1-release`, `M12b-offhand-like-alucard` |
| M13 | The partner as a real second player | Done | `M13-partner-player` |
| M14 | Connect the way Slippi does (cut down, D123) | Done | `M14-relay` |
| M15 | PvP, the host's option | Done | `M15-pvp` |
| — | Boss rush | Done | `boss-rush` |
| M16 | Saturn Maria, the long-coat Richter, the Saturn select, the PSP Alucard voice | Planned | `M16-saturn-characters` |
| M17 | 3+ players, online then couch | Planned | `M17-more-players` |
| M18 | Mac and Linux (Steam Deck) builds | Planned | `M18-mac-linux` |
| M19 | Widescreen | Planned | `M19-widescreen` |

The inverted castle's tests are built (D133), but it ships after v1.0 as v1.1 (D114).

## Backlog
Tucker moves one of these into a milestone when he wants it worked on.

- **DXC dialogue and voice acting (D84):** an option to use the *Dracula X Chronicles* English script and voices: converting the PSP's ATRAC3 audio and replacing the cutscene scripts in 8 stages. It needs the player's DXC disc.
- **F9 sends bug reports (D86):** the snapshot plus a short form, sent to a private repo through a small hosted relay. It needs a free Cloudflare account and a GitHub token from Tucker. Design: `design/backlog-report-sending.md`.
- **A rescue menu for playtesters:** "I'm stuck" in the pause menu, to get past a co-op bug and keep playing. Design: `design/backlog-rescue-menu.md`.
- **Power tuning and more characters' testing (D111):** waits for community feedback on v1.0.
- **AYN Thor dual screen (D111):** top screen you, bottom screen your partner, and a metal bat in place of the blood vial's cork (centred, with a pixel test).
- **Community characters (D111):** a guide, a format and a module interface for adding characters (for example, Soma from *Aria of Sorrow*): a PS1 player overlay in C, built like our Maria (`characters/maria-dx/`), shipped as patches of code only, with its art converted from the player's own files. PS1 overlays are the one character format that also runs on SymphonyRecomp.
- **Thrown items and potions from the off hand** (TNT, Karma Coin, Str. potion, Resist potions), and weapon specials (Crissaegrim, Muramasa, Shield Rod spells).
- **Connecting:** IPv6 and port prediction (deferred from M14).
- **Installers:** accept `.chd` disc images; a small branded `.exe`, so the firewall prompt doesn't say "Python".
