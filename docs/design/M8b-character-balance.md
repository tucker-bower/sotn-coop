# M8b design: Richter and Maria balance and the ability mapping

**Status:** proposal 2026-10-20, for Tucker's review. It goes with `docs/design/M8-maria-and-richter.md` (option 3A: one Alucard castle for every character).
**Goal (Tucker):** Richter and Maria progress through the whole game, and never feel more or less powerful than Alucard at any point. Abilities that don't map can be borrowed from Alucard: for example, Richter must be able to pass mist grates.

Facts marked **(code)** are from the decomp (`src/ric`, `src/maria`, `src/dra`, `src/st`). Facts marked **(verify)** are to confirm in the M8 spike, and the rest are game knowledge. The proposals are mine, and every number is a tuning knob.

---

## 1. What each character can do

### Alucard: relics (23 in the US version) (code: `RELIC_*`, `include/game.h`)
| Relic | Effect | Found (first castle, typical route) | Needed for |
|---|---|---|---|
| Cube of Zoe | Candles drop items | Entrance | — |
| Spirit Orb | Damage numbers shown | Marble Gallery | — |
| Faerie Scroll | Enemy names shown | Long Library | — |
| Jewel of Open | Opens blue (sealed) doors | Long Library (Librarian) | **Progress** |
| Soul of Wolf | Wolf form: fast, low profile | Outer Wall | Low gaps (or bat/mist) |
| Leap Stone | Double jump | Castle Keep | Ledges |
| Form of Mist | Mist form: passes grates, brief invulnerability | Colosseum | **Mist grates** |
| Soul of Bat | Bat form: flight | Long Library (after Lesser Demon) | High places |
| Fire of Bat | Bat shoots fireballs | Clock Tower (Karasuman) | — |
| Ghost Card | Ghost familiar | Castle Keep | — |
| Power of Mist | Mist lasts indefinitely | Castle Keep | Long mist passages |
| Echo of Bat | Bat sonar | Olrox (after the fight) | — |
| Sword Card | Sword familiar | Royal Chapel route | — |
| Gravity Boots | Super jump (↓↑ + jump) | Marble Gallery | High places |
| Merman Statue | Calls the ferryman | Underground Caverns | **Progress** |
| Holy Symbol | No damage from poison water | Underground Caverns | **Progress** |
| Demon Card | Demon familiar | Abandoned Mine (Cerberus) | — |
| Bat Card, Faerie Card | Familiars | Various | — |
| Power of Wolf, Skill of Wolf | Wolf dash attack, wolf attacks | Various | — |
| Force of Echo, Gas Cloud | Sonar damages, poison mist | Inverted castle | — |
| Rib/Heart/Tooth/Ring/Eye of Vlad | +10 to a stat each; open the inverted center | Inverted castle | Ending |

**Alucard also grows by:**
- **Levels:** every level gives about +0.6 to each stat, +4.5 MP, +2 hearts and HP by level band (code: `CheckAndDoLevelUp`).
- **Equipment:** weapon ATK, armor DEF, resistances.
- **Spells:** button inputs costing MP, available once known.
- **Familiars:** the cards.

**His power curve, from the boss debug starts (D83):**

| Boss | Level | Attack | Defense | HP |
|---|---|---|---|---|
| Slogra & Gaibon | 8 | 20 | 6 | 97 |
| Olrox | 26 | 42 | 20 | 205 |
| Richter | 38 | 61 | 24 | 343 |

### Richter (code: `src/ric`)
| Move | Input | Damage (code: `gen/subweapons.h`) | In vanilla |
|---|---|---|---|
| Whip | □ | **32**, fixed for the whole game | from start |
| Subweapons | ↑ + □ (hearts) | dagger 20, axe 50, cross 40, holy water 5 + 8/flame, rebound stone 40, vibhuti 20, agunea 20, bible 5, stopwatch | from start |
| Item crash | △ (hearts, 1 crash per subweapon) | 20–80 per hit (hydro storm 80, bible 80, cross 40/60, agunea 80) | from start |
| Flame whip | △ with no subweapon | 64 fire | from start |
| Backflip | jump again near the top of a jump | — | from start |
| High jump | ↓ ↑ + ✕ (also in the air) | 80 on the way up | from start |
| Slide | ↓ + ✕ | passes low gaps | from start |
| Slide kick | ✕ while sliding | 20 | from start |
| Blade dash (tackle) | ↓ ↘ → + □ (also in the air) | 60 | from start |
| Run | land from a moving jump | — | from start |

