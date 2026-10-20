# M7 design: Standalone repository (`sotn-coop`) + Online PC Co-op

**Status:** built and verified 2026-10-19 (`coop-m7-repo-online`, pushed to `tucker-bower/sotn-coop`).
**Context:** D70 (architecture ready for online), D72 (`mods/co-op/` moves to its own repo), D73 (`tucker-bower/sotn-coop`, self-hosted CI), D74 (zero-infra connect codes, compressed MTU-safe snapshots).

## Progress & Evidence
| # | Criterion | Status & Evidence |
|---|---|---|
| 1 | Standalone repository (`tucker-bower/sotn-coop`) with full commit history and pinned `sotn-decomp` dependency | **Done:** `git subtree split --prefix=mods/co-op` preserved all 48 commits, pushed to `https://github.com/tucker-bower/sotn-coop`. `patches/sotn-decomp.patch` holds the 5-file upstream hook diff against `Xeeynamo/sotn-decomp @ d12b397f36`. Clean clone in `/home/tucker/sotn-coop` passes `doctor.py`, `make -C module`, `test_patcher.py`, and `harness/run.py`. |
| 2 | Self-hosted CI (`.github/workflows/ci.yml`) | **Done:** `.github/workflows/ci.yml` verifies zero tracked game data, links the runner environment cache, and runs `doctor.py`, `build_disc.sh`, `test_patcher.py`, and `harness/run.py`. |
| 3 | MTU-safe compressed snapshots (`online_mtu_and_loss`) | **Done:** `TAG_SNPC` (`zlib` level-1 compression + `<= 1150`-byte chunks). Passes `online_mtu_and_loss` (5.4s): shared room + guest enemy kill under 1200-byte MTU cap, 20 ms RTT latency, and 3% random packet loss with `mtu_drops == 0` and full convergence. |
| 4 | Connect codes & direct-IP (`online_connect_codes`) | **Done:** 10-char base32 endpoint codes (with 2-bit CRC), 6-char room codes (`link/rendezvous.py`: LAN UDP broadcast + `ntfy.sh` relay + RFC 5389 STUN), and `ip:port` direct fallback. Passes `online_connect_codes` (1.4s, 19 assertions). |
| 5 | Version mismatch refusal (`online_version_mismatch`) | **Done:** `Host` + launcher check `link` version and disc `patch` CRC32, refuse mismatched partners with a clear message, relay zero packets while refused, and lift refusal on matching `HELO`. Passes `online_version_mismatch` (1.6s, 7 assertions). |
| 6 | Online joint save, Continue, and both-dead reload (`online_joint_save`) | **Done:** `JointSave` relays `save_req`, `save_done`, `load_save`, and `game_over` over `ReliableMessages` (`TAG_CTRL`/`TAG_CACK`). Passes `online_joint_save` (5.2s, 6 assertions). |
| 7 | Full regression suite + Windows installer (`SOTN-Coop-setup-0.7.0.exe`) | **Done:** all 61 harness scenarios (57 existing + 4 M7 online) and `launcher/smoke.py` (`check_online`) pass. |

## Goal
1. **Standalone repository (`tucker-bower/sotn-coop`):** move `mods/co-op/` into its own repository with its full commit history preserved, building against a pinned `sotn-decomp` commit as a dependency rather than a fork, with CI that builds the module and tests from a clean checkout (never distributing or storing copyrighted disc images in git or releases).
2. **Online PC co-op:** two players on separate PCs play together over the internet (one game instance per PC, full window, local music unmuted), connecting via zero-infrastructure connect codes or a direct-IP fallback, with compressed MTU-safe shared-room snapshots, synchronized joint saves, and a clear UI refusal when versions don't match.

---

## Part 1: Standalone repository (`tucker-bower/sotn-coop`)

### How the standalone repo builds against `sotn-decomp`
Today our diff outside `mods/co-op/` is **5 files (46 lines total)**:
- `src/dra/42398.c`, `src/dra/5087C.c`, `src/dra/62DEC.c`: the 5 `#ifdef COOP` size-neutral hooks (`CoopBoot`, `CoopUpdate`, `CoopRenderEntities`, `CoopDrawMapCursor`, `CoopStoreSaveData`).
- `tools/builds/gen.py`, `tools/sotn-assets/build.go`: passes `-DCOOP` and `-T dra_hooks.ld` when `COOP=1`.

