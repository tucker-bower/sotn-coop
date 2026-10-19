# Roadmap

**Final goal (D19):** two players explore the castle **independently**, each on their own screen, with **shared progression**. They meet up to fight the same enemies, beat bosses together, and watch cutscenes together. It should still be fun after tens of hours and on repeat playthroughs, including co-op speedruns.

**Architecture (D20):** each player runs their own copy of the game in an emulator. A **co-op link** connects them: an in-game module plus a host program per player. It shares progression, presence, teleports, and the state of any room both players are in. The details are in `research.md` → "Independent exploration".

**Month target (by 2026-11-18, Claude Pro):** a playable "explore together" build, M1–M6. This scope is much bigger than the old "P2 Lite" plan.
- **M4 (shared rooms) is the main risk.** The checkpoints are after M2 and after M4. At each one we decide on scope cuts, or a plan upgrade if needed.
- **Post-month:** Richter and Maria (mixed-character rules), full inverted-castle coverage, speedrun features, and the decision on which emulator we ship for (R1).

## Budget model
Pro usage limits are measured in rolling 5-hour windows (plus possible weekly caps), not published token counts. So the budget is a **share of the month's usage**, tracked by elapsed days and by how often limits are hit.

| # | Milestone | Budget (share of month) | Target date |
|---|---|---|---|
| M0 | Test harness + 8MB verification ✅ | 12% | 2026-10-22 (done 10-18) |
| M1 | Link + presence | 15% | 2026-10-23 |
| M2 | Shared progression (live) + joint save | 15% | 2026-10-28 |
| M3 | Teleport, respawn, pause rules | 8% | 2026-10-31 |
| M4 | Shared rooms: same enemies, fight together | 25% | 2026-11-08 |
| M5 | Bosses and cutscenes together | 12% | 2026-11-13 |
| M6 | Playable build + playtest | 10% | 2026-11-18 |
| — | Reserve | 3% | — |
| R1 | Product emulator decision (research, with Tucker) | outside the milestones | before M6 |
| M7+ | Richter/Maria, inverted castle, speedrun features | post-month | — |

**Dev platform until R1:** two SwanStation instances driven by our harness (each instance is its own process, since a libretro core can only be loaded once per process). PCSX-Redux is the cross-check. Code that talks to the emulator stays in one thin **emulator adapter** (read/write RAM, a per-frame callback, input), so the R1 choice only means replacing that adapter.

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

### M2: Shared progression (live) + joint save
- **Shared, live:** relics, castle flags (walls, doors, switches, item pickups, bosses), explored map, equipment (picking one up gives *each* player a copy), and max-HP/MP/Hearts upgrades. The partner's instance applies each change within a few frames.
- **Separate:** level, XP, gold, consumables, the equipped loadout, and current HP/MP.
- **Live room refresh:** a change that affects the room the partner is standing in shows immediately. For example, a wall breaks, a door opens, or a pickup disappears. The partner doesn't have to re-enter the room.
- **Joint save:** saving in either game saves both, plus a session file. Resuming restores both games and the shared state.
- Merges converge after random inputs, so a 30-minute soak with both players exploring ends with identical shared state in both games.

### M3: Teleport, respawn, pause rules
- **Teleport to partner** from a pause-menu entry, across stages and into the inverted castle. It lands at a safe position near the partner.
- **Death:** the player respawns at the partner's location with full HP instead of getting Game Over. If both players die, they reload the last joint save (D24).
- **Pause:** each player pauses and uses the menu independently. If both are in the same room, a pause by either one pauses both.
- Zero softlocks in a teleport fuzz test (random teleports between harness savestates).

### M4: Shared rooms (same enemies, fight together)
- When both players are in the same room, they see and fight **the same enemies**. Damage from either player counts, and enemies can target and damage either player.
- The method to pick in the M4 design: room authority (one game runs the enemies and the other mirrors them) vs a lockstep merge. The leading candidate is in `research.md`.
- Enemies keep normal HP.
- Players can enter and leave a room in any order without duplicated or lost enemies and without crashes, on the test route: entrance → Alchemy Lab → Marble Gallery → Outer Wall.

### M5: Bosses and cutscenes together
- When either player enters a boss room, the partner is **teleported in automatically**. Bosses have **2× HP** (regular enemies don't change).
- When either player triggers a cutscene, the partner is brought in, both see it, and both get credit (flags).
- **Death during a boss fight:** the player who died stays dead until the boss is killed, then respawns next to the survivor. If both die, they reload the last joint save (D24). Scripted boss fights cover each case with no softlocks.

### M6: Playable build + playtest
- A couch-co-op launcher: two instances, two pads, and both screens shown together.
- The bring-your-own-disc build script produces the patched image (D9).
- Manual (Tucker): a human playtest from the start through the first few bosses.
- Online play between two machines, if R1 has settled the emulator by then. Otherwise it moves to M7.