**What changes for Richter in vanilla (code):**
- No double jump, flight, mist or wolf.
- **HP:** Life Max Up gives him **double** HP. Heart Max Up gives him **nothing** (`func_800FE044` refuses it).
- **Defense:** comes from `g_Status.defenseEquip`, which he can't raise without equipment.
- **XP:** he earns it (`st/collision.h` awards it to anyone), but his overlay never runs the level-up check, so his level stays put **(verify)**.

### Maria (code: `src/maria`, the PSP *Dracula X Chronicles* version)
| Move | Input | Notes | In vanilla |
|---|---|---|---|
| Attack | □ | Her guardian strike (`PL_S_CARDINAL_ATTACK`) | from start |
| Guardians (subweapons) | ↑ + □ (hearts) | Cardinal, Cat (White Tiger), Turtle, Dragon, and the doll | from start |
| Guardian crashes | △ (hearts) | Cardinal, Cat, Turtle, Dragon | from start |
| Double jump | ✕ in the air | `CHECK_DOUBLEJUMP` | from start |
| High jump | ↓ ↑ + ✕ | | from start |
| Dive kick | ↓ + ✕ in the air | Bounces off what it hits (a jump again) | from start |
| Slide | ↓ + ✕ | | from start |
| Dash forward / back | R1 / L1 (in the air too) | `MarSetRun` | from start |
| Blade dash (Guardian Knuckle) | ↓ ↘ → + □ | | from start |

**What changes for Maria:** her damage numbers come from the PSP disc. They're measured in the M8 spike, when her table is built. HP and hearts work as for Richter **(verify)**.

### The shape of the problem
- **Vanilla Richter and Maria start with everything:** all movement, and crashes worth 60–80 per hit. So they're far stronger than Alucard early (Alucard's attack is 20 at Slogra).
- **They never grow:** Richter's whip is 32 at Richter as at Slogra, while Alucard's attack triples and he gains spells and familiars. So they fall behind late.
- **Their movement also skips the castle's gates.** They can reach high places with no relic, so the relic order stops meaning anything.

---

## 2. What the first castle requires
| Gate | Alucard needs | Vanilla Richter / Maria | Proposal |
|---|---|---|---|
| Blue (sealed) doors | Jewel of Open | Same check works for anyone (code: `e_sealed_door.h` reads the relic) | No change |
| Ferryman | Merman Statue | Same (code: `no4/e_ferryman.c`) | No change |
| Candles drop items, damage numbers, enemy names | Cube of Zoe, Spirit Orb, Faerie Scroll | Same (code: stage code reads the relics) | No change |
| Poison water | Holy Symbol | The check is in Alucard's code (code: `692E8.c`, `7879C.c`); Richter's water handling **(verify)** | Same rule in our Richter and Maria |
| High ledges, tall shafts | Leap Stone, Gravity Boots, Soul of Bat | High jump, backflip, double jump from the start | **Gate them** (mapping below) |
| Low gaps | Wolf, bat or mist | Slide from the start | **Gate the slide** |
| **Mist grates** (e.g. the bars before Lesser Demon) | Form of Mist (Power of Mist for long ones) | **Impossible** (collision `EFFECT_MIST_ONLY`) | **Mist Step**, borrowed from Alucard |
| Spike corridor (Catacombs) | Spike Breaker armor worn | Takes spike damage | Owning Spike Breaker protects them |
| Clock room (Marble Gallery center) | Gold + Silver Ring worn | No equipment | Owning both rings opens it |
| Shaft instead of Richter | Holy Glasses worn | — | Owning the glasses counts, or the glasses' new accessory slot (§4) |
| The Librarian's shop | Alucard | Refuses others (code: `lib/e_shop.c:616`) | The world sees Alucard (M8 §3) |
| Cutscenes (Maria, Death, Succubus, Shaft...) | Alucard | Skipped for others (code: `nz0`, `no3`, `dai`, `dre`, `top`, `cen`) | The world sees Alucard; the cutscene shows the player's own character with Alucard's lines |

**Acceptance test for this table:** the reachability audit (§6) checks it room by room.

---

## 3. The mapping: same relic, same kind of power
**Rule:** Richter and Maria start like Alucard after Death: walk, jump, crouch, attack, subweapons, plus each one's basic dodge (Richter's run, Maria's dash, the counterpart of Alucard's backdash). Every other move is unlocked by the relic that gives Alucard the same kind of power.

