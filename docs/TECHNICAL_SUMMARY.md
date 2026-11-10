# SOTN Co-op: technical summary

This is for anyone who wants to understand how the mod works, or build on it. Players want the [README](../README.md). The details behind each choice are in [`DECISION_LOG.md`](DECISION_LOG.md) (referred to here as Dnn), and each milestone's design is in [`design/`](design/).

## The idea in one paragraph
*Symphony of the Night* can't hold two players in two places. It keeps exactly one stage resident: the stage code always loads at `0x80180000`, VRAM holds one stage's tiles, SPU RAM holds one stage's sounds, and the camera, tilemap and spawner assume one world. So instead of putting a second player into one game, **each player runs their own copy of the game**, and the copies are kept in sync (D19, D20). Every game's engine stays stock; the work is all in the syncing. A small module inside each game reports what happens and applies what the partner did. A host program next to each game carries that between the two, over a local socket on the couch or UDP online.

```
 game A (emulator)                                              game B (emulator)
   co-op module ⇄ mailbox (8 MB RAM)                               mailbox ⇄ co-op module
                      ⇅                                               ⇅
                   host A  ⇄─────── UDP (localhost or internet) ───⇄  host B
                      ⇅                                               ⇅
                 launcher A (window, pads, saves)            launcher B (or the same one, on the couch)
```

