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
| M4 | Shared rooms: same enemies, fight together ✅ | 25% | 2026-11-04 (done 10-19) |
| M4b | Playtest 1 fixes, autonomous playtesting ✅ | (from reserve) | 2026-10-19 (done 10-19) |
| M5 | Bosses and cutscenes together ✅ | 12% | 2026-11-13 (done 10-19) |
| M6 | Playable build + playtest ✅ | 10% | 2026-11-18 (done 10-19) |
| — | Reserve | 3% (M3b came out of the M2/M3 savings) | — |
| R1 | Product emulator: **decided**, our own launcher (D36) | — | — |
| M7 | Its own repository (`tucker-bower/sotn-coop`, D72/D73), online PC co-op (D74) | post-month | — |
| M8 | Playable Maria & Richter from the start + DXC alternate dialogue/voices (D75) | post-month | — |
| M9 | Android port of the launcher and session engine (D36, D75) | post-month | — |
| M10 | AYN Thor curated dual-screen (top = you, bottom = partner) + true widescreen FOV (D75) | post-month | — |
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

### M6: Playable build + playtest (design: `design/M6-playable-build.md`)
- **A Windows installer:** the launcher, the SwanStation core, OpenBIOS (no BIOS hunt) and a disc patcher that builds the co-op disc from the player's own image (D9). There's a first-run wizard, then one big Continue / New game button (the Slippi and BBLauncher model).
- **Nothing is ever deleted:**
  - every savestate the launcher makes (on events only, never on a timer) is kept, and the space it uses is always shown, with where to clean it up;
  - predefined debug starts are made on the player's PC;
  - F9 makes a full environment snapshot.
- **Built for what's next:** a headless session engine and a written link protocol, so online (M7) and Android reuse them.
- Manual (Tucker): install from scratch, then play from a new game through the first few bosses.
- Online play between two PCs comes next (M7+), then Android (with the disc patched on a PC).

### M7: Its own repository, then online PC co-op (design: `design/M7-repo-and-online.md`)
- **Its own repository (D72, D73):** the co-op mod moves out of the sotn-decomp fork into `tucker-bower/sotn-coop`, which builds against a pinned `sotn-decomp` commit as a dependency, not a fork. Git history for `mods/co-op/` comes along. Self-hosted CI builds and runs the full harness suite from a clean checkout.
- **Online PC co-op (D74):** each player runs one game on their own PC, connecting with zero-infrastructure connect codes (STUN + base32 endpoint/room code) and a direct-IP fallback. Shared-room snapshots are compressed and chunked below path MTU for smooth WAN play, joint saves and both-dead reloads sync over the link, and mismatched versions are refused with a clear message.

### M8: Maria and Richter playable from the start + DXC dialogue/voices (D75)
- **Playable characters from a fresh game:** either player can pick Alucard, Richter, or Maria right from the start of a new playthrough (including mixed pairs like Alucard + Maria or Richter + Maria), with cross-character puppet rendering in the 8MB area and clear shared-progression rules (D27).
- **Extracted from local DXC USA (`disks/sotn.pspus.iso`):** builds a `pspus` asset map so Maria's sprites, overlays, and SFX extract cleanly from the USA *Dracula X Chronicles* ISO (resolving D15 without needing the EU disc).
- **Alternate dialogue & voice acting option:** optional toggle in the patcher/launcher to use the *Dracula X Chronicles* (PSP) English script and voice acting preferred by some players.

### M9: Android port (D36, D75)
- **Native Android launcher & session engine:** runs the co-op disc on Android using the SwanStation Android arm64 core (`swanstation_libretro_android.so`) and the link protocol (`docs/link-protocol.md`), connecting over Wi-Fi/internet to another Android device or PC, with controller-first UI, event savestates, and F9 snapshots.

### M10: AYN Thor dual-screen & widescreen (D75)
- **Curated AYN Thor dual-screen mode:** on the AYN Thor clamshell handheld, the top 6.0" 16:9 AMOLED screen renders your game while the bottom 3.92" screen displays your partner's screen live.
- **True widescreen on the top screen:** expanded horizontal FOV (not stretched 4:3) on the 16:9 top display, widening the draw/clip viewport, room scroll bounds, and entity layout spawn window so rooms and enemies render naturally across the 16:9 frame.

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

