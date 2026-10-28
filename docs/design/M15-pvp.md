# M15 design: PvP

**Status:** proposal for Tucker's review (2026-10-27). Depends on M13 (the partner as a real player).

## Goal
An option, set by the host, that lets players hurt each other with their attacks: weapons, subweapons, spells and familiars, through the game's own damage rules (defence, elements, knockback, invincibility frames).

## Who decides a hit
| Option | Idea | Verdict |
|---|---|---|
| **A. The victim's game (recommended)** | Just before our hit detection, the partner's live attacks (from M13's simulated body) go into spare effect slots as harmless contact-damage objects. Hit detection hands their attack and element to our player's own damage code. Our game then tells the others: damage, element, direction | ✅ What you see is what hits you; no hit is decided from a stale copy. The game's own damage path, unchanged. |
| B. The attacker's game | The attacker's game decides it hit the partner's body, and tells the victim | ❌ The victim gets hit from where they no longer are |
| C. The room's authority | The room owner decides every hit | ❌ Adds a round trip for one of the two players |

- **The others show it:** each game puts the same hit on its copy of the victim, so the stagger, sound and damage number play there too.
- **Deaths:** a PvP death follows the normal rules (respawn at the partner, D24; no game over). No XP, gold or items change hands.
- **Off by default.** The host's setting covers the whole session and shows in the lobby. Couch and online alike.
- **Not in boss fights, cutscenes or menus:** PvP is off in a locked boss room, while either player is in a scene, and for 3 s after arriving in a room (spawn protection).

## Acceptance criteria
1. `m15_pvp_*`: for each character pairing, each attack type (hand weapon, subweapon, spell, familiar) damages the partner with the game's damage (the victim's defence and resistances apply), knockback away from the attacker, and invincibility frames.
2. Both games show the same hit (stagger, sound, number) within the playout delay.
3. PvP off: no damage in the same scenarios (the default, and every M12 test stays green).
4. No PvP damage in a locked boss room, in a scene, or in the first 3 s in a room.
5. A PvP death respawns at the partner with full HP; nothing else changes.
6. Online with 120 ms lag and 5% loss: no hit counted twice or lost (`online_pvp_lossy`).

## Risks
- **Spare effect slots:** a busy room may have none free. The attack copies take the lowest free slots in 160–191 and skip a frame when none is free (rare; logged).
- **Balance:** Alucard's spells against Richter's HP. Tuned by community playtests, not this milestone.

## Budget
About 3–4 usage windows.
