# Dev setup (contributors and agents)

This is for working **on** the mod. Players never need any of it: they get a patcher in M5.

## One-time
1. Use Ubuntu 26.04, natively or in WSL2. Passwordless sudo makes the bootstrap unattended.
2. Put your own discs in `disks/` (git-ignored):
   - `sotn.us.cue` plus its `.bin` tracks: Symphony of the Night (USA). **Required.**
   - `sotn.pspus.iso`: Dracula X Chronicles (USA, ULUS-10277). Used in M8 for Maria and Richter.
3. Run `scripts/bootstrap.sh`. It fetches pinned `sotn-decomp` into `.env/src/sotn-decomp`, applies `patches/sotn-decomp.patch`, builds the SwanStation core and OpenBIOS, and verifies the 115/115 matching US build. Safe to re-run. Steps: `apt python swanstation openbios decomp`.
4. Run `scripts/doctor.py`. Every required check should be ✅.

## Where things are
Everything is listed in `env.example.toml`. Override per machine in `env.toml` (git-ignored).

| What | Where |
|---|---|
| Discs (working copies) | `disks/` |
| Master copies of discs and BIOS | `win_masters` (on Tucker's PC: `OneDrive\Desktop\Emulators\SOTN`) |
| SwanStation core, OpenBIOS, savestates, harness output | `mods/co-op/.env/` (git-ignored) |
| Python venv (decomp tools and harness) | `.venv/` at repo root |
| Matching build output | `build/us/` |

## Notes
- Ubuntu 26.04 has no `gcc-mipsel-linux-gnu`, so the bootstrap installs it from 24.04 via a low-priority apt pin (D12).
- If a first build fails partway through, run `rm -rf build/us` before rebuilding. Ninja keeps the broken objects.
- Upstream `make disk` rewrites the tracked file `include/lba_us.h`. Restore it with `git checkout include/lba_us.h` before committing.