## Building on sotn-decomp
The mod is built on [sotn-decomp](https://github.com/Xeeynamo/sotn-decomp), the matching decompilation of the game: C that compiles back into the exact retail binaries. That gives us named symbols, struct layouts and the ability to compile new code against the game's own headers.
- **The co-op module** (`module/`, about 30 C files) is compiled with the decomp's MIPS toolchain and lives in the **8 MB expansion RAM** (D7). The retail game uses 2 MB, and most emulators offer 8 MB. The module's code, the mailbox and the partner's sprite data all live above 2 MB.
- **Loading:** a 184-byte boot stub inside the last sector of `DRA.BIN` (the game's main engine) loads `COOP.BIN`, a new file placed after every retail file on the disc (D32).
- **Hooks are size-neutral (D33).** DRA's code ends exactly where a fixed-address data block starts, so not one instruction can be added. Each hook instead *retargets an existing call* to a module function with the same signature, which does its work and calls the original (for example `DebugUpdate` → `CoopUpdate`, `RenderEntities` → `CoopRenderEntities`). `build_disc.sh` fails the build if DRA's image changes size.
- **No retail file moves on the disc (D34).** Making `DRA.BIN` one sector bigger shifted every later file, and the intro FMV, read from a fixed sector, hung at boot. `check_disc_layout.py` enforces it.
- **Patched code is flushed (D17).** SwanStation notices self-modifying code by itself; PCSX-Redux's dynarec and real hardware don't. The module calls `FlushCache()` after every code patch.

## The two emulator cores
Every player's game runs in **SwanStation**, the libretro core forked from DuckStation before DuckStation's licence change, driven by our own frontend (D36). There's no RetroArch: the link has to read and write RAM exactly between frames, and no stock emulator runs two games on two pads in one window.
- **Couch co-op runs two cores.** A libretro core can only be loaded once per process, so each game is a **worker process** with its own core, its own host and its own UDP socket on localhost (`harness/session.py`). The launcher (`launcher/gameview.py`, pygame) drives both workers frame by frame over pipes, gets their frames through shared memory, draws them side by side (or stacked, or in two windows), and mixes their audio, with one game playing the music (D55). Online, each player's launcher runs one worker. Android can't start processes, so there the one game runs in the app's own process (design/M9).
- **Our own core build (D125).** Windows, Linux and Android all ship SwanStation built from one pinned commit plus a small patch, so savestates move between platforms and `harness/core_check.py` can prove the builds give identical RAM and VRAM. The patch adds a **second VRAM bank**: the partner's body needs graphics of its own character, and the PS1's 1 MB of VRAM is full. Spare address bits that retail code never sets select it: bit 9 of y for uploads, bit 14 of the texpage for texture reads, bit 15 of the CLUT for palettes. It works in the software renderer only. Savestates are 12 MB with both banks.
- **Determinism is a rule.** Each game must be deterministic on its own: no uninitialized reads, and nothing in the game that depends on timing. The harness's reproducibility depends on it (see Testing). Anything timing-dependent, like the network jitter buffer, lives in the host, never in the game.
- **BIOS:** the releases ship **OpenBIOS** (from PCSX-Redux), built with fast boot, so nobody has to hunt for a BIOS dump (D68, D117).
- **Emulator calls go through one thin adapter** (`link/adapter.py`): RAM read and write, a per-frame callback, and pad input. Porting to another emulator means rewriting the adapter, not the link.

## The mailbox and the link
- **The mailbox** is `g_CoopLink`, a struct at a fixed address in the 8 MB area (its address is in the module's linker map). It holds each player's **presence** (stage, room, position, animation, flags), event rings in both directions, room snapshots, commands and save slots. The game never touches the network, and the host never touches game state outside the mailbox. The layout is written twice, in `module/link.h` and `link/mailbox.py`: the module's build asserts every offset (`module/coop.c`), and `link/test_layout.py` checks the Python against the header.
- **The host** (`link/host.py`) runs once per frame while the emulator is paused: it reads the mailbox, sends datagrams, receives the partner's, and writes them in.
- **The wire protocol** is documented well enough to write another host without reading our Python: [`link-protocol.md`](link-protocol.md). `harness/spec_test.py` checks the document against a real game, playing the partner over a raw UDP socket using only what the document says. In outline:
  - `PRES`: presence, every frame, best effort.
  - `EVTS` / `ACK`: game events (a relic found, a flag set, an item picked up, a boss hit), sent reliably and in order.
  - `SNPC`: a shared-room snapshot, compressed against the last one the partner acknowledged and split into chunks under 1200 bytes, since many routers drop fragmented UDP (D74, D77).
  - `HELO`: the handshake (versions, the co-op disc's CRC, the room token, clock samples for the round trip).
  - Nothing from the network is trusted: a malformed or oversized datagram is dropped, never an error in the host's frame (`link/test_malformed.py`).

### What's shared, and how
- **Progression is merged as events, not by diffing state.** A diff can't tell "the partner found a second potion" from "I used one". Castle flags (`g_CastleFlags`) and the explored map are merged as a union, since they're set-only and so converge in any order. Finds (relics, items, max-HP/MP/heart ups) are add-on-find events, so each player gets their own copy (D37). A placed item or vessel travels as the castle flag it sets, and the other game gives its player what that pickup holds (`module/collectibles.c`), so a reconnect catches a player up on finds they made and didn't save (D172). An item an enemy drops is one item, for whoever takes it (D171). Gold is pooled (D38). Level, XP, hearts and loadout stay each player's own.
- **Live refresh:** entities read their flag when they spawn, so a flag set by the partner wouldn't show in a room you're already in. `module/flag_gated.c` maps each flag-gated entity type to a refresh: despawn it, put it in its "done" state, or rerun its init ([`flag-gated-entities.md`](flag-gated-entities.md)).
- **Shared rooms (D23, D50).** When both players are in the same room, the first one in becomes the room's **authority** and runs the enemies. The other game (the **guest**) stops running its own enemies and mirrors the authority's entity slots 64–255 every frame, along with the primitives and VRAM uploads they draw with (D53, D63–D65). This works because both games run the same binary and the same stage overlay, so raw entity memory, function pointers included, is valid in both. Hits from the guest, and pickups it touches, go back to the authority as events (D57, D66). Scenery is run by each game itself (D56).
- **Enemy targeting.** Most enemy AI reads the player through a handful of shared helpers in `st_common.h` (`GetSideToPlayer` alone has about 420 call sites). Pointing those at the nearer player gave most enemies two-player awareness in one change. Bosses also switch aggro between players every few seconds (D47, D62).
- **Enemy health:** every enemy has more health with a partner, 200% by default (D160).
- **Bosses and scenes.** A boss pulls the partner in and is fought in one shared world, however far apart the two cameras are (D25, D131). Cutscenes pull the partner in and hold until both players have seen them (D26, D102). Killing Richter or Dracula ends the game for both players (D130, D134).
- **The partner's body (M13).** In your game, the partner is a real second player: each frame the module swaps the partner's player state into the player slots, runs the character's own player code with the partner's buttons from the link, and swaps back. The partner's attacks hit with their real hitboxes, and their graphics come from the second VRAM bank (D124, D128). The partner's body costs about 45 to 60 of a frame's 263 scanlines (D129).
- **Characters.** Richter and Maria are playable (M8). Our Richter is Alucard's engine plus Richter's code, run from the expansion RAM (D89). Maria's code is compiled from the PSP *Dracula X Chronicles* overlay via the decomp's Maria port and applied as **patches of code only**, so no game art ships (`characters/maria-dx/make_patches.py`). These two are **Co-op Richter and Co-op Maria**: Alucard's gear, relic moves and levels, each a castle rule. **Ultimate Maria** is SOTN Ultimate's PSP Maria as that mod plays her: the same decompiled Maria built without our changes, with Ultimate's glue (`characters/maria-ultimate/mar2.c`, CHAR_ULT_MARIA). Her two-icon HUD, which Ultimate draws from its own DRA, is drawn by her overlay through a hook the module calls before the frame's primitives. The launcher's `maria.blob` holds both Marias' blobs, one after another (`CHAR_BLOB_NEXT`), and the module's co-op-only features check `CHAR_COOP` (docs/design/character-mods.md). **Saturn Maria** (`CHAR_SAT_MARIA`, `characters/maria-saturn`) is SOTN Ultimate's: upstream's `src/ric` plus Ultimate's changes, built with `MOD_MARIA_SAT`. Her art is generated from the player's Saturn disc by `launcher/saturn_maria.py`, a Python port of Ultimate's converter, into the arrays her shipped build has zeroed. The blobs (all three Marias) live at `0x80300000`-`0x80500000`. Her partner build runs at `0x80200000`, below the module, and swaps a longer header (her 0x568-byte sprite table), taken from her build at every swap-in. The module stands in for Ultimate's DRA changes: her save-room walk snap, her Holy Beasts halt, her own Saturn HUD (drawn by her overlay through a hook) and her sounds' priorities. Her two sound banks are synthesized from the Saturn disc by `launcher/saturn_maria_sounds.py` and carried in her blob as vab 1 and vab 2. **Ultimate Richter** (`CHAR_ULT_RICHTER`) is retail RIC.BIN with the Saturn's coat sheet, made by `launcher/saturn_richter.py`; his blob is RIC.BIN's first 96 KB, copied over the retail load, and the module uploads his coat's palettes and arm (`CharacterRicCoat`). As a partner he runs our Richter's partner build with his coat's sprite table and colours.
- **PvP** (off by default) uses the attacker's real hitboxes, sent over the link, and the victim's own game decides each hit (D132).

- **Castle rules (D162).** Every co-op change to the game is a setting of the castle, defaulting to how it plays now: `launcher/rules.py` lists them, `castle.json` keeps them, HELO gives the joiner the host's, and the host writes them into the mailbox every frame. Each rule is a bit or a percentage the module checks where the change happens; all zero is the default. Hanging onto the bat (`module/carry.c`, D167) is the one rule that's off by default.

### Saves
A **joint save** (`link/jointsave.py`) holds both games' memory cards in one file, so either partner can continue any castle (D31, D97). Saving uses the game's own save rooms, and resuming uses the game's own Load menu (D46). The launcher keeps savestates at big moments and never deletes or overwrites one (D69).

## Online
- **Room codes:** both players post their candidate addresses to a topic on the room's [ntfy.sh](https://ntfy.sh) relay, which needs no account and no server of ours, and read the other's (D78). The code carries a token, so only the right partner is accepted (D100).
- **NAT traversal:** STUN from the game's own socket, UDP hole punching to every candidate, UPnP-IGD and NAT-PMP port mapping, and a LAN broadcast so two games in one house find each other without the internet (D96). This is the way Slippi connects: no relays (D113, D123). When nothing works, the lobby says which step failed and what to try.
- **Jitter buffer:** `link/playout.py` plays the partner's presences and snapshots back at an even pace with an adaptive delay of at most 0.1 s (D170), interpolating across a lost presence, so the partner and the shared enemies don't stutter. `netplay_partner_lag` measures how far behind each game shows the other.
- **Testing the network:** `link/netsim.py` and `link/natsim.py` simulate latency, loss, reordering and router types in tests.

## Distribution: no game data, ever
Players bring their own disc (USA, SLUS-00067). The release ships a **BPS patch** of only our changes (`patcher/`), which the launcher applies to the player's image (D9, D71). The patch must never carry retail data: `patcher/test_patcher.py` checks every stored 64-byte run against every retail sector, and checks that no sector checksums are stored (D90). The test castles shipped in the app are save files with the memory card's icon header blanked: progress only (D136).

## The randomizer
Co-op runs on a disc randomized with [the randomizer](https://github.com/sotnrando/sotnrando), the first supported mod (D174, `design/M20-randomizer.md`). The randomizer changes bytes inside retail files and moves nothing, so its changes and co-op's land in different places. The launcher makes the randomized co-op disc on the player's machine, as a three-way merge of their retail disc, their randomized disc (or a seed's `.ppf`) and the co-op disc (`patcher/layer.py`, `randomizer.py`). Two things need more than a merge. Seven presets hook the one instruction co-op also redirects, and their trampoline gets co-op's version instead (`layer.relocate`). The table that turns a placed find's castle flag into an item is remade from the disc's own stages (D176). HELO carries the seed, so partners must play the same one (D175). `harness/mods.py` builds every preset at a pinned randomizer commit. The `mod_*` and `rando_finds_*` tests play four of them (casual, safe, boss-rush, and lycanthrope-spr26te, a start-room preset), and `mods.py --test` plays each of the others in turn, keeping one disc at a time. The tests assume nothing about retail's NO3 rooms: start-room presets replace the entrance's rooms 16 and 24 with a teleport to the seed's start room (`session_mods.replaced_rooms`).

## Testing
Everything that "works" has a test that proves it. There are about 300 tests, most of them running real games.
- **The harness** (`harness/`) drives SwanStation headless and frame-stepped from Python through [libretro.py](https://github.com/JesseTG/libretro.py), at about 25–30× real time per game. A test starts from a savestate, drives inputs (scripted, random or bot), and asserts on RAM by symbol name (`read("g_Status", ...)`). It writes a report, a clip and a log.
- **Two-game session tests** (`@session_scenario`) run two games plus their hosts. The driver steps them alternately, one frame each, on a simulated clock. For example: "A picks up a relic, and B has it within N frames", or "both fight the boss, and it dies once in both games, with the same flags after". Because each game is deterministic and the clock is simulated, these tests are reproducible even on a machine loaded with other tests.
- **Fixtures:** savestates outside every boss and scene, made by script from the built disc (`scripts/rebuild_fixtures.sh`), since savestates contain the module's code.
- **One runner** (`harness/run.py`, D138). Each test runs in its own process, many side by side, longest first. Network tests share one lane, and the few that time the host in real time run after the rest. It also runs the launcher's checks, its UI flows (`launcher/uxdriver.py` drives the real app headless, two launchers for online) and the patcher's round trip. How to run it is in [`AGENTS.md`](../AGENTS.md).
- **Cross-checks:** PCSX-Redux runs the module headless through Lua (`scripts/redux_check.sh`). `lockstep.py` replays two games on the same inputs and compares RAM hashes, as a determinism check.
- **Bots and playtests:** `harness/playtest.py` plays both games with bots for minutes at a time and flags stuck games, frozen screens, dropped events and mismatched worlds. Humans playtest each release.

## Repository map
| Path | What |
|---|---|
| `module/` | The in-game co-op module (C, MIPS): link, progress, shared rooms, bosses, the partner's body, characters, PvP |
| `characters/richter-ps1/` | PS1 Richter: the game's own Richter built with our changes, run from the expansion RAM |
| `characters/maria-dx/` | Co-op Maria: Dracula X Chronicles Maria for PS1, her PSP code built against the decomp, shipped as code-only patches |
| `characters/maria-ultimate/` | Ultimate Maria: SOTN Ultimate's PSP Maria glue on the same code, shipped the same way |
| `link/` | The host: mailbox, protocol, transport, joint save, connection, jitter buffer, network simulation |
| `launcher/` | The app: pygame frontend, two cores, lobby, castles, boss rush, settings |
| `harness/` | The headless test harness, the scenarios, the runner |
| `patcher/` | The BPS patcher that builds the co-op disc from the player's own |
| `android/` | The Android build (python-for-android) |
| `scripts/` | Bootstrap, doctor, disc build, fixtures, release |
| `docs/` | Roadmap, decisions, designs, the link protocol, research notes |

## How it's made
The project is developed by an AI coding agent (Claude Code), working from short design proposals that the owner approves. It works in milestones, each with a design doc, testable acceptance criteria, a PR with test evidence, and a playtest build. The working rules are in [`AGENTS.md`](../AGENTS.md).

## Building
See [`DEVELOPER_GUIDE.md`](../DEVELOPER_GUIDE.md): `scripts/bootstrap.sh` sets up a Linux (or WSL2) machine with the decomp's toolchain and the core, `scripts/doctor.py` checks it, `scripts/build_disc.sh` builds the co-op disc from your own disc image, and `scripts/release.py` builds the installers. Everything is AGPL-3.0, like sotn-decomp.
