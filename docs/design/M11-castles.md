# M11 design: castles (drop-in saves, solo, shared level)

**Status:** approved by Tucker (2026-10-25), built on branch `coop-m11-castles` (stacked on M9). Implementation defaults: D98.

## Goal
Players can finish a playthrough with whoever is around. One night solo, the next with a friend, a week later with another friend. The friend who joined keeps a copy of that castle and can play it solo or host it for someone else.

## The model
- **A castle is the only save concept.** It holds the shared world and two player slots. There are no player names, profiles or seats.
- **The shared world:** castle flags, the map, relics, equipment, max HP/MP/Hearts, the gold purse (all shared already), and now **level and XP**.
- **Slot 1 is always the player on this machine.** Slot 2 is whoever plays with them: a couch P2, or an online partner. A slot holds what the shared world doesn't: the equipped loadout, consumables, current HP/MP, and the stat coin-flips from level-ups.
- **The host's castle is played.** The host picks it when hosting (or starts a new one). The joiner picks nothing.
- **The joiner gets a copy.** At every joint save, the joiner's machine stores the host's castle, with the joiner's own state in slot 1. Later, the joiner can continue it solo, on the couch, or host it online.
- **Nothing the joiner played is ever overwritten** (see "Copies" below).
- **Solo turns off the duo balancing:** 2× boss HP, aggro switching, and the XP cut.
- **Old playthroughs aren't converted** (Tucker). They stay on disk, untouched, and aren't listed.

## Names
- **Format:** `<name>_<created>`, e.g. `Tucker_2026-10-25-21:40`.
  - `name` is what the host typed at SOTN's own name entry (`SaveInfo.name`, in every save).
  - `created` is when the castle was started. It never changes, so a castle never renames itself.
- A brand-new castle is shown as `New castle_2026-10-25-21:40` until its first save carries the typed name.
- **The folder** uses only file-safe characters (`Tucker_2026-10-25-21-40`), because Windows doesn't allow `:`.
- **The castle list** sorts by last played and shows each castle's area, level and last-played date.
- A joiner's copy keeps the host's name ("I played on Tucker's castle").

## Shared level (XP)
SOTN gives kill XP through one function, `func_800FE044(amount, enemyLevel)` (DRA `5D5BC.c`). It scales the XP by the level gap, then adds it to `g_Status.exp`. The game's own `CheckAndDoLevelUp`, which runs every frame, then levels up and plays the animation.

| Option | How | Verdict |
|---|---|---|
| **A. Halve at the grant, share the gain (recommended)** | Our existing `GrantWrap` (`module/progress.c`, already hooked: the shared relics and Life/Heart Ups go through it) halves a kill's `amount` while a partner is linked (minimum 1), and emits `EV_EXP` with the XP actually gained. The partner adds it to its own `g_Status.exp`, and its game levels up the normal way. | ✅ No new DRA hook (D33). Level-ups happen at the right moment on both sides, with their animation. |
| B. Halve afterwards | Watch `g_Status.exp` like gold, and take half of each increase back | ❌ The game has already levelled up on the full amount by then |
| C. Sync level and stats directly | Copy level, max HP/MP and stats across | ❌ Fights the game's own level-up code and its animation, and double-counts max HP |

- **Both games stay at the same level and XP.** That's enforced again on load: a castle's slot 2 takes slot 1's level and XP.
- **Level-up stat gains** (SOTN flips a coin per stat) stay each game's own, so two players at the same level can differ by a point or two of STR. Max HP from level-ups isn't shared as an event, so it isn't counted twice.
- **"Partner linked"** means the same rule as 2× boss HP (D25): the partner's game was heard from in the last 10 s. With one shared pool and two players killing, half XP per kill levels you at about the solo rate.

