# Hanging onto Bat Alucard (#43)

**Status:** proposed, needs Tucker's approval. It changes the game, so it's a castle rule, off by default (D162).

**Goal:** a partner hangs onto Alucard's bat, at the cost of his speed, to reach what the bat reaches. They can still double-jump, so they can drop off and carry on.

## Options
1. **Carried body (recommended).** A player presses Up beside the bat in a shared room. Each game runs its own player, and the carried player's position follows the bat's, with their own collision off, until they jump, take a hit, or the bat lands or changes form. The bat's speed drops by a set share while carrying. Small: it uses presence, as #98 does, and needs no new link traffic beyond a flag.
2. **Teleport on release.** Nothing moves until the bat's player lets go, then the partner arrives there. Very small, but it isn't hanging on, and it adds little to the existing map teleport.
3. **Full shared physics.** One game runs both players. Rejected: it breaks each game owning its own player.

## Recommendation
Option 1, because each game keeps its own player, and the rest reuses what exists.

## Risks
- Being carried through a wall: on release the player must land somewhere solid. It uses the last safe ground in presence (`groundX`, `groundY`).
- A room change while carried: the carried player follows through the existing door path, which needs testing.
- Online lag: the follower lags the bat by the round trip, which should read as a swaying hang.
- Sequence breaks: reaching rooms early is the point, but a test of progress gates is needed.

## Acceptance criteria
- [ ] With the rule on, a partner grabs the bat, is carried across a gap and up a shaft, and releases onto solid ground: a two-game test in each seat.
- [ ] The bat flies at the slower speed while carrying, and normally after.
- [ ] Jump, a hit, landing and a form change each release the partner safely.
- [ ] A door while carried leaves both players in the same room.
- [ ] With the rule off (the default), nothing changes.
