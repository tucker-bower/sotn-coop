# M4 design: Shared rooms (the same enemies, fighting together)

**Status:** approved 2026-10-19 ("everything for shared rooms sounds good").
**Budget:** 25% of the month (the main risk). Target: 2026-11-04. Checkpoint after the spikes.
**Context:** D23 ("same room means the same enemies"), `research.md` → "Shared rooms", M1–M3.

## Goal
When both players are in the same room, they see and fight **the same enemies**:
- either player's attacks damage them, and an enemy killed by one is dead for both;
- enemies chase and hurt either player;
- regular enemies keep normal HP (D25).

When the players are apart, each game runs its own world, as today. Walking in and out of a shared room never duplicates or loses enemies.

## What the code says (2026-10-19)
- **Entity and primitive positions are camera-relative.** Every frame the engine shifts camera-locked entities, and the primitives they draw with, by the scroll delta (`RunMainEngine`, `src/dra/5087C.c`). Copying an enemy from one game to the other therefore means adding the camera difference.
- **The stage's per-frame logic is reached through `g_api.o`**, a table of function pointers in RAM (`Update`, `HitDetection`, `UpdateRoomPosition`, …). The module can swap those pointers at runtime, with no DRA change and no new hook.
- **The targeting helpers** (`GetSideToPlayer`, `GetDistanceToPlayerX/Y`, `GetPlayerCollisionWith`, about 880 call sites) are compiled into each of 52 stage and boss overlays. They can be patched **in RAM after each overlay loads**, using per-overlay address tables generated from the build maps. Disc files stay untouched (D34).
- **Enemies spawn from the room layout as the camera moves.** What exists depends on where a game's camera is. That's why two games with two cameras can't simply simulate the same room in lockstep.

## Part 1: whose world is the shared room?

| Option | Idea | Verdict |
|---|---|---|
| **A. Room authority with mirroring** | The first player in a room is its **authority**: that game runs the room's enemies as normal. The other game (the **guest**) stops running its own enemies: its `g_api.o.Update` is swapped for a stub. Each frame it receives a **snapshot** of the authority's room: stage entities (slots 64–255), the primitives they draw with, and the stage overlay's BSS. It copies these in, shifted to its own camera. It still runs its own player, and its own hit detection against the copies. | ✅ **Recommended.** Everything in the guest is the game's own code and data, so enemies look and behave exactly right. Hand-over is clean: the guest already holds the full room, so it just resumes running it. Each player keeps their own character code, so Richter and Maria (M7) still work. |
| B. Lockstep merge | Both games simulate both players and the same enemies, in lockstep | ❌ What exists and what moves depends on each game's camera, and the two cameras differ, so the games would drift apart. It also needs every character's code in every game (the old Richter relocation). |
| C. Per-enemy ownership | Each enemy is run by whichever game spawned it; the other game mirrors it; ownership passes between games | Later, maybe. It's the most general (big rooms with the players far apart), and the most complex. A is the special case where one game owns everything. |

### How A works, frame by frame
1. **Authority, after its update:** packs a snapshot (about 40 KB: 192 entities × 0xBC, plus the primitives they use, plus stage BSS) and sends it. On one PC that's a memory copy (couch, D36). Online it'll need delta compression (M7+).
2. **Guest, before its update:**
   - Writes the snapshot into its own entity slots and primitive buffer, adding `authorityScroll − guestScroll` to positions.
   - **Primitive indices are remapped** to free slots in the guest's buffer, so they never clash with the guest's own player and HUD primitives (link pointers are rewritten to match).
3. **Guest, hit detection:** runs as normal against the copies.
   - **Enemies hurt the guest natively:** their attack boxes are in the copy, so the game's own damage, knockback and invincibility frames apply to the guest's player.
   - **The guest's attacks:** the module wraps `g_api.o.HitDetection` and records what it did to each copied enemy (HP, hit flags, death flag, invincibility frames, stun, hit effect). It sends that as **HIT events**.
4. **Authority, start of its next frame:** writes those hit results into its own enemies before they update. Their own code then flinches, dies and drops loot, once, in the authority's world. The next snapshot carries the result back to the guest.
5. **Targeting:** in the authority's game, the patched helpers measure to the nearer of its own player and the guest's position (from presence, M1). Enemies built on the helpers chase and face whoever is closer. The roughly 135 places that read the player directly still target the authority's player only. They get fixed case by case, test route first, from a generated list.