| Option | Idea | Verdict |
|---|---|---|
| **A. Pinned `sotn-decomp` checkout in `.env/src/sotn-decomp` + tracked `patches/sotn-decomp.patch`** | `bootstrap.sh` fetches the pinned upstream `sotn-decomp` commit into `.env/src/sotn-decomp` (just like it already fetches pinned `swanstation` and `pcsx-redux` commits into `.env/src/`) and applies `patches/sotn-decomp.patch` (`git apply`). `env.example.toml` sets `repo = ".env/src/sotn-decomp"`. | ✅ **Recommended.** Zero submodules to break on clone, identical pattern to `swanstation`/`pcsx-redux` in `bootstrap.sh`, and updating the pinned decomp revision is a one-line SHA bump + `git apply --check`. |
| B. Git submodule at `decomp/` pointing to a fork | Keep a forked `sotn-decomp` as a submodule | ❌ Still requires maintaining a fork (violates D72). |
| C. Binary-patch `DRA.BIN` without compiling `sotn-decomp` | Patch the 5 `jal` instructions directly in retail `DRA.BIN` | ❌ Loses compile-time verification of `dra.map`, stage overlay symbol maps (`gen_overlay_table.py`), and header layout checks. |

### History migration & layout
- **History preservation:** `git subtree split --prefix=mods/co-op -b coop-standalone` extracts all commits touching `mods/co-op/` with paths rooted at `/` (`AGENTS.md`, `docs/`, `harness/`, `launcher/`, `link/`, `module/`, `patcher/`, `scripts/`, `installer/`).
- **Path updates:**
  - `env.example.toml`: `repo = ".env/src/sotn-decomp"`, `disks = ".env/disks"` (or symlinked from `win_masters` by `bootstrap.sh`).
  - `module/Makefile`, `scripts/build_disc.sh`, `scripts/gen_flag_gated.py`, `scripts/gen_overlay_table.py`: read `REPO` from `coop_env.py` / `env.toml` instead of assuming `../../..`.
  - Include paths in `src/dra/*.c` hooks (inside `patches/sotn-decomp.patch`): use `-I$(COOP_MOD)/module` and `#include "coop_api.h"` so the module location is decoupled from `sotn-decomp`'s directory tree.
- **Self-hosted CI (`.github/workflows/ci.yml`):**
  - Runs on `self-hosted` (this WSL2/Linux machine).
  - Links `.env` cache/discs/toolchains from a persistent runner cache directory (`~/.cache/sotn-coop-ci`), runs `scripts/bootstrap.sh`, `scripts/doctor.py`, `scripts/build_disc.sh`, `patcher/test_patcher.py`, and `harness/run.py` (all scenarios).
  - Fails if any retail disc sector moved or if any tracked file contains game data.

---

## Part 2: Online PC co-op

### 2.1 Single-game online session (`Session` & `GameView`)
In M6 couch play, `Session` spawns two local emulator workers (`s.a`, `s.b`) and `GameView` draws both side by side (`2 × 512×480`), mixing audio and muting one game's music.
For online play:
- **`OnlineSession(disc, start, role, peer_transport, session_file)`:**
  - Spawns **one** local emulator worker (`s.local`, with `rank=0` for the host / room creator and `rank=1` for the joiner, D50).
  - Runs one `Host` connected to the remote peer over `UdpTransport`.
  - Exposes the same interface to `GameView` (`games = (s.local,)`).
- **`GameView` single-screen mode:**
  - Centers or scales the single player's screen (`256×240 × 2` or window-fitted 4:3) with the status bar underneath showing connection state (`Connected (ping 18 ms) · Together/Apart`), or any active `host.mismatch` / reconnecting notice.
  - **Audio (D55):** `CONTROL_MUTE_MUSIC` is never set in online mode; each player hears 100% of their own game's music and SFX.
  - **Event savestates & F9 reports:** work identically, saving `<time>_<event>_local.state.zst` and full single-side + 60s link-traffic F9 reports.

