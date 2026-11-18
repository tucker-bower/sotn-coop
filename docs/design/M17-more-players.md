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
- **Bosses:** enemy HP scales with the players in the session (1×, 2×, 2.75×, 3.5×: D213, already in); aggro picks among all of them; the boss pull-in brings everyone.
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
- **Palettes:** CLUT bit 15 picks a bank, and CLUT x bits 4–5 say which: bank = 1 + those bits. Every banked palette today has x < 256: the body's rows (`partner.c` `BankClut`: y 0xF0–0xFF) and the off-hand weapons' (`offhand.c`: y 0x1F0+). So those bits are always 0 there, bank 1 is encoded as it is now, and two-player discs and savestates don't change.
- **Textures:** bank = texpage bit 14 | bit 15 << 1, so bank 1 is still bit 14 alone.
- **Cost:** new cores for Windows, Linux and Android (`bootstrap.sh`), `harness/core_check.py` identical on all three, and 20 MB savestates (v59; v58 still loads).

**Steps** (each a PR; acceptance criteria above, plus "two players unchanged": the gate passes):
1. **Core: four banks** (the patch above). `core_check`, plus a test that draws one sprite from each bank.
**The second limit is the 8 MB RAM: it's nearly full** (`coop_api.h`, `link.h`: blobs, partner builds, F_GAME copies, portraits, weapon and familiar copies up to 0x80800000). Each extra partner needs about 0x21000 bytes for its weapon, familiar and status copies. Worse, the Richter and Maria partner builds are linked at one address each (`PARTNER_RIC_ADDR`, `PARTNER_MAR_ADDR`) with their own statics. Two partners of the same character share that code, so each body's statics (.data/.bss) must be swapped in for its frame, as #166's design does for weapon overlays. Step 2 starts with a RAM map in `docs/research.md`.

2. **Mailbox: N partners.** `link.h`'s partner fields become `partners[3]` (presence, pad, sprites, prims, hits, snapshots in), each with its own 8 MB copies (weapons, familiar, status: 0x10000 each). Partner 0 is today's partner, and every module system still reads only it. `test_layout` checks it.
3. **Hosts: the roster and the mesh.** `transport.py` is per peer; `host.py` keeps one per partner, maps each to a mailbox slot, and forwards between guests who can't reach each other (criterion 2). Python-only, so it's tested with fake games (`test_connect` with three).
4. **Bodies: one per partner.** `partner.c`'s single body becomes an array (`Body`): swap regions per body, bank k + 1 for partner k, its own tint, and each partner's weapon swings and familiar from its own copies. Two partners on one character share its partner build, each with its own statics (D214). Tested with three games (`session_three.py`, `--full`): `partner_bodies_three_players`, `partner_bodies_two_richters`, `rules_enemy_hp_three_players`.
5. **Shared rooms, progression, bosses, respawn** (criteria 1 and 3): the authority streams to each guest, merges take every partner, bosses go for every player, and a fallen player revives at a living partner (D215). Enemy HP scales by the players in the session (D213), not only the room: a player across the castle can arrive at any moment. Tested with three games: `shared_rooms_three_players`, `gold_pooled_three_players`, `castle_flags_rejoin_three_players`, `boss_aggro_three_players`.
6. **Launcher:** a 4-player lobby, the map's colours, teleport choosing a partner, and couch 2×2 (criterion 4). Then the measurements and caps (criteria 5 and 6).

## Step 6 plan: the app (needs Tucker's approval, 2026-11-18)
Steps 1–5 make three and four games work together when linked (the tests link them directly). Step 6 lets players do it from the app. Two choices are hard to reverse:

**1. Castle saves for 3–4 players.** Today a castle file holds slot 1 (this machine's player) and slot 2 (whoever plays with them).
| Option | Idea | Verdict |
|---|---|---|
| **A. A slot per player number (recommended)** | Slots 1–4 by player number in the room; every joiner keeps a copy, as today. A returning player loads their own slot; a new one gets a copy of slot 1, as a new partner does now. Old castles read as two slots. | ✅ Everyone resumes as themselves; a format bump, read both ways |
| B. Two slots, extra players start fresh each time | Players 3 and 4 get slot 1's copy every session | ❌ Their level and gear don't carry over |
| C. Only the host's castle keeps everyone | Joiners keep nothing | ❌ A joiner can't host the castle later (M11 gives everyone a copy) |

**2. How players 3 and 4 join.**
| Option | Idea | Verdict |
|---|---|---|
| **A. Drop in (recommended)** | The host's room stays open while it plays; anyone with the code joins mid-game and arrives at the host, and anyone who dropped out rejoins the same way (completes #318's Rejoin). The pause menu lists who's in. | ✅ Matches how people play: someone joins late or reconnects |
| B. A lobby that waits | Everyone joins first; the host starts | ❌ Anyone who drops can't come back until the next session |

**3. Couch with 3–4 controllers** (2×2 panes): after online, as the goal says, once the measurements (criterion 5) show four emulators hold 60 fps on Tucker's PC.

Also for the release: the four-bank cores for Windows and Android (`bootstrap.sh swanstation_win swanstation_android`, `core_check`).
