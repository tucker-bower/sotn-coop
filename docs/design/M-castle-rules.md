# Castle rules

Tucker, 2026-11-01: every feature that changes vanilla game logic is a toggleable option, scoped to the castle and shared with the partner. Options › Open settings holds them. Decision: D162.

## Options considered
1. **Global settings, with the host's copied for a session** (how PvP worked). Rejected: a castle would change character with whoever hosts it.
2. **Rules in `castle.json`, sent in HELO, written to the mailbox by the host** (chosen). A setting is data on the castle, so copies, savestates and joiners follow it. All-zero mailbox words mean the game as built, so nothing else in the suite changes.
3. **Rules inside the joint save.** They'd survive a file copy of the save alone, but SaveData has no spare room, and the rules would only change at a load.

## How it works
- **Schema:** `launcher/rules.py`: sliders, toggles, defaults, and `encode()`. A castle with no `rules` takes the defaults, starting from the app's old global PvP and aggro settings.
- **Game:** `CoopLink.rulesOff` (one bit per rule turned off) and five percentages, written by the host every frame so a savestate can't undo them. Bits 24 and up reach the player overlays through `g_CoopOptions`.
- **Damage taken** needs no DRA hook: hit detection leaves the damage in `PLAYER.hitPoints`, and the module scales it before the player's update reads it, after Alucard's defense. **Damage dealt** wraps `g_api.DealDamage`, which every stage's hit detection calls.
- **Sharing:** the host's rules go out in every HELO. The joiner stores them on its copy and follows a change within a second. Only the host can edit them during a session.
- **UI:** Options › Open settings, the pause menu's Castle rules (controllers, phones) and Settings › Castle rules. In a game it opens that castle; from the menus, it asks which.

## The rules
| Rule | Kind | Default |
|---|---|---|
| XP gain, damage dealt, damage taken | 25–400% | 100% |
| Enemy HP with a partner | 50–400% | 200% |
| Enemy HP alone | 50–400% | 100% |
| Boss aggro | 0–100% | 50% |
| One shared level, one purse, revive at your partner, partner's faerie revives | toggle | on |
| Bosses bring your partner, scenes bring your partner, teleport from the map, enemies pick the nearer player | toggle | on |
| Richter and Maria level up, use Alucard's stats (STR, INT, defense, resistances: #160), relics teach them, extra jumps, off-hand weapons, their familiars | toggle | on |
| PvP, button remap (both players, face and shoulder buttons) | toggle | off |

**Not toggles:** castle flags, pausing, scene votes, the map, items and relics, shared rooms, the partner's body, joint saves, and the shared death of Richter and Dracula. These are what co-op is: turning one off leaves two games that disagree about the castle. Controls (shortcuts, spells) stay per player, because they're about a player's hands, not the castle.

## Risks
- Turning off relic moves or extra jumps can make the castle uncompletable for Richter and Maria. The rule's description says so.
- Revive off with a partner who plays on: the fallen player waits until the partner falls or leaves.
- Editing rules pauses that player's game, like any menu. Online, a long edit can show the partner "Lost contact" until it ends.
- Damage taken doesn't scale grabs or poison water, which skip `PLAYER.hitPoints`.
- A new feature that changes the game must add a rule here, or be argued onto the list above.

## Acceptance criteria
1. Every rule's default plays as before: everyday suite, with no rules set.
2. Each rule changes the game: `rules_*` tests, in two real games.
3. Rules belong to a castle, and a joiner's copy takes the host's: `launcher_rules`, `rules_host_tells_joiner`.
4. Options › Open settings and the pause menu edit them: `ui_menus`, `ui_couch`.
