# M12 design: the agent plays the game (coverage), and playtest 3 fixes

**Status:** proposal, awaiting Tucker's approval. Playtest fixes (`docs/playtest/2026-10-25-tucker-thor-pc.md`) are built meanwhile on `coop-m12-coverage`.

## Goal
Playtesters are scarce and the major features are done, so the agent becomes the playtester. Every cutscene and every boss, played as co-op, with every character; every character past every obstacle on the way; every hand item in every character's hands; both screens checked. The ideal is a full end-to-end playthrough by the agent. M12 builds the pieces that make that possible and runs them, within budget.

## What "covered" means
A **session test** (two games plus hosts, in the harness) that ends with RAM assertions on both games, plus a contact sheet of both screens at the key moments. The agent reviews contact sheets itself, and only where the automatic checks can't decide (vision costs usage).

## Part 1: every cutscene, together
- **The catalogue** (`harness/cutscenes.py`): every scene, generated from the decomp, then checked by hand. That means the 14 cutscene scripts (`src/st/*/cutscene.c`, `e_cutscene_dialogue.c`, `src/boss/mar`), plus scenes started another way (boss intros, Shaft, the ending). Each entry: stage, room, the spot that triggers it, and the story flags it needs. The fixtures are made from RAM, like the boss starts (`launcher/bossstarts.py`).
- **Per scene, three tests:**
  1. A triggers it while B is elsewhere: B is pulled in, the two copies start within 3 frames of each other, both end back in play, and the flags match;
  2. both are in the room when it starts;
  3. A triggers it while B is busy (in a menu, loading, or in the prologue): A waits, then both play it.
- **Pass:** no game stuck in a scene (30 s budget past the scene's own length), no pull-in loop, no lost flag, and both screens show the scene (frame-difference check).
- **The prologue and the scene after it** are built first (playtest note 1).

## Part 2: every boss, every character
- The boss starts cover the first castle. Add the inverted castle's bosses (same method).
- **Per boss, for the pairings A+A, R+M and A+R:**
  - the pull-in;
  - 2× HP;
  - the fight finishes with a **fight bot** (a damage boost is allowed: this tests the flow, not balance);
  - after the kill, the same results in both games: the relic or item drop, the doors, the story flags and the time-attack record;
  - the death-mid-fight rule, once per boss.
- The fight bot is generic: approach, attack, back off when hurt. Bosses it can't beat even with the boost are listed, and get a scripted kill (HP to 0) so the flow after them is still tested.

## Part 3: abilities, obstacles, weapons, screens
- **Obstacles:** a list of every traversal gate on the critical path and the optional areas, each with what it takes to pass. Examples: double jump, high jump, mist bars, bat-only gaps, water, the Gravity Boots, the Jewel of Open. Per character, a scripted crossing from a savestate in front of it. Fails are a reachability report (the M8b criterion 3 audit), not just test failures.
- **Hand items:** every hand item (about 170), in Alucard's hands and in Richter's and Maria's off hands. Each one is equipped by RAM, then used next to a training enemy. **Pass:** the attack entity spawns, the enemy takes damage of the item's element, nothing stays behind, and no crash. A 1-frame crop of the swing goes on a contact sheet per weapon class.
- **Abilities:** every relic power, spell, subweapon and Item Crash per character, by the same method.
- **Both screens:** in every shared-room test, the partner (body, weapon, subweapon) must be drawn on the other screen, found by pixel difference against a render without the partner (`partner_pixels`).

## Part 4: the end-to-end playthrough (stretch)
| Option | Idea | Verdict |
|---|---|---|
| **A. Chained segments (recommended)** | The critical path split into segments: savestate in, scripted route plus bots, savestate out. Each segment is a test, and the chain is the playthrough. A failing segment is restarted from a fixture, so one bug doesn't stop the run. | ✅ Reuses parts 1–3. It grows a segment at a time and stops wherever the budget does. |
| B. An agent-in-the-loop player | The agent reads RAM text each few seconds and chooses inputs | ❌ Thousands of model calls: far past the Pro budget |
| C. Replay a published speedrun movie | TAS input files exist for other emulators | ❌ They desync on SwanStation, and a speedrun skips most of the game |

## Playtest fixes (in parallel)
1. **Prologue and cutscenes held for each other** (note 1): see part 1.
2. **Graceful exit** (note 5): a goodbye message, "Your partner left" in game and in the launcher, with a choice to continue solo; a lost connection says so after 10 s.
3. **Maria's special weapon** (note 4): reproduce, fix, regression test.
4. **Partner's weapons drawn** (note 2): subweapons and spells first, then hand weapons, whose graphics need the partner's weapon file loaded into a spare VRAM slot.
5. **Off-hand weapons like Alucard's** (note 3): **decision for Tucker after a spike** (`docs/STATUS.md`).

## Acceptance criteria
1. `cutscenes.py` lists every scene, and each has its three tests passing, or a written reason (for example, a scene only one player can be in).
2. Every boss in both castles: pull-in, 2× HP, the kill and its results checked in both games, for A+A, R+M and A+R.
3. An obstacle report per character: every gate passed by script, or listed as a gap with the reason.
4. A hand-item report: every item in every hand works, or is listed with the problem.
5. The playtest notes: each fixed with a regression test, or decided by Tucker (note 3).
6. Part 4: as many critical-path segments as fit in the budget, chained. Report how far the chain got.

## Risks
- **Fixtures by RAM can hide bugs that real play hits** (for example, the flags that only a real walk sets). The obstacles and the end-to-end chain play the real route.
- **The fight bot may not beat many bosses.** A scripted kill keeps the flow tested; the balance is still for humans.
- **Budget:** parts 1–3 are about 6–8 usage windows, the fixes about 3, and part 4 whatever is left. The heaviest costs are boss and cutscene fixtures. Reports are RAM text; screenshots are reviewed only by exception.
