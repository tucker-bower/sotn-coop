# M8b design: Richter and Maria balance and the ability mapping

**Status:** approved by Tucker 2026-10-21 (D85, D86), with one-button moves (§3.2) and off-hand weapons (§4.1). In progress on `coop-m8-maria-richter`. It goes with `docs/design/M8-maria-and-richter.md` (option 3A: one Alucard castle for every character).
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

**The safety net (Tucker):** if a spot turns out to need Alucard and the audit missed it, a team with an Alucard player still gets through: the Alucard player passes it and the partner teleports to them from the map (M3). So a miss blocks only teams without an Alucard (Richter + Maria, Maria + Maria...) until it's fixed. The goal stays full parity, so the audit still has to fix every miss it finds.

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
- **What the player does:** with Form of Mist, Richter or Maria keeps walking into a mist grate for half a second. They dissolve (a flicker and Alucard's transform sound), drift through unseen, and reform on the other side, invulnerable throughout. (Holding ✕ was the first idea, but ✕ jumps.)
  - Without Power of Mist, only grates up to about 2 tiles thick, the same limit Alucard has in practice.
  - With it, any length.
- **How (built):** the module sees mist-only tiles ahead of the player (stage collision) and checks the relic. While they drift, their collision ignores mist-only tiles, exactly as Alucard's does in mist form: the module swaps `g_api.CheckCollision` for the frame and walks them through.
  - It needs no change to the player overlays, and works the same for both.
  - It's deterministic, so shared rooms stay in step.
- **Not done:** a real mist *form* for Richter and Maria (free movement as mist). That needs new sprites and physics in their overlays, and only grates need it.

### 3.2 One-button moves (Tucker, 2026-10-21)
**Every shortcut here is optional, per player:** each player turns them on or off in the launcher (the lobby's character card, and Settings › Controls), and the choice is remembered per controller seat. Off, the game plays exactly as vanilla.

The fighting-game inputs also get a button of their own, on buttons the character doesn't use in vanilla. The original inputs keep working, and the same relic gates both.

| Move | Vanilla input | Its own button | Who |
|---|---|---|---|
| High jump | ↓ ↑ + ✕ | **L2** (left trigger), on the ground or in the air | Richter, Maria |
| Blade dash | ↓ ↘ → + □ | **R2** (right trigger), toward the facing direction (or the one held) | Richter, Maria |
| Off-hand attack (§4.1) | — | **○** | Richter, Maria |

**Why these buttons:**
- **Free in vanilla (code):** Richter's overlay reads only the d-pad, □, ✕ and △ (○ and L2 only in its debug mode, which isn't in retail builds). Maria's reads the same plus L1/R1 for her dashes. So L2, R2 and ○ are free for both, and Maria's dashes keep L1/R1.
- **Nothing new to carry:** they're ordinary PlayStation buttons, so the harness, recordings and online play carry them as they are, and each game stays deterministic.
- **Discoverable:** How to play and the lobby's character card show them.

**Alucard (Tucker: in M8):** he already uses every PlayStation button: □ ○ for his hands and all four shoulders for wolf, mist, bat (code: `g_ButtonMask`). His fighting-game inputs are spells (Soul Steal, Hellfire, Dark Metamorphosis...). A modern pad has buttons the PlayStation lacks: L3, R3 and the right stick.
- The launcher would send them to the game as one extra byte with the pad, through the mailbox. It's recorded with the inputs, so it stays deterministic.
- The module casts a spell Alucard has learned, for its usual MP. Right stick ↑ → ↓ ← would be four spells, picked in Settings › Controls.

---

## 4. Power: keeping pace with Alucard
Richter and Maria use the same `g_Status` as Alucard (HP, hearts, stats, equipment slots). So the plan is to let them use it.

| Axis | Alucard | Proposal for Richter and Maria |
|---|---|---|
| **Levels** | XP → level → stats, HP, MP, hearts | **The same.** Our overlays run the level-up check like Alucard's code does. They already earn XP. |
| **Attack** | Weapon ATK + STR (DRA `make_att`) | **Whip / guardians:** the vanilla 32 plus a share of STR, so they grow with levels (knob). **Off hand:** any weapon found, swung with ○ at its own ATK + STR (§4.1). |
| **Subweapons and crashes** | Alucard's subweapons: fixed damage | Fixed damage × (1 + INT / 50) (knob), so they scale like Alucard's spells do with INT |
| **Defense** | Armor, helm, cloak, accessories | **The same slots, the same items:** body, head, cloak and two accessories, equipped in the pause menu. DRA's damage already uses `defenseEquip` for every character (code: `HandleDamage`). |
| **HP** | Levels + Life Max Up (+5) | Levels + Life Max Up. **Normalize** the vanilla double HP for Richter to +5 (knob). |
| **Hearts** | Levels + Heart Max Up | **Let Heart Max Up count** (vanilla refuses it), and +2 per level like Alucard |
| **MP / spells** | MP for spells | No MP; crashes cost hearts (as vanilla), and hearts are their "MP" |
| **Familiars** | Cards | The same, if the spike confirms (§3) |

**The equipment menu:** Richter's and Maria's pause menu today has no equip screen **(verify)**. Two options:
- (a) Open Alucard's equip menu for them. One hook; all item names and stats already work.
- (b) Auto-equip the best item per slot.

**Tucker: (a).** Players like choosing, and resistances matter (Ice Mail, rings). The menu also holds the off-hand weapon (§4.1).

### 4.1 Off-hand weapons (Tucker, 2026-10-21)
Richter always has his whip and Maria her guardians. In the other hand, each can equip any weapon or hand item they find, and use it with its own button, the way Alucard has two hands.
- **Equip:** in Alucard's equip menu.
  - The whip hand shows the Vampire Killer (Maria's: her guardians), fixed.
  - The other hand takes anything Alucard could hold there.
- **Use:** ○ (§3.2).

**How Alucard's weapons work (code):** each weapon class has an overlay (`src/weapon/w_*.c`, about 60 of them; `w_000` alone covers 23 swords). The overlay draws the weapon and places its hitbox by following Alucard's own swing animation, reading the player's animation frame 10–40 times per overlay. Richter and Maria have no such animation, so the overlays can't run for them as they are.

| Option | Idea | Verdict |
|---|---|---|
| **A. Each weapon class on one of their own poses (Tucker: approved, existing art only)** | Each class (sword, short sword, greatsword, spear, club, fist, katana...) gets a Richter pose and a Maria pose from their existing sprites (the whip swing, the subweapon throw, the blade dash's punch). A small module entity draws **the weapon's own sprite** (from its overlay's graphics) as an arc or a thrust, by class. Damage, element and hits use the game's own weapon stats through DRA's normal damage, so ATK, STR and elements work as for Alucard. | ✅ **Recommended.** Every weapon works and looks like itself, with no new art. |
| B. The real weapon overlays, fed a fake Alucard swing | The module gives each overlay the animation frames it expects | ❌ About 60 overlays expect Alucard's player state: high risk, a bug hunt per weapon |
| C. Stats only (the earlier proposal) | A carried weapon only raises the whip's damage | ❌ Tucker wants to use the weapons |

**Existing art only (Tucker):** no new animations, poses or drawn art. The swing is made only from the game's own sprites: Richter's and Maria's existing frames, and the weapon's own frames from Alucard's swing, placed and timed so the swing looks as natural as possible.

**Other hand items under A:**
- **Shields** add their DEF. There's no guard pose, so no blocking.
- **Potions and food** are used as Alucard uses them.
- **Thrown items** (TNT, Karma Coin...) are thrown with the subweapon throw.

**Weapon specials** get their basic swing only, and can be added one by one later. Examples: Crissaegrim's multi-hit, Muramasa's growth, the Shield Rod's spells, sword button techniques.

**Spike first:**
- Alucard's hand weapons have their own VRAM slots: check that they're free with Richter or Maria loaded.
- Check that the item-use effects run for them.

---

## 5. Balance targets and how to tune them
**Target:** at every boss, each character is within **±20%** of Alucard on:
1. time to kill the boss
2. damage taken per minute in the boss fight

with the same level, gear and relics: one boss debug start, three characters. Richter and Maria hold the start's best weapon in their off hand, and the bot uses both attacks.

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
5. **Growth works** (`m8b_growth`): Richter and Maria level up and equip armor and accessories, and defense and resistances apply. The whip's and guardians' damage follows STR.
6. **One-button moves** (`m8b_buttons`):
   - With shortcuts on, L2 does the high jump and R2 the blade dash for Richter and Maria, gated by the same relics as the original inputs, which still work. Maria's L1/R1 dashes are unchanged.
   - With them off, L2 and R2 do nothing for them, as in vanilla.
   - For Alucard, with shortcuts on, each right-stick direction casts its chosen spell if he knows it, for its MP.
   - Couch: P1 on and P2 off (and the reverse) works in one session, and the choice is remembered.
7. **Off-hand weapons** (`m8b_offhand`):
   - For Richter and Maria, one weapon of every class equips in the other hand and hits with ○. The damage matches DRA's formula for that weapon, ATK + STR, with its element.
   - Each one shows its own sprite (screenshots in the PR).
   - A shield adds its DEF, a potion heals and a thrown item is thrown.
   - The same holds in a mixed-team shared room (the partner's puppet shows the swing).

---

## 7. Tucker's answers (2026-10-21) and what's left
**Answered:**
- The mapping table and the balance plan are accepted ("the mappings and balance all look really great"). That includes crashes gated by Echo of Bat.
- Equipment through Alucard's equip menu.
- Fighting-game inputs get their own buttons (§3.2).
- Found weapons go in the other hand, on their own button (§4.1).
- An Alucard player is the safety net for any spot the audit misses (§2).

**Final (2026-10-21):**
- Off-hand weapons: option A, existing art only.
- Alucard's spell shortcuts: in M8.
- All button shortcuts are optional, per player, set in the launcher.

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
