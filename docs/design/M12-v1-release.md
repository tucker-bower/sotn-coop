# M12 finish: v1.0 release

**Status:** approved by Tucker (2026-10-27). Extends `M12-coverage.md` (parts 1–3 built) into the v1.0 release. Priority order and scope: D109.

## Goal
A playable, public **v1.0** that a stranger can install and finish the first castle with, on PC or Android, alone, on the couch or online. "Covered" means what it meant in M12 (a session test with RAM assertions on both games); v1.0 widens what is covered to the whole first castle and closes the release gaps (licence, signing, start-up).

## Work, in order
1. **Coverage, widened.** What M12 has, plus what's missing:
   | Area | Now | v1.0 |
   |---|---|---|
   | Bosses | 12 of 12 first-castle, 3 pairings | same, plus the death-mid-fight rule per boss |
   | Hand weapons | 72 of 72, 3 characters | same |
   | Relics | the M8b gate tests | **every relic's effect, per character** (`m12_relic_*`): equipped by RAM, used next to its gate or effect, the result checked |
   | Spells, subweapons, Item Crashes | partial | every one, per character |
   | Rooms | the critical path, gate by gate | **every first-castle room reachable by every character** (see below) |
   | Scenes | all but 4 | all first-castle scenes (the Librarian, Maria in the chapel and in the Center) |
2. **Release gaps.**
   - **Licence:** the repository has **no LICENSE file** (GitHub shows none), so legally it isn't open source yet. Add `LICENSE` (AGPL-3.0, as the installer already says), a `NOTICE` with third-party credits, and the same licence folder in the APK (SwanStation GPL-3.0, OpenBIOS MIT, Python PSF, pygame-ce LGPL-2.1, pyjnius MIT, SDL2 zlib).
   - **Android release key** (replaces D95): a release keystore, its password and a copy of the file in Tucker's password manager; the build reads it from a path in `env.toml`, never from the repo. **Migration:** today's APKs are debug-signed, and the new key can't install over them without an uninstall, which deletes the app's private saves. The last debug-signed build (0.12.x) moves saves to shared storage (`Documents/SOTN Co-op`), which survives the uninstall; the first release-signed build reads them from there.
   - **Launch black screen:** the 2× disc speed and the "Starting the game" overlay are built but unchecked. Check them on the PC and the Thor; find why our disc boots 3.5 s slower than retail (the co-op module and Richter loading) and remove what can be. **Assumption:** this is the black screen Tucker means. If he saw a different one, it gets reproduced first.
3. **Known bugs:** the M8 leftovers (Richter's blank HUD name box after a load, the faerie/demon/sword familiars for Richter and Maria, thrown items and potions from the off hand), the sound underruns on the emulators, and everything open in the M12 playtest notes.
4. **The first-castle playthrough, in segments** (M12 part 4, option A): the critical path from the prologue to the inverted castle's entrance, as chained segments (savestate in, scripted route and bots, savestate out). Each segment is a test, and a failing one restarts from a fixture so one bug doesn't stop the run. Runs with `--full`.
5. **Then the inverted castle**, the same way (its bosses, scenes and segments). See decision 1.

## Every room, every character: how
| Option | Idea | Verdict |
|---|---|---|
| A. Live crawl | A bot enters every room from every door and walks to every other exit, per character | ❌ Several hundred rooms × their exits × 3 characters: far past the budget, and brittle |
| **B. Static map, live proof (recommended)** | A planner reads each room's collision tiles (from the player's disc, at test time) and each character's measured moves (jump height and reach, slide, wings, mist, bat), and finds which exits connect with which relics. Every connection it calls marginal (within a few pixels of a jump's reach) gets a live scripted crossing; the rest are sampled (10%) | ✅ RAM and tile text only. The report lists every room per character as reachable, reachable live-checked, or a gap with the reason |
| C. Playthrough only | Trust the chained segments plus the gate tests | ❌ Proves the path, not "every room" |

## Acceptance criteria
1. Every relic, spell, subweapon and Item Crash: a passing test per character, or listed with the problem.
2. A room report per character (option B): every first-castle room reachable, or a gap with its reason, and no gap Tucker hasn't seen.
3. Every first-castle boss and scene passes its session tests, the 4 open scenes included.
4. `LICENSE` and `NOTICE` in the repository; licence texts in the installer and the APK; `release.py` refuses a release without them.
5. The APK is release-signed; `android/test_pair.py` shows a debug-signed install's saves surviving the switch.
6. Launch: a picture (overlay or game) within 1 s of pressing Play, and the title within 20 s on the PC (measured by the launcher's frame log).
7. The M8 leftovers: each fixed with a regression test, or decided by Tucker.
8. The first-castle chain passes from the prologue to the inverted castle's entrance (`run.py --full`).
9. `run.py --full` all green, a boot check on PCSX-Redux, and a playtest by Tucker, before v1.0 is published.

## Decisions (Tucker)
1. **Does v1.0 wait for the inverted castle?** Recommended: **no**. Ship v1.0 after criterion 8, and the inverted castle is v1.1 (it adds about 4–6 windows before release).
2. **Boss fights pause when either player opens the menu** (decided: D110). Nothing to build: it's today's behaviour, now with a regression test (`m12_boss_menu_pauses`).

## Risks
- **The planner (option B) can call a crossing possible that the game doesn't allow** (a slope, a moving platform). Live checks on every marginal crossing, and the playthrough segments, catch most of that.
- **Fight bots can't beat every boss**, so some kills stay scripted. That tests the flow, not the difficulty.
- **The key migration:** an Android user who skips 0.12.x and goes straight to a release-signed build loses saves. The release notes say so in the first line.

## Budget
About 12–16 usage windows: coverage 6–8, release gaps 2, known bugs 2–3, the first-castle chain 3–4. The inverted castle is about 4–6 more.
