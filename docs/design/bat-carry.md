# Hanging onto Bat Alucard (#43)

**Status:** option 1 approved by Tucker, built (D167). It changes the game, so it's a castle rule, off by default (D162).

**Goal:** a partner hangs onto Alucard's bat, at the cost of his speed, to reach what the bat reaches. They can still double-jump, so they can drop off and carry on.

## Options
1. **Carried body (recommended).** A player presses Up beside the bat in a shared room. Each game runs its own player, and the carried player's position follows the bat's, with their own collision off, until they jump, take a hit, or the bat lands or changes form. The bat's speed drops by a set share while carrying. Small: it uses presence, as #98 does, and needs no new link traffic beyond a flag.
2. **Teleport on release.** Nothing moves until the bat's player lets go, then the partner arrives there. Very small, but it isn't hanging on, and it adds little to the existing map teleport.
3. **Full shared physics.** One game runs both players. Rejected: it breaks each game owning its own player.

## Recommendation
Option 1, because each game keeps its own player, and the rest reuses what exists.

## Risks
- Being carried through a wall: on release the player must land somewhere solid. The carried player's body is checked against the room every frame, and a gap with no room for it drops them off.
- A room change while carried: the carried player follows through the existing door path, which needs testing.
- Online lag: the follower lags the bat by the round trip, which should read as a swaying hang.
- Sequence breaks: reaching rooms early is the point, but a test of progress gates is needed.

## Acceptance criteria
- [x] With the rule on, a partner grabs the bat, is carried across a room, and releases onto solid ground, in each seat: `bat_carry_alucard`, `bat_carry_richter`, `bat_carry_other_seat`, `bat_carry_on_a_bad_connection`.
- [x] The bat flies at the slower speed while carrying, and normally after: `bat_carry_is_slower`.
- [x] Jump, a hit, landing and a form change each release the partner safely: `bat_carry_*_drops_off`.
- [x] A door while carried leaves both players in the same room: `bat_carry_through_a_door`.
- [x] With the rule off (the default), nothing changes: `bat_carry_off_by_default`.
- [x] Each game draws the other right: the bat's game draws the rider hanging under it (its copy of the rider is held where the rider's game holds them), and after a door the rider's game still draws a bat (a copy made on foot gets the partner's form button): `bat_carry_rider_hangs_in_the_bats_game`, `bat_carry_through_a_door_still_a_bat` (#262).
- [ ] Progress gates aren't tested, and only the entrance hall's door is. Sequence breaks are a question for playtests.
