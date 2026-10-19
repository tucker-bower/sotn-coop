# Roadmap

**Final goal (D19):** two players explore the castle **independently**, each on their own screen, with **shared progression**. They meet up to fight the same enemies, beat bosses together, and watch cutscenes together. It should still be fun after tens of hours and on repeat playthroughs, including co-op speedruns.

**Architecture (D20):** each player runs their own copy of the game in an emulator. A **co-op link** connects them: an in-game module plus a host program per player. It shares progression, presence, teleports, and the state of any room both players are in. The details are in `research.md` → "Independent exploration".

**Month target (by 2026-11-18, Claude Pro):** a playable "explore together" build, M1–M6. This scope is much bigger than the old "P2 Lite" plan.
- **M4 (shared rooms) is the main risk.** The checkpoints are after M2 and after M4. At each one we decide on scope cuts, or a plan upgrade if needed.
- **Post-month:** Richter and Maria (mixed-character rules), full inverted-castle coverage, speedrun features. Then online PC co-op and the Android port of the launcher (D36).

## Budget model
Pro usage limits are measured in rolling 5-hour windows (plus possible weekly caps), not published token counts. So the budget is a **share of the month's usage**, tracked by elapsed days and by how often limits are hit.

| # | Milestone | Budget (share of month) | Target date |
|---|---|---|---|
| M0 | Test harness + 8MB verification ✅ | 12% | 2026-10-22 (done 10-18) |
| M1 | Link + presence ✅ | 15% | 2026-10-23 (done 10-18) |
| M2 | Shared progression (live) ✅ | 12% | 2026-10-26 (done 10-19) |
| M3 | Teleport, respawn, pause rules, joint save ✅ | 11% | 2026-10-30 (done 10-19) |
| M3b | The game's own save rooms, end to end (resume from the Load menu) ✅ | 4% | 2026-10-21 (done 10-19) |
| M4 | Shared rooms: same enemies, fight together | 25% | 2026-11-04 |
| M5 | Bosses and cutscenes together | 12% | 2026-11-13 |
| M6 | Playable build + playtest | 10% | 2026-11-18 |
| — | Reserve | 3% (M3b came out of the M2/M3 savings) | — |
| R1 | Product emulator: **decided**, our own launcher (D36) | — | — |
| M7+ | Richter/Maria, inverted castle, speedrun features, online PC co-op, Android | post-month | — |
| Last | **3–4 players** (D48) | post-month | — |

**Platform (D36):** our own launcher around the SwanStation libretro core, which the harness already drives: two processes, since a libretro core can only be loaded once per process. PCSX-Redux stays as a cross-check. Code that talks to the emulator stays in the thin **emulator adapter**.

## Acceptance criteria (draft, finalized in each milestone's design doc)
Every criterion is a **multi-instance harness test**, unless it's marked manual. The harness runs two instances plus the host, with scripted inputs on both and assertions across instances.

### M0: Test harness + 8MB verification ✅
Done. Results are in `design/M0-harness.md`.

### M1: Link + presence
- **Loader:** the co-op module loads as an extra DRA section (option B from the withdrawn M1 design, D29). It's resident from boot on a new game, with no familiar trick.
- **Mailbox:** an in-RAM message buffer in the 8MB area, in each direction, read and written by the host every frame. The emulator adapter is the only emulator-specific code.
- **Presence:** each instance knows its partner's stage, room, position, facing, pose and character. When both are in the same room, the partner appears as a tinted **puppet** that animates correctly, in both instances.
- **Map:** the partner's position shows on the map screen.
- **Latency:** with both instances on one machine, the delay from a partner's movement to the puppet updating is ≤ 2 frames.
- With `COOP` off, the matching build is still 115/115.

### M2: Shared progression (live)
Full criteria: `design/M2-shared-progression.md`.
- **Shared, live:** relics, castle flags (walls, doors, switches, item pickups, bosses), explored map, equipment (picking one up gives *each* player a copy), and max-HP/MP/Hearts upgrades. The partner's instance applies each change within a few frames.
- **Separate:** level, XP, gold, consumables, the equipped loadout, and current HP/MP.
- **Live room refresh:** a change that affects the room the partner is standing in shows immediately. For example, a wall breaks, a door opens, or a pickup disappears. The partner doesn't have to re-enter the room.
- Merges converge after random inputs, so a 30-minute soak with both players exploring ends with identical shared state in both games.

### M3: Teleport, respawn, pause rules, joint save
Full criteria: `design/M3-teleport-respawn-save.md`.
- **Teleport to partner** with ✕ on the map screen, across stages and into the inverted castle. It lands at a safe position near the partner.
- **Death:** the player respawns at the partner's location with full HP instead of getting Game Over. If both players die, they reload the last joint save (D24).
- **Pause:** each player pauses and uses the menu independently. If both are in the same room, a pause by either one pauses both.
- Zero softlocks in a teleport fuzz test (random teleports between harness savestates).
- **Joint save:** saving in either game saves both (`session.coop`). Resuming restores both games and the shared state. Moved here from M2: resuming uses the same "put a player in a room" path as teleport.

### M4: Shared rooms (same enemies, fight together)
- When both players are in the same room, they see and fight **the same enemies**. Damage from either player counts, and enemies can target and damage either player.
- The method to pick in the M4 design: room authority (one game runs the enemies and the other mirrors them) vs a lockstep merge. The leading candidate is in `research.md`.
- Enemies keep normal HP.
- Players can enter and leave a room in any order without duplicated or lost enemies and without crashes, on the test route: entrance → Alchemy Lab → Marble Gallery → Outer Wall.

### M5: Bosses and cutscenes together
- When either player enters a boss room, the partner is **teleported in automatically**. Bosses have **2× HP** (regular enemies don't change, D25).
- **Boss aggro switches between players** (D47): after each boss attack there's a 50% chance it targets the other player next. That's a starting value, to tune by playtest. It's built on M4's targeting patch, plus per-boss handling of the bosses' own direct player reads.
- When either player triggers a cutscene, the partner is brought in, both see it, and both get credit (flags).
- **Death during a boss fight:** the player who died stays dead until the boss is killed, then respawns next to the survivor. If both die, they reload the last joint save (D24). Scripted boss fights cover each case with no softlocks.

### M6: Playable build + playtest
- **The couch co-op launcher (D36):** two games, two pads, both screens in one window, audio, and joint saves.
- The bring-your-own-disc build script produces the patched image (D9).
- Manual (Tucker): a human playtest from the start through the first few bosses.
- Online play between two PCs comes after couch co-op works (M7+), then Android.

### Last: 3–4 players (D48)
Three or four players, each in their own game:
- **Presence and the map** show every partner.
- **Teleport** offers a choice of which partner to go to.
- **Shared progression** merges across all games, using the same events and union rules.
- **Shared rooms** have one authority and up to three guests.
- **Respawn** is at the nearest living partner.
- **Bosses** scale their HP and aggro to the player count.
- **The launcher** splits the screen 3 or 4 ways.

The link was built per-partner, so this mostly means turning "the partner" into "the partners".