| Alucard relic | Alucard gets | Richter gets | Maria gets | Work |
|---|---|---|---|---|
| **Leap Stone** | Double jump | **Backflip** (his second jump) | **Double jump** | Gate an existing move |
| **Gravity Boots** | Super jump | **High jump** (and its 80-damage rise) | **High jump** | Gate |
| **Soul of Wolf** | Wolf: fast, through low gaps | **Slide** | **Slide** | Gate |
| **Power of Wolf** | Wolf dash attack | **Slide kick** | **Dive kick** (with bounce) | Gate |
| **Skill of Wolf** | Wolf attacks | **Blade dash** | **Blade dash** (Guardian Knuckle) | Gate |
| **Soul of Bat** | Flight | **Chained backflips:** each backflip re-arms the next, so he climbs like a bat flies, slower | **Cardinal's wings:** the double jump re-arms, so she climbs indefinitely | Small change: reset the second-jump flag |
| **Form of Mist** | Mist: through grates, brief invulnerability | **Mist Step** (borrowed) | **Mist Step** (borrowed) | New: §3.1 |
| **Power of Mist** | Mist lasts | Mist Step for long grates; can be held while ✕ is held | Same | Part of Mist Step |
| **Fire of Bat** | Bat fireballs | **Flame whip:** the whip itself burns (fire + 25%) | **Fire guardian:** her attack burns (fire + 25%) | Small: element and damage on the attack |
| **Echo of Bat** | Sonar | **Item crashes** (all subweapons) | **Guardian crashes** (all four) | Gate |
| **Force of Echo** | Sonar damages (inverted) | **Whip reach + holy damage** | **Guardian homing** | New, small (inverted castle) |
| **Gas Cloud** | Poison mist (inverted) | **Poison crash:** holy water crash poisons | **Turtle crash poisons** | Small |
| **Holy Symbol** | Poison water | Same | Same | Check in our overlays |
| **Jewel of Open, Merman Statue, Cube of Zoe, Spirit Orb, Faerie Scroll** | World | Same | Same | Nothing (code already checks the relic) |
| **Cards** (Bat, Ghost, Faerie, Demon, Sword) | Familiars | **Familiars too** (the servant follows `PLAYER`) **(verify)** | **Familiars too** (fits her guardians) | Spike: do servants run beside our overlays? |
| **Vlad relics** | +10 to a stat | Same, through §4's stats | Same | — |

**Why crashes come with Echo of Bat (Olrox, ~level 26):**
- Crashes are Richter's and Maria's biggest damage, 60–80 per hit.
- Unlocking them mid-game matches when Alucard's damage takes off: his attack goes from 34 to 42 to 56 between Karasuman and Succubus.
- **Alternative (knob):** crashes from the start, priced in hearts, the way Alucard's spells are priced in MP.

