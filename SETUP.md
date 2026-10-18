# Dev setup (contributors and agents)

This is for working **on** the mod. Players never need any of it: they get a patcher in M5.

## One-time
1. Use Ubuntu 26.04, natively or in WSL2. Passwordless sudo makes the bootstrap unattended.
2. Put your own discs in `disks/` at the repo root (git-ignored):
   - `sotn.us.cue` plus its `.bin` tracks: Symphony of the Night (USA). **Required.**
   - `sotn.pspeu.iso`: Dracula X Chronicles (EU). Only needed for Maria.
3. Run `mods/co-op/scripts/bootstrap.sh`. It takes about 15 min and is safe to re-run. Steps: `apt python swanstation openbios decomp`.
4. Run `mods/co-op/scripts/doctor.py`. Every required check should be ✅.

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
