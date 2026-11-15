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

## Implementation plan (2026-11-14)
Everything today assumes one partner: about 1,500 references across `module/`, `link/`, `launcher/` and `harness/`. So the build goes in steps, each shippable with two players unchanged and each with its own tests.

**The hard limit is VRAM.** A partner's body draws from a full copy of the texture half in its own bank (M13). `patches/swanstation.patch` gives one extra bank, chosen per primitive by spare bits: y bit 9 for uploads, texpage bit 14 and CLUT bit 15. A third and fourth player need banks 2 and 3, so two bits per primitive:
- **Uploads and fills:** y bits 9 and 10 (VRAM 1024×2048, 4 MB). Retail never sets either.
- **Textures:** texpage bits 14 and 15, both unused by the PS1.
- **Palettes:** CLUT bit 15, plus CLUT x bit 5. The palette rows a body is banked from (`partner.c`, y 0xF0–0xFF) all have x < 256, so x bit 5 (x ≥ 512) is free there. The core reads `(bit15 | xbit5 << 1)` as the bank only when bit 15 is set, so bank 1's encoding stays as it is today and two-player discs and savestates don't change.
- **Cost:** new cores for Windows, Linux and Android (`bootstrap.sh`), `harness/core_check.py` identical on all three, and 20 MB savestates (v59; v58 still loads).

**Steps** (each a PR; acceptance criteria above, plus "two players unchanged": the gate passes):
1. **Core: four banks** (the patch above). `core_check`, plus a test that draws one sprite from each bank.
2. **Mailbox: N partners.** `link.h`'s partner fields become `partners[3]` (presence, pad, sprites, prims, hits, snapshots in), each with its own 8 MB copies (weapons, familiar, status: 0x10000 each). Partner 0 is today's partner, and every module system still reads only it. `test_layout` checks it.
3. **Hosts: the roster and the mesh.** `transport.py` is per peer; `host.py` keeps one per partner, maps each to a mailbox slot, and forwards between guests who can't reach each other (criterion 2). Python-only, so it's tested with fake games (`test_connect` with three).
4. **Bodies: one per partner.** `partner.c`'s single body becomes an array: swap regions per body, bank k for partner k, and its own drawing pass. Tested as `m17_bodies_*` with three games.
5. **Shared rooms, progression, bosses, respawn** (criteria 1 and 3): the authority streams to each guest, merges take every partner, boss HP scales by players in the room, and respawn goes to the nearest living partner.
6. **Launcher:** a 4-player lobby, the map's colours, teleport choosing a partner, and couch 2×2 (criterion 4). Then the measurements and caps (criteria 5 and 6).