### Becoming shared, and splitting up
- **Shared** means: same stage and room, both in normal play, and the cameras overlapping (within one screen of each other).
  - **Players far apart in a big room stay independent:** each game simulates its own part, as single-player does.
  - **When the cameras meet,** the guest adopts the authority's snapshot. Enemies near the guest may then jump to the authority's version, once (Option C fixes this later).
- **Hand-over:** when the authority leaves the room, dies, or freezes for a shared-room pause, the guest becomes authority. It restores its `Update` pointer and carries on from the last snapshot. The layout spawner's position is re-based on its own camera (spike S4).
- **Loot:** drops spawned in the authority's world are entities, so they're mirrored, and either player can pick them up. A pickup in the guest's world goes back to the authority like any hit, so the authority removes the drop, and M2 shares the item.

## Part 2: what's shared vs local in a shared room
- **Shared:** enemies, projectiles, loot and other drops, breakable candles and walls (they're stage entities too). Also room objects like elevators and switches.
- **Local:** each player's own character, weapons, spells, familiar and HUD.
- **Shared-room pause:** as M3. The authority freezes too when the guest pauses, and the guest holds its last snapshot.

## Spikes first (about 1.5 days, then a checkpoint with Tucker)
1. **S1 mirror fidelity:** in a few test-route rooms with enemies, copy A's room into B every frame, with primitive remapping, with both cameras equal. Then do a pixel diff of B's screen against A's. Count the enemy types that look wrong.
2. **S2 hit transplant:** B attacks a copied zombie. A's zombie takes the same damage, flinches and dies once, and the death shows in B.
3. **S3 targeting patch:** per-overlay helper addresses from the build maps, patched after load. A bat chooses B when B is closer.
4. **S4 hand-over:** A leaves; B carries on with the same enemies (continuous positions, nothing lost or duplicated), and new spawns appear around B's camera.
5. **Measure:** snapshot size and frame-time cost in both games (D40 applies).

If S1 or S4 show that A can't be made to look right, the fallback is Option C limited to enemies on screen. It's more work, and would mean re-planning M5/M6 dates.

## Acceptance criteria (two-game harness tests unless noted)
1. **Same enemies:** with both players in a test-route room with enemies, B's screen shows A's enemies at the same room positions (pixel and entity checks), and none of B's own.
2. **Both damage:**
   - B hits an enemy: it loses the same HP in A's world as a hit by A would take.
   - An enemy killed by B is gone in both worlds and drops loot once.
3. **Both get hurt:** an enemy attack that reaches B damages B (B's HP falls), and A is unaffected.
4. **Targeting:** a helper-based enemy (for example a bat or an Axe Knight) turns toward whichever player is closer.
5. **In and out:** A and B enter and leave in every order across the test route (entrance → Alchemy Lab → Marble Gallery → Outer Wall), including hand-over while enemies are mid-attack. There are no duplicated or lost enemies, and no crash.
6. **Normal HP:** regular enemies' HP is unchanged.
7. **Cost:** frame time with sharing on stays within budget (`no_effect_on_play` still passes with no partner). Snapshot size is reported.
8. **Soak:** 10 minutes, both players in shared rooms most of the time, random fighting: no crash, and shared state converges.
9. **Manual (Tucker, at M6):** a couch session fighting together feels right.

## Risks
- **Stage state outside the entity slots** (overlay statics, layout-spawner indexes, camera-dependent effects) can make the guest's copy or a hand-over wrong. Mitigation: mirror stage BSS, and the S4 spike.
- **Primitive remapping:** some entities may keep primitive indices outside `primIndex` (in `ext`). Mitigation: S1 counts the wrong-looking enemies, plus a per-type fix list.
- **The ~135 direct player reads:** some enemies will only chase the authority's player at first. Accepted for M4. They're listed and fixed on the test route first.
- **Bandwidth online:** 40 KB × 60/s is fine on one PC (couch first) and needs compression online (M7+).
- **Bosses** are their own overlays, with M5's own rules (2× HP, pull-in, stay-dead). M4 makes sure ordinary rooms work. M5 builds bosses on top.
