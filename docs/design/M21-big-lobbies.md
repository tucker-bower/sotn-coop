# M21 design: big lobbies (8, 16, 32 players)

## Goal
Tucker (2026-11-19): "Can we get 8, 16 or even 32 people in a lobby at once?" One room code, one castle, up to 32 players, each in their own game, sharing progress, as M17 does for four.

## What limits it today (measured 2026-11-19)
| Limit | Today (M17) | Why |
|---|---|---|
| **Bodies drawn in full** | 3 partners | Each full body needs a VRAM bank of its own (4 banks: spare address bits, D125/D214), about 125 KB of the 8 MB RAM (weapon and familiar copies), and 45-85 of the frame's 263 scanlines at the 200% CPU clock (D129). RAM has about 130 KB free: a fourth full partner doesn't fit. |
| **Emulated CPU** | 200% clock | Not the limit on a PC: 800% costs about 2 ms a frame here (`harness/m17_measure.py`, no drawing). Phones are slower. |
| **Network** | full mesh, 16 KB/s a link | 31 links of 16 KB/s is 500 KB/s each way per player: too much. Most of it (presence 60 times a second, room snapshots) only matters to players in the same room. |
| **Shared rooms** | one authority, any guests | Snapshots go from the authority to each guest: 31 guests in one room would be 500 KB/s up for the authority. |
| **Mailbox** | 3 partner slots | Fixed layout (`link.h` `more[]`). |

## Options
| Option | Idea | Verdict |
|---|---|---|
| **A. Big lobby, near players in full (recommended)** | Up to 32 per code. In your game, the 3 partners nearest you in your room get full bodies (as now, re-chosen as people move); any more in your room are **light puppets**: their pose drawn from sprite pixels sent over the link (the M1 ghost, `PRESENCE_SPRITE`), no attacks of their own on your screen; everyone else is a map marker. Links carry presence and snapshots only between players in the same stage; progress events and a 2-per-second roster (where everyone is) go to all. | ✅ Fits RAM, VRAM and bandwidth; every find still shared; feels like a full castle |
| B. Everyone in full | 31 bodies in every game | ❌ Needs 31 VRAM banks and 4 MB of RAM copies; impossible on the PS1's memory map |
| C. Rooms of 4, many rooms per code | A code makes several 4-player parties that share progress but never see each other | ⚠️ Simplest, but players can't meet beyond their party |

## How A works
- **Membership:** the Room (`link/mesh.py`) seats up to 32. Player 0 tells everyone the roster; pairs link directly when they come near (same stage) and drop the link when apart, falling back through player 0 as now. Idle pairs keep only a heartbeat.
- **Interest:** presence every frame, sprites and snapshots only to players in your stage; a compact roster entry (stage, room, x, y, character, HP) twice a second to all, for the map, teleports and the lobby list.
- **Slots:** the mailbox keeps its 3 full partner slots, filled with the nearest; a new table of up to 28 light entries (presence plus a sprite frame each, about 2 KB apiece) for the rest of your room, and the roster for the map. RAM: about 60 KB, in the gaps.
- **Shared rooms:** unchanged (one authority, any guests); a room holds at most 8 players at once (a ninth is kept at the door with "Room full"), which keeps the authority's upload near 120 KB/s.
- **Rules:** enemy HP scales with the players in the room, not the lobby, on D213's curve, capped at 8. Bosses aggro among the players in their room. Teleports go to any player on the map.
- **Saves:** M17's per-player slots, up to 32 in a castle file.
- **Launcher:** the lobby list, the pause menu's "who's in" and the map show everyone by name; the host can set a cap (4, 8, 16, 32).

## Acceptance criteria
1. 8, then 16, then 32 games on one code (the harness, headless): every game seated, progress converges (`m21_progress_32`), each game's map shows everyone.
2. In a room of 8: the 3 nearest are full bodies, the other 4 are puppets that move and animate with their players (`m21_room_of_8`).
3. A ninth player is held at the door of a room of 8 (`m21_room_full`).
4. Bandwidth measured at 8, 16, 32: no player sends more than 150 KB/s, and player 0 no more than 300 KB/s, with everyone in one stage (`harness/m21_measure.py`).
5. Online, 8 launchers on the playtest network for 5 minutes: no stuck game, one purse (`online_8p_lossy`).
6. A 4-player session plays exactly as M17's (the gate).

## Risks
- **Puppets don't hit:** a puppet's attacks show only in its own player's game. Its hits on enemies still count (they reach the authority as events, as a guest's do), but you won't see its whip. If that feels wrong, the near-3 count could grow by sharing one VRAM bank among same-character partners (each needs only its current pose's tiles: research first).
- **Phones:** more links and puppets cost CPU; Android may need a lower cap (8).
- **Testing 32:** 32 headless games need about 5 GB of RAM and every core; the full suite only.

## Budget
Option A: about 2-3 weeks of agent time in steps: roster and interest (1), puppets in your room (2), room cap and rules (3), the launcher (4), 8-launcher playtest build (5).
