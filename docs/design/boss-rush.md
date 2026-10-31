# Boss rush (Tucker, 2026-10-31: "choose boss rush mode -> load first test castle -> kill first boss -> loads players into next castle/boss -> repeat for every boss")

Tucker asked for it directly and said to build it now, so this is a record of the choices, not a proposal.

## How it plays
- **Where:** Solo, Couch and Host each list **Boss rush** under the castles, after Test castles. It makes a new castle named "Boss rush"; Continue on it later resumes at the boss it reached.
- **The run:** the 22 bosses in story order: the first castle's 12, then the inverted castle's 10 (the test castles' boss starts). Each boss starts outside its door with that start's typical progress (level, gear, relics): the fights stay balanced whatever happened before.
- **Next boss:** when the boss is beaten (its own time-attack record, as the game writes it; Richter, whose death starts the ending: as his ending starts), a short pause (3 s, for the death sequence), then both players load into the next boss's castle at its start, as a test castle loads.
- **Death:** as anywhere: a dead player revives at a living partner; both dead (or solo) reloads the current boss's start.
- **The end:** Dracula's ending plays. The status bar shows the boss count and the run's time all along; each boss's split and the total are kept in the castle (`castle.json`, `rush`), with the best total.

## Choices (reversible, agent-default)
- Each boss's own progress, not carried over: carrying level 8 Alucard into Galamoth would be a wall, and balance is the test castles' (D127).
- Time counts frames in play (not loads, not the ending), shown as m:ss.
- Richter: his death would start the ending, which a load can't leave; the next boss loads 1.5 s after he falls, before its fade (`g_CoopRichterState`, boss.c).
- Online, only the host's status bar shows the count and time (the joiner follows the host's loads).
- No new game code: it's launcher-side (`launcher/bossrush.py`), on the joint save's existing load (`JointSave.resume`), so it works on the couch and online (the host drives it; the joiner follows the host's loads).
- Scenes aren't in it (Maria, the Librarian...): bosses only.

## Tests
- `boss_rush_advances` (harness, two games): Slogra & Gaibon beaten → both in the Doppleganger's start; the split is kept; both dead → back at the current boss.
- `boss_rush_through_richter`: Richter killed → not the ending: both at the Creature's start.
- `boss_rush_finishes` and `uxdriver boss_rush` as below; all pass.
- `boss_rush_finishes`: Dracula killed → the ending, the run marked finished with its time.
- `uxdriver boss_rush`: Home > Solo > Boss rush starts at Slogra & Gaibon's door.