### 3.1 Mist Step (borrowed from Alucard)
- **What the player does:** with Form of Mist, Richter or Maria walks into a mist grate and holds toward it with ✕ held. They dissolve (a flicker plus Alucard's mist puff sound), pass through, and reform on the other side. They're invulnerable while passing.
  - Without Power of Mist, only grates up to 2 tiles thick, the same limit Alucard has in practice.
  - With it, any length.
- **How:** the module sees `EFFECT_MIST_ONLY` tiles ahead of the player (stage collision), checks the relic, and moves the player through over a few frames, with collision off.
  - It needs no change to the player overlays, and works the same for both.
  - It's deterministic, so shared rooms stay in step.
- **Not done:** a real mist *form* for Richter and Maria (free movement as mist). That needs new sprites and physics in their overlays, and only grates need it.

---

## 4. Power: keeping pace with Alucard
Richter and Maria use the same `g_Status` as Alucard (HP, hearts, stats, equipment slots). So the plan is to let them use it.

| Axis | Alucard | Proposal for Richter and Maria |
|---|---|---|
| **Levels** | XP → level → stats, HP, MP, hearts | **The same.** Our overlays run the level-up check like Alucard's code does. They already earn XP. |
| **Attack** | Weapon ATK + STR (DRA `make_att`) | **Whip / guardian damage = the game's own attack value for the weapon they "carry" in the right hand.** Picking up a weapon still gives a stat, but they never swing it: Richter keeps whipping, harder. Floor: the vanilla 32. |
| **Subweapons and crashes** | Alucard's subweapons: fixed damage | Fixed damage × (1 + INT / 50) (knob), so they scale like Alucard's spells do with INT |
| **Defense** | Armor, helm, cloak, accessories | **The same slots, the same items:** body, head, cloak and two accessories, equipped in the pause menu. DRA's damage already uses `defenseEquip` for every character (code: `HandleDamage`). |
| **HP** | Levels + Life Max Up (+5) | Levels + Life Max Up. **Normalize** the vanilla double HP for Richter to +5 (knob). |
| **Hearts** | Levels + Heart Max Up | **Let Heart Max Up count** (vanilla refuses it), and +2 per level like Alucard |
| **MP / spells** | MP for spells | No MP; crashes cost hearts (as vanilla), and hearts are their "MP" |
| **Familiars** | Cards | The same, if the spike confirms (§3) |

**The equipment menu:** Richter's and Maria's pause menu today has no equip screen **(verify)**. Two options:
- (a) Open Alucard's equip menu for them. One hook; all item names and stats already work.
- (b) Auto-equip the best item per slot.

**Recommendation:** (a). Players like choosing, and resistances matter (Ice Mail, rings).

---

## 5. Balance targets and how to tune them
**Target:** at every boss, each character is within **±20%** of Alucard on:
1. time to kill the boss
2. damage taken per minute in the boss fight

with the same level, gear and relics: one boss debug start, three characters.

**Tuning knobs** (one table in the overlay build, `M8B_TUNING`):
- attack floor and scale
- the subweapon INT scale
- the relic for crashes (Echo of Bat, or from the start)
- the HP per Life Max Up for Richter
- the hearts per level
- the Mist Step length

**Method:** the boss debug starts already give the right progress at each of the 12 bosses (D83). A bot fight runs three times per boss, once per character, and records time to kill and damage taken. The numbers go in a table in this doc. The knobs change until every row is within the band, and then Tucker plays the outliers.

---

## 6. Acceptance criteria (M8b)
1. **Relics gate the moves** (`m8b_relic_gates`): for each row of §3, the move doesn't work without the relic and does with it, for Richter and for Maria.
2. **Mist Step** (`m8b_mist_step`): Richter and Maria pass the Lesser Demon bars with Form of Mist and can't without it. With Power of Mist they pass a long grate. Shared rooms stay in step (session test, mixed team).
3. **Reachability audit** (`m8b_reachability`): from the boss debug starts, a route bot shows that every pre-inverted relic, boss and save room can be reached by each character with exactly the relics a player has by then. Nothing is reachable earlier than Alucard can reach it, give or take one room.
4. **Power curve** (`m8b_power_curve`): at all 12 boss starts, time to kill and damage taken for Richter and Maria are within ±20% of Alucard's. The table goes into this doc.
5. **Growth works** (`m8b_growth`): Richter and Maria level up, equip armor and accessories (defense and resistances apply), and their attack follows their weapon and STR.

---

## 7. Decisions for Tucker
1. **The mapping table (§3).** Is "same relic, same kind of power" the right rule, and are any rows wrong for you? The rows to look at:
   - Soul of Bat → chained backflips (Richter) and re-arming double jump (Maria)
   - Echo of Bat → crashes
   - Fire of Bat → a burning attack
2. **Crashes:** gated by Echo of Bat (recommended), or from the start priced in hearts?
3. **Equipment for Richter and Maria (§4):** use Alucard's equip menu (recommended), or auto-equip?
4. **Weapons for Richter and Maria:** a carried weapon only raises their attack (recommended), or do you want visible weapon swaps? Visible swaps aren't possible without new sprites.

## Appendix: where the game checks the character (code, for the M8 spike)
- **Player dispatch** (must see the real character):
  - `dra/game_handlers.c` (overlay choice, ~10 sites)
  - `dra/cd.c:678` (overlay load)
  - `dra/5087C.c:1922-1939`
  - `dra/6BF64.c`, `dra/7879C.c:1788`
  - `dra/5F60C.c:754,1094` (Maria specifics)
- **World and story** (must see Alucard):
  - cutscenes: `st/nz0/cutscene.c:91`, `st/no3/cutscene.c:250,268`, `st/dai/e_cutscene_dialogue.c:289`, `st/dre/e_cutscene_dialogue.c:252,280`, `st/top/cutscene.c:74`, `boss/mar/cutscene.c:85`
  - `st/cen/e_chamber.c:124,596,672`
  - `st/lib/e_shop.c:616,3685`
  - `st/no1/e_red_door.c:152`
  - `dra/5F60C.c:86,223,1201,1247`
  - `dra/4A538.c:286`
  - `dra/5087C.c:1268,1433,1637`
  - `dra/5D5BC.c:382,395` (vessels)
- **Inverted castle** (later): `st/rcen`, `st/rnz1`, `st/rno1`, `boss/rbo2`.
