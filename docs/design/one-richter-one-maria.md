# One Richter and one Maria (decided, issue 232)

**Decided (Tucker, 2026-11-11):** the lobby offers **Alucard, Richter, Maria (PSP), Maria (Saturn) and Richter (Saturn)**. Our Richter and Maria keep every co-op feature, each a castle rule as before. Ultimate Maria (the PSP Maria with SOTN Ultimate's two sub-weapon slots) leaves the lobby: a player who had her plays Maria (PSP). The Saturn pair's portraits are shown as they are, without a tint. Options B and C below were not taken; the analysis stays for the record.

## What the six characters are today
| In the lobby | Needs | What it is | How it plays |
|---|---|---|---|
| **Alucard** | PS1 disc | The game's own | As the game |
| **Co-op Richter** | PS1 disc | Our build: Richter's code running on Alucard's engine (D89) | Wears Alucard's armour and gear; levels up; learns moves from Alucard's relics; his attacks and defence use Alucard's stats; off-hand item on Circle; familiars and gear effects work. **Each of those is a castle rule, all on by default.** |
| **Ultimate Richter** | PS1 + Saturn disc | SOTN Ultimate's: the retail Richter, in the Saturn's long coat | Every move from the start; his own stats and damage; none of Alucard's gear, levels or relics |
| **Co-op Maria** | PSP disc | Our build of the PSP Maria (the decomp's `mariapsp-forpsx`), with the same co-op features as Co-op Richter | As Co-op Richter: gear, levels, relic moves, Alucard's stats, each a castle rule |
| **Ultimate Maria** | PSP disc | SOTN Ultimate's PSP Maria: the same decompiled Maria, built as that mod builds her | All her moves from the start; **two sub-weapon slots** (Circle swaps) and the PSP's sub-weapons (Cat, Cardinal, Turtle, Dragon, Doll); her own stats; no gear or levels |
| **Saturn Maria** | PS1 + Saturn disc | SOTN Ultimate's Saturn Maria: a different moveset altogether | Kicks, dives, a backdash, a double jump, the Holy Beasts; her own Saturn HUD and voice |

So the difference is mostly **our co-op features** (gear, levels, relic moves, Alucard's stats). Those are already castle rules. Turn them all off, and Co-op Richter plays close to Ultimate Richter: the moves and stats are the retail Richter's, but he still runs on Alucard's engine, so the feel can differ in small ways we haven't measured. What only an Ultimate build has:
- **Ultimate Richter:** the Saturn coat. Nothing else.
- **Ultimate Maria:** two sub-weapon slots and the PSP's five extra sub-weapons, plus SOTN Ultimate's bug fix for sticking after a crouch.
- **Saturn Maria:** a whole other moveset.

## Options
| | What players see | Work | Upkeep |
|---|---|---|---|
| **A. One Richter, one Maria: ours, with the Ultimate extras folded in as options** (recommended) | **Richter** and **Maria**. Castle rules (already there) choose gear, levels, relic moves and stats. Two new **player** options, shown once the Saturn disc is attached: *Richter's Saturn coat*, and *Maria's moves: PSP or Saturn*. Later, a castle rule for *Maria's two sub-weapon slots* | Medium. The coat is cosmetic (Ultimate Richter's coat code on our Richter); Saturn Maria stays as she is, offered as Maria's Saturn moveset rather than a character; the two sub-weapon slots mean porting Ultimate's `mar2.c` glue into our Maria (a separate, later step) | Lowest: two Marias to keep working instead of three; no Ultimate Richter blob |
| B. Keep both builds, explain them better | The same six, each with a line like "Plays as in SOTN Ultimate: every move from the start, no gear" | Small: wording only | Highest: every Richter and Maria fix done twice; most tests per character |
| C. Ultimate only | Ultimate Richter, Ultimate Maria, Saturn Maria | Small to remove ours | Loses the co-op features we built (gear, levels, relic moves, shared progression with Alucard), which are what make them fit a co-op castle. Ultimate Richter needs the Saturn disc, so PS1-only players would have no Richter |

## Recommendation: A
- **Players see one Richter and one Maria.** Our builds stay the base: Richter needs only the PS1 disc, and both share Alucard's progression, which is what makes a two-player castle work.
- **The castle rules already cover the gameplay difference.** With every Richter-and-Maria rule off, ours play like the retail ones. A short "Classic" choice in the castle settings could switch all those rules off at once.
- **The Saturn content becomes looks and moves, not more characters.** The coat is an option for whoever plays Richter. Saturn Maria becomes "Maria's moves: Saturn" for whoever plays Maria. Both need the Saturn disc, as now.
- **Ultimate Maria's two sub-weapon slots** are the one thing we'd lose at first. They could return as a castle rule once her glue is ported. If they matter to you now, keep Ultimate Maria until then.
- **Existing castles keep working:** a save made with Ultimate Richter or Maria loads as Richter or Maria, with the castle's rules.

## Questions for Tucker
1. Option A, B or C?
2. If A: keep Saturn Maria as "Maria's Saturn moves", or drop her?
3. If A: should the two sub-weapon slots come back (a castle rule, later), and does it matter if they're missing for a while?
4. If A: add a "Classic Richter and Maria" switch to the castle settings, one switch for all their co-op rules?
