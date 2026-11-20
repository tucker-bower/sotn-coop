# M21 design: co-op lobbies of 4 or 8

## Goal
Tucker (2026-11-19): more players co-operating is still cool. A framework where the host picks a lobby of 2, 4 or 8, every player in their own game, everything M17 does for four (drop-in, shared progress, shared rooms, saves that follow players) working for eight. Battle royale (M22) is separate: it uses puppets, not partner bodies.

## What we know (measured or read, 2026-11-19)
| Resource | Per partner | Today | Where it's spent |
|---|---|---|---|
| **Mailbox** | 2.2 KB (`CoopPartnerIn`) | 3 partner slots | Presence, buttons, events, sprites |
| **RAM copies** | about 140 KB | 3 partners; 130 KB free in the 8 MB | Two weapon copies (2 x 29 KB), a familiar copy (65 KB), the body copy (15 KB). The PS1's 8 MB is otherwise full: the game, Richter's and Maria's builds (2 MB), the mailbox |
| **VRAM banks** | one per *other character*, not per partner | 4 banks (spare address bits: no more) | A body playing your character draws from your own bank (`partner.c`: `banked` only for another character or a partner build) |
| **CPU** | 45-85 of a frame's 263 scanlines | 200% clock | Bodies exist only for partners *in your room*. The PC runs 800% in about 2 ms a frame |
| **Network** | presence about 4 KB/s a link; room snapshots 10-16 KB/s per guest | full mesh | Snapshots go only from a room's authority to the guests in it |

So at eight, the walls are RAM (7 partners need about 1 MB of copies), VRAM banks (seven partners could be more than three other characters), and CPU when everyone crowds one room. The network is fine: 7 links of presence is about 30 KB/s, and a room's authority with 7 guests sends about 110 KB/s.

## Options
| Option | Idea | Verdict |
|---|---|---|
| **A. Eight in full (recommended)** | Every partner in your room is a full body, as today: their attacks, familiar and weapons on your screen | ✅ Co-op as it plays now, for eight. Needs the four changes below |
| B. Nearest three in full, the rest as puppets | M22's puppets for partners four to seven in your room | ⚠️ Fewer changes, but some partners' attacks aren't seen in co-op. The fallback if A's VRAM sharing fails |
| C. Stay at four | | ❌ Not the goal |

## Option A: the four changes
1. **RAM: our core's 32 MB.** SwanStation already has an 8 MB option; our patch makes it 32 MB (the RAM mask, so DMA reaches it too). Each partner's copies get room of their own above 8 MB: 7 x 140 KB. Savestates grow from 12 MB to about 36 MB. Retail code never addresses past 8 MB, so nothing else changes. *Alternative if that's too heavy:* partners on one familiar share its copy, which saves 65 KB each.
2. **VRAM: banks per character, shared.** Bank 0 is your character's. Banks 1-3 go to up to three other characters *in your room*, assigned as partners arrive and freed as they leave. Two partners on one character share their bank's sheets. What differs between them gets a sub-slot each: weapon sheets, familiar strips, Maria's guardian and HUD uploads. *Research first:* how big those are, and whether four of them fit beside the sheets (a bank is 1 MB; a character's sheets take about a quarter). A fourth other character in your room at once is drawn as a puppet (M22) until a bank frees.
3. **The mailbox: seven slots.** `more[]` grows to six (15 KB more). A partner away from your room keeps only their roster entry; their slot fills when they arrive.
4. **CPU: the clock follows the room.** 200% with up to 3 bodies here, 400% with more (a core option, set by the launcher when the lobby is over four).

## Unchanged from M17, scaled
- Links: the room's mesh, with player 0 forwarding for pairs that can't reach each other. Interest: presence at full rate only to players in your stage, a roster twice a second to all.
- Rules: shared rooms with one authority and any guests; enemy HP on D213's curve, carried on to eight (1, 2, 2.75, 3.5, 4.1, 4.6, 5.1, 5.5x), counted among players in the room. Bosses take turns among those in the room.
- Saves: per-player slots by id (D219), up to eight.
- UI: the lobby's list, the pause menu's who's in, a map cursor and an HP bar per partner (seven tints: blue, red, green, orange, purple, cyan, white).

## Acceptance criteria
1. Eight headless games: seated, progress converges, everyone in one room sees seven bodies, each animating with its player (`m21_room_of_8`).
2. Eight players on four characters (two each): three other characters drawn from banks 1-3, same-character partners sharing a bank, each in their own weapon and familiar (`m21_shared_banks`).
3. A fourth other character arriving in your room is drawn as a puppet, and as a full body once a bank frees (`m21_bank_overflow`).
4. 32 MB core: retail and co-op savestates load; `core_check` matches on Linux, Windows and Android.
5. A room of 8 at 400% holds 60 fps on Tucker's PC (missed frames under 2% in the entrance hall, `mixed_soak` with eight).
6. Eight launchers online on the playtest network: drop-in, a joint save, everyone gets their own slot back (`ui_online_eight_players`).
7. Two to four players unchanged (the gate).

## Risks
- **Bank sub-slots may not fit** four players' weapons and familiars beside a character's sheets. If not, option B for the overflow.
- **Phones:** 400% and seven bodies may be too slow on Android; its lobby cap could stay at four.
- **36 MB savestates:** F9 reports and save history get bigger; their compression needs checking.
- **Testing eight** online needs eight launchers: about 3 GB of RAM, real time.

## Steps
1. Research: bank sub-slots (sizes, layout), and a 32 MB core spike (`core_check`, savestate size).
2. Core 32 MB and the partner copies moved above 8 MB.
3. Seven mailbox slots and bodies for up to seven.
4. Banks per character, shared; puppet overflow (with M22's puppets).
5. Rules and UI for eight; the lobby-size setting.
6. Eight launchers online; measurements; Tucker's PC.

## Budget
About 3-4 weeks after M17 merges.
