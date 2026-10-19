# Test harness

Headless, frame-stepped SOTN on the SwanStation libretro core, at about 25× real time on Tucker's PC. Setup is in `../SETUP.md`.
Run everything with the repo's venv: `../../../.venv/bin/python <script>`.

| Command | What it does |
|---|---|
| `python savestates.py [disc.cue]` | Builds the savestate library for that disc (~20 s): `entrance` (after Death takes the gear), `nz0` Alchemy Lab, `no0` Marble Gallery, `no1` Outer Wall. |
| `python run.py [scenario...]` | Runs scenarios from `scenarios.py`. Writes `.env/out/<name>/report.json` and `clip.gif`. |
| `python lockstep.py --minutes 10` | Determinism check from M0: two processes, same inputs, rollback-style state reloads, RAM hashes compared every second. `--inject-desync N` proves it can fail. It's no longer the netplay model (D20), but it's still useful as a check that each instance is deterministic, and for the M4 lockstep-merge option. |
| `../scripts/build_disc.sh` | Builds `.env/out/disc/sotn_coop.us.cue` with the co-op module. |
| `../scripts/redux_check.sh` | The same module check in the Windows PCSX-Redux, headless, via `redux_check.lua`. |

## Writing a scenario
```python
@scenario(start="entrance")                  # savestate name; disc=... for a co-op build
def my_test(run):
    s = run.play(walker("left", attack_every=8), 600, until=lambda s: s["room"] == (14, 40))
    run.expect(s["room"] == (14, 40), "reaches the hall", room=s["room"])
```
`run.emu` gives you `step(n, p1, p2)`, `read("symbol", fmt, offset)`, `write(...)`, `snapshot()`, `save_state()` and `screenshot()`. Symbols come from the decomp's `config/symbols.us*.txt`, and co-op module symbols come from `build/coop/coop.map` (`module.py`).

## Things to know
- **Savestates are per disc image.** SwanStation refuses a state made on a different image, so rebuild the library after every `build_disc.sh` (it takes about 20 s).
- **Harness-only shortcuts** (never in the mod): `savestates.skip_prologue` (the game's own Richter-game-over path), `savestates.warp` (the debug module's stage load, keeping the player's status), and the Bat Card poke in `heartbeat_8mb`.
- Savestates, discs and GIFs contain game data. They live in git-ignored `.env/` and are never committed.