## Copies (the joiner's side)
- **The castle's identity:** each castle has an id (random, set when created) and a save count. On connect, the host sends `{"op": "castle", "id", "name", "created"}` over the existing reliable control channel (`TAG_CTRL`). The joiner's joint saves go into its copy of that castle, and the copy stores the slots swapped, so slot 1 is the joiner.
- **Which copy is updated:**
  - **(rec.)** The joiner's copy of this castle id is updated in place, as long as the joiner hasn't played it since it last received it.
  - If the joiner has played it since (solo, or hosting it), that copy is kept, and the incoming one becomes a new entry, `Tucker_2026-10-25-21:40 (2)`.
  - So nothing a player played is ever overwritten, and a copy that only ever received gets "new info only".
- Options considered:
  - a new entry every session (clutters the list after a few nights);
  - always overwrite (loses a joiner's solo progress);
  - merging (Tucker: no).

## Slots when a partner joins
- **Slot 2 exists:** the partner takes it, inheriting the last partner's loadout, consumables and HP/MP. Level and gear are shared anyway, and the partner arrives in the host's save room.
- **Slot 2 doesn't exist yet** (a castle only played solo): it starts as a copy of slot 1. That's the same level, gear and items (potions included), in the host's save room. The character comes from the lobby, as now (D85).

## Launcher flow
- **Home:** Solo · Couch · Online.
- **Solo, Couch and Host online** each show the castle list: *New castle*, then castles by last played. Joining online asks for the room code only.
- **Solo** runs one game with no link. A solo save writes slot 1 and keeps slot 2 untouched.
- **What's kept as is:** joint saves at save rooms, Continue, both-dead reload, the cards, and event savestates. They move from `playthroughs/` into `castles/`, one folder per castle: `castle.json` (id, name, created, played, saves, where it came from) plus `castle.coop` (slot 1, slot 2).

## Acceptance criteria
1. **Solo** (`m11_solo`): a solo castle starts, saves, and continues from the launcher's flow. Bosses have 1× HP, the aggro never switches, and a kill gives the game's full XP.
2. **Shared level** (`m11_shared_xp`, session test): kills by either player add half the XP (minimum 1) to both games. After enough kills for a level-up, both are the same level with the same XP, and the other game showed the level-up too.
3. **The joiner gets a copy** (`m11_copy`): A hosts castle X, B joins, they joint-save. B's machine now has X: same id and name, with B's state in slot 1. A's X is unchanged except for the save.
4. **A copy can be hosted** (`m11_copy_hosted`, three instances in turn): B hosts its copy of X and C joins. B plays slot 1 (its own state), C gets slot 2, and C now has a copy too. A's X is untouched.
5. **Nothing played is overwritten** (`m11_no_overwrite`): B plays its copy of X solo, then joins A's X again. B ends up with two entries, its solo copy unchanged and `… (2)` from A. When B hasn't played its copy, it's updated in place instead.
6. **A solo-only castle takes a partner** (`m11_slot2_clone`): slot 2 starts as a copy of slot 1, in the host's save room, at the same level.
7. **Names** (`launcher/test_castles.py`): `Tucker_2026-10-25-21:40` from the typed name, with a file-safe folder, the list sorted by last played, and `New castle_…` before the first save.
8. **Couch and Android:** couch plays a castle (P1 slot 1, P2 slot 2). The cross-play tests (`android_pc`, `android_room`) pass with a joint save that lands as a copy on the emulator.

## Risks
- **Richter and Maria XP:** our Richter and Maria may not earn XP through `func_800FE044` the way Alucard does. A spike checks this first. If they don't, their kills get the same `EV_EXP` emit from their own kill path.
- **An idle partner** who is linked but just standing in a menu still halves your XP. That's acceptable, and it's the same rule as boss HP.
- **Kills while the link is briefly down** give full XP, which is shared once the events get through (they're reliable). That's a small, rare drift, fixed again on the next load.
- **The wire changes** (a new event and a control op): version bump, and the version check already tells mismatched partners by name.
- **The cost:** about 2 usage windows. The XP hook is small; most of the work is the launcher's castle list and the copy rules, with their tests.

## Defaults I chose (reversible)
- The castle id/save count for the copy rule; `New castle_…` before the typed name exists; slot 2 cloned from slot 1 (potions included); the folder name with `-` for `:`; old playthroughs hidden, not deleted.
