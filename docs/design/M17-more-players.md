# M17 design: 3+ players

**Status:** approved by Tucker (2026-10-27). Replaces backlog D48. Depends on M13.

## Goal
As many players as the technology holds, each in their own game, one castle. Online first, then couch.

## What changes
The link was built per partner, so most of this is turning "the partner" into "the partners":
- **Link protocol:** a roster (player numbers, names, characters), per-pair links, and events addressed to one player or all.
- **Network shape:**
  | Option | Idea | Verdict |
  |---|---|---|
  | **A. Mesh, the host introduces (recommended)** | Every pair gets its own direct link (M14's ladder); until it opens, or if it never does, the host forwards | ✅ The lowest latency between any two players; the host's upload grows only for pairs that need it |
  | B. Star through the host | Everything goes through the host | ❌ Double latency between guests, and the host's upload grows with every player |
- **Shared rooms:** one authority and any number of guests; the authority streams to each (the delta snapshots already are per receiver).
- **Shared progression:** the same merge rules, from all games (they're unions and maxima, so order doesn't matter).
- **Presence, map, teleport:** every partner on the map, each with their own colour; teleport asks which partner.
- **Bosses:** HP scales with the players in the room (1×, 2×, 2.75×, 3.5×: to tune); aggro picks among all of them; the boss pull-in brings everyone.
- **Respawn:** at the nearest living partner. Everyone dead: reload the last joint save.
- **Castles (M11):** more slots; every joiner keeps a copy.
- **Couch:** 3 or 4 panes in one window (a 2×2 grid), a controller each.

## How many
Limited by, in order: **VRAM** (each partner needs a bank: M13's layout), **CPU** (one partner update per partner per frame, on every machine), and **upload** (about 250 kbit/s per partner each way).
- **Online cap: 4** at first. The suite then measures 5 and 6; the cap goes up if they hold on a mid-range PC.
- **Couch cap: 4** (four emulators on one PC: CPU-bound, measured).
- **Android: 2**, unless the Thor holds 3 (measured).

## Acceptance criteria
1. Online with 3 and 4 games: every M12 shared-room test generalised (`m17_*`): progression converges, shared rooms with one authority and 2–3 guests, bosses with scaled HP and aggro across all players.
2. A guest pair that can't reach each other directly plays through the host's forwarding.
3. Players join and leave mid-session in any order with no lost progress and no stuck games (`m17_join_leave_fuzz`).
4. Couch with 3 and 4 controllers at 60 fps on Tucker's PC.
5. Frame cost and bandwidth measured at 4, 5 and 6 players; the caps set from them (and written in DECISIONS).
6. A 4-player online session with simulated lag and loss holds (`online_4p_lossy`).

## Risks
- **Every test doubles in cost.** The 3–4 player tests go in `--full` only; the everyday suite keeps pairs.
- **Boss balance at 4 players** is a guess until people play it.
- **The host leaving:** for now the session ends for everyone with a joint save; host migration is later work.

## Budget
About 8–10 usage windows.
