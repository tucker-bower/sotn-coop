# Dev setup (contributors and agents)

This is for working **on** the mod. Players never need any of it.

## One-time
1. Use Ubuntu 26.04, natively or in WSL2. Passwordless sudo makes the bootstrap unattended.
2. Put your own discs in `disks/` (git-ignored):
   - `sotn.us.cue` plus its `.bin` tracks: Symphony of the Night (USA). **Required.**
   - `sotn.pspus.iso`: Dracula X Chronicles (USA, ULUS-10277). Needed for Maria.
3. Run `scripts/bootstrap.sh`. It fetches pinned `sotn-decomp` into `.env/src/sotn-decomp`, applies `patches/sotn-decomp.patch`, builds the SwanStation core and OpenBIOS, and verifies the 115/115 matching US build. Safe to re-run. Steps: `apt python swanstation openbios decomp`.
4. Run `scripts/doctor.py`. Every required check should be ✅.

## Where things are
Everything is listed in `env.example.toml`. Override per machine in `env.toml` (git-ignored).

| What | Where |
|---|---|
| Discs (working copies) | `disks/` |
| Master copies of discs and BIOS | `win_masters` (on Tucker's PC: `OneDrive\Desktop\Emulators\SOTN`) |
| SwanStation core, OpenBIOS, savestates, harness output | `.env/` (git-ignored) |
| Python venv (decomp tools and harness) | `.env/src/sotn-decomp/.venv/` |
| Matching build output | `.env/src/sotn-decomp/build/us/` |

## Notes
- Ubuntu 26.04 has no `gcc-mipsel-linux-gnu`, so the bootstrap installs it from 24.04 via a low-priority apt pin (D12).
- If a first build fails partway through, run `rm -rf build/us` before rebuilding. Ninja keeps the broken objects.
- Upstream `make disk` rewrites the tracked file `include/lba_us.h`. Restore it with `git checkout include/lba_us.h` before committing.
- **Tucker's machine:** `.env` is a link into the old fork (`/home/tucker/sotn-decomp-coop/mods/co-op/.env`), and the decomp's `mods/co-op/module` is a link to this repo's `module/`. The decomp includes `mods/co-op/module/coop_api.h` through that link, so the path is real even though the repo no longer lives there.