### 2.2 Smooth WAN transport: compressed, MTU-safe snapshots (`docs/link-protocol.md` v9)
As researched (`docs/research.md`), raw `SNAP` payloads are ~8 KB (up to ~16 KB with tilemap/VRAM), which exceeds internet path MTU (~1200–1400 bytes) and causes IP fragmentation packet loss on consumer routers.

| Option | Idea | Verdict |
|---|---|---|
| **A. `zlib` compression + application-layer MTU chunking (`≤ 1200` bytes)** | Compress `SNAP` payloads with `zlib.compress(snap, level=1)` (stdlib, ~0.1 ms, shrinks 8 KB to ~1.2 KB) and split into `≤ 1200`-byte datagrams (`TAG_SNPC` header: `snap_seq: u32, chunk_idx: u8, chunk_cnt: u8`). The receiver reassembles when all chunks of the newest `snap_seq` arrive and drops older partial sequences. | ✅ **Recommended.** Zero new binary dependencies, fits most snapshots in 1–2 MTU-safe packets, never triggers IP fragmentation, and degrades gracefully under packet loss. |
| B. Raw 8 KB UDP datagrams | Rely on OS IP fragmentation | ❌ Fails on many home routers/VPNs and magnifies packet loss 7×. |
| C. Send snapshots over TCP | Parallel TCP stream for `SNAP` | ❌ Head-of-line blocking causes multi-frame freezes whenever a single packet drops. |

- Backward-compatible in `link/transport.py`: small snapshots that fit in one datagram after compression still arrive in a single packet; multi-chunk snapshots reassemble in `UdpTransport` before `Host.after_frame()` sees `TAG_SNAP`.

### 2.3 Zero-infrastructure connect codes + direct-IP fallback
We want Slippi-style ease of use with **zero servers to run or pay for** (D74):

| Option | Idea | Verdict |
|---|---|---|
| **A. Hybrid Zero-Infra: Public Relay Room Code + Stateless STUN Code + Direct IP** | **1. STUN + UPnP:** On "Host Online" / "Join Online", the launcher attempts UPnP/NAT-PMP port mapping on the local router and queries public STUN (`stun.l.google.com:19302`, `stun.cloudflare.com:3478`) on the game's UDP socket to learn its public `ip:port`.<br>**2. Short Connect Code:** A 6-character code (e.g. `BAT-429`) pairs the two players via a public zero-account WebSocket relay (Nostr public relays `wss://relay.damus.io`, `wss://nos.lol`), exchanging both sides' STUN `ip:port` + local LAN `ip:port` so both sides simultaneously UDP hole-punch.<br>**3. Stateless Code & Direct IP fallback:** Always displays the stateless 10-char endpoint code (base32-encoded `ip:port`, which needs no relay at all) and accepts raw `ip:port` (for LAN, VPN/Tailscale, or manual port-forwarding). | ✅ **Recommended.** Zero infrastructure owned by us; 6-char room code in the common case; 100% offline/relay-free fallback via the stateless endpoint code or `ip:port`. |
| B. Stateless STUN endpoint code only | Encode `ip:port` in base32; both players type each other's 10-char code | Good fallback, included inside A, but typing two 10-char codes is clunkier than a 6-char room code when public relays are reachable. |
| C. Custom cloud rendezvous server | Run our own Fly.io / Cloudflare service | ❌ Violates zero-infra requirement (D74). |

