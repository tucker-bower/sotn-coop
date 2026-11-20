# M22 design: battle royale

## Goal
From a comment on Tucker's Reddit post (2026-11-19), and Tucker: every player spawns somewhere random in a castle (a randomized one, most likely), the playable space shrinks toward a centre, and players fight until one is left. It's also the proof of concept for how many players one game can hold: 8, then 16, then 32.

## What makes it cheaper than co-op
- **No shared rooms.** Each game runs its own enemies, so nobody sends room snapshots, the heaviest traffic co-op has (10-16 KB/s per guest).
- **No progress to share.** Each player keeps their own finds. Only who's alive, where, and the hits travel.
- **Other players don't need full bodies.** PvP already sends the attacker's real hitboxes and lets the victim's own game decide each hit (D132), so other players only need to be **puppets**: their pose drawn from a picture sent over the link, plus their hitboxes and attack primitives (the existing `PRIM` message). A puppet needs no VRAM bank, no partner build and no weapon or familiar copies: about 4 KB of RAM.

## Options
| Option | Idea | Verdict |
|---|---|---|
| **A. Puppets streamed (recommended)** | Each game draws everyone else as a puppet. A pose picture is sent once, then named by its number; hitboxes and attack primitives come with the presence. | ✅ Scales with the network, not with VRAM or RAM; 32 is a measurement, not a wall |
| B. Full bodies | Everyone runs as a partner body, as in co-op | ❌ Capped near 8 by banks, RAM and CPU (M21), and costly in a crowd |
| C. One game runs the fight | The host simulates everyone | ❌ A PS1 can't run 32 players |

**The shrinking castle**
| Option | Idea | Verdict |
|---|---|---|
| **A. A zone of rooms that hurts outside (recommended)** | Each phase, the safe zone becomes the rooms within N map cells of the match's centre. Outside it, you lose a share of your max HP every second. The map shows the zone. | ✅ Uses the map players know; no castle changes |
| B. Sealed doors | Doors outside the zone lock | ❌ Can trap players in dead ends; needs per-room door work |
| C. Forced teleports | Stragglers are moved in | ❌ Takes control away |

## How it plays (option A, A)
- **Lobby:** the host makes a "Battle royale" castle (a game mode, D137's way), picks the randomizer preset or a seed and a player cap (8 to start). Everyone builds the same game disc (as today). Up to the cap may join.
- **Start:** a countdown; each game spawns its player in a random room (from the match's seed and the player's number, so no two land together), at level 1 or a set level.
- **Play:** PvP always on; enemies and finds are each player's own. A death is out: the player watches someone still alive (their camera follows a puppet), or leaves.
- **Zone:** 4-5 phases over about 15 minutes; the centre is a room picked from the seed (the keep, a hall: rooms big enough to fight in). The last phase is the centre room and its neighbours.
- **End:** the last one alive wins; a results screen (place, kills, time) in every game.

## Network
- Links: M17's room (a mesh, with player 0 forwarding for pairs that can't reach each other).
- Each player sends its presence, pose number, hitboxes and attack primitives every frame to players in its stage (about 4-6 KB/s each), and a small roster entry twice a second to everyone (for the map and the alive count). Pose pictures go once to each player that needs them.
- At 32 with everyone in the last room: about 31 x 5 KB/s = 155 KB/s up per player, roughly 1.2 Mbps. Player 0 forwards for pairs that can't link, which needs measuring.

## Acceptance criteria
1. 8, 16 and 32 headless games in one match: everyone spawns apart, the zone shrinks on schedule in every game, deaths and the winner agree in all of them (`br_match_8`, `_16`, `_32`).
2. Puppets: in a room of 8, every other player is drawn in the pose they're in and moves with them; a hit from a puppet's attack lands in the victim's game exactly when its hitbox overlaps (`br_puppet_hits`).
3. Bandwidth measured at 8, 16, 32: no player over 200 KB/s up (`harness/br_measure.py`).
4. 8 launchers online on the playtest network: a full match to a winner (`ui_br_8`).
5. Co-op plays as before (the gate).

## Risks
- **Fairness on lag:** the victim's game decides hits, so on lag an attacker sees a swing connect that doesn't count. Hit markers come only from the victim's verdict.
- **Puppets look plainer** than full bodies: no afterimages, familiars or subweapon trails unless their primitives are streamed (some are, through `PRIM`).
- **32 games to test** need about 5 GB of RAM and every core: full suite only.
- **Spawns on a randomized castle** must avoid rooms you can't leave without a relic: a list of safe spawn rooms per stage, checked by a test.

## Budget
About 3 weeks: puppets (1), the match and zone (1), the lobby, spectating and results (0.5), 8-launcher online test and measurements at 16 and 32 (0.5).