### 2.4 Online joint saves, Continue, and both-dead reload
In couch play, `JointSave` sits above both local mailboxes in one process. Online, each PC only has its own mailbox:
- **Save rooms:** when Player A saves in a coffin (`save_seq` increments), Host A sends `SAVE` (containing A's stage, block, roomX, roomY, and `SaveData` blob) over the reliable channel (`ReliableChannel`) to Host B. Host B issues `CMD_SAVE_NOW` to Game B, writes `session.coop` with both blobs once Game B finishes its card write, and sends B's `SaveData` blob back to Host A so both PCs have identical `session.coop` files and matching memory-card saves.
- **Both-dead reload & Continue:** when both players are `DEAD` for 4 frames (or when starting an Online Continue session), the host (`rank=0`) sends the `session.coop` save pair over the reliable channel so both games load their respective `SaveData` and `CMD_LOAD_SAVE` together.

### 2.5 Version mismatch refusal
- `Host` already checks `HELO` (`{"link": LINK_VERSION, "patch": patch_crc}`, sent every 60 frames) and sets `host.mismatch` while stopping all relay traffic (`docs/link-protocol.md`).
- In M7:
  - Both the online connection screen and the in-game status bar check `host.mismatch`.
  - If set during handshake or mid-session, the launcher shows a clear message screen explaining whether the **launcher/link version** or **co-op disc patch version** differs, and keeps listening for a matching `HELO` if the partner updates.

---

## Defaults (reversible, logged as `agent-default`)
- **Host = rank 0, Joiner = rank 1:** the player who chooses "Host Online" is `rank=0` (breaks shared-room ties and owns the canonical `session.coop` on Continue); "Join Online" is `rank=1`.
- **Snapshot compression:** `zlib` level 1 with a 1200-byte chunk limit (`MAX_CHUNK = 1200`).
- **Keepalive & reconnect:** `HELO` every 60 frames (1 s) doubles as the UDP NAT keepalive; if no packet arrives for 15 s, the status bar shows `"Waiting for partner (connection lost)..."` and automatically resumes when packets return.

## Acceptance criteria (multi-instance harness tests)
1. **Standalone repository & history (`D72, D73`):**
   - `tucker-bower/sotn-coop` contains the full commit history of `mods/co-op/`.
   - From a clean checkout with no pre-existing build, `scripts/bootstrap.sh && scripts/doctor.py && scripts/build_disc.sh` fetches the pinned `sotn-decomp`, applies `patches/sotn-decomp.patch`, builds the byte-identical co-op disc, and verifies 115/115 retail matching with `COOP` off.
2. **Self-hosted CI (`D73`):**
   - `.github/workflows/ci.yml` runs on the self-hosted runner on push/PR and passes `doctor.py`, `build_disc.sh`, `test_patcher.py`, and `harness/run.py`.
3. **MTU-safe compressed snapshots (`online_mtu_and_loss`):**
   - With a simulated WAN transport in the harness enforcing a strict **1200-byte UDP packet size limit** (dropping any packet > 1200 bytes), 20 ms RTT latency, and 2% random packet loss, two games enter the entrance hall together (`shared_same_enemies` / `guest_hits_count`), fight and kill enemies, and sync foreground tile changes (`guest_blocked_by_closed_door`) with zero dropped snapshots > 1200 bytes and full state convergence.
4. **Connect codes & direct-IP (`online_connect_codes`):**
   - Stateless base32 endpoint codes encode/decode `(ip, port)` round-trip and reject corrupted codes with a plain error.
   - Loopback room-code discovery and direct `ip:port` connect two `OnlineSession` instances and complete the `HELO` handshake within 2 s.
5. **Version mismatch refusal (`online_version_mismatch`):**
   - Two `OnlineSession` instances with different `link` versions or different `patch_crc` values refuse each other within 2 s, surface the exact human-readable refusal reason to the launcher, relay zero presence/events/snapshots, and recover automatically when a matching `HELO` arrives.
6. **Online joint save, Continue, and both-dead reload (`online_joint_save`):**
   - With two separate `OnlineSession` instances (separate memory cards and separate `session.coop` paths, linked only over UDP), Player A saves in the Alchemy Lab coffin. Both instances write their memory cards and both write identical `session.coop` files over the network link.
   - When both players die, both reload `session.coop` into the save room.
7. **Full regression suite:**
   - All existing 57 scenarios plus the new M7 online scenarios pass on both OpenBIOS and retail BIOS.

## Risks
- **Strict Symmetric NATs (carrier-grade NAT / cellular):** STUN + simultaneous UDP hole punching works on ~80–85% of home routers (Full Cone, Restricted Cone, Port-Restricted Cone), but fails when both peers are behind Symmetric NAT without UPnP. Mitigation: attempt UPnP IGD port mapping first, and clearly tell the user in the UI if symmetric NAT blocks direct UDP (suggesting UPnP, port forwarding, or Tailscale/ZeroTier with direct IP).
- **Public Nostr relays unreachable or rate-limited:** The launcher queries 3 public relays in parallel with a 3 s timeout and always displays the stateless 10-char STUN endpoint code + direct `ip:port` on the same screen so connection never depends on a third party.
