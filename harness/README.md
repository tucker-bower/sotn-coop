# Test harness

Headless, frame-stepped SOTN on the SwanStation libretro core, at about 25× real time on Tucker's PC. Two linked games (`session.py`) run as two processes at about 30× each. Setup is in `../SETUP.md`.
Run everything with the repo's venv: `../../../.venv/bin/python <script>`.

| Command | What it does |
|---|---|
| `python savestates.py [disc.cue]` | Builds the savestate library for that disc (~20 s): `entrance` (after Death takes the gear), `nz0` Alchemy Lab, `no0` Marble Gallery, `no1` Outer Wall. |
| `python run.py [scenario...]` | Runs scenarios from `scenarios.py` (one game) and `session_scenarios.py`, `session_progress.py` (M2) and `session_travel.py` (M3), all two linked games. No args: all of them but the long `*_NNmin` soaks, which run by name. Writes `.env/out/<name>/report.json` and `clip.gif` (side by side for two games). |
| `python lockstep.py --minutes 10` | Determinism check from M0: two processes, same inputs, rollback-style state reloads, RAM hashes compared every second. `--inject-desync N` proves it can fail. It's no longer the netplay model (D20), but it's still useful as a check that each instance is deterministic, and for the M4 lockstep-merge option. |
| `../scripts/build_disc.sh` | Builds `.env/out/disc/sotn_coop.us.cue`: DRA with its hooks, the boot stub, and `COOP.BIN`. Fails if a hook changes DRA's size or a retail file moves (`check_disc_layout.py`). Then run `savestates.py` on it. |
| `../scripts/redux_check.sh` | The same module check in the Windows PCSX-Redux, headless, via `redux_check.lua`. |

## Writing a scenario
```python
@scenario(start="entrance")                  # savestate name; disc=... for a co-op build
def my_test(run):
    s = run.play(walker("left", attack_every=8), 600, until=lambda s: s["room"] == (14, 40))
    run.expect(s["room"] == (14, 40), "reaches the hall", room=s["room"])
```
`run.emu` gives you `step(n, p1, p2)`, `read("symbol", fmt, offset)`, `write(...)`, `snapshot()`, `save_state()` and `screenshot()`. Symbols come from the decomp's `config/symbols.us*.txt`, and co-op module symbols come from `build/coop/coop.map` (`module.py`).

## Writing a two-game scenario
```python
@session_scenario(starts=("entrance", "entrance"))   # one savestate per game; discs=(a, b) optional
def my_test(run):
    run.step(60, p1=("right", ""))                     # (pad A, pad B), or a function of (i, snap A, snap B)
    run.expect(run.s.b.mailbox("partner_presence").x > 100, "B sees A move right")
```
`run.s.a` / `run.s.b` proxy every `Emu` call, plus `mailbox(...)`, `unlink()` / `link()` (stop or resume a game's host), and `proc` (its worker process). The driver steps the games alternately, one frame each, so B gets A's presence for frame N before B's frame N+1. `session_scenarios.partner_pixels(game)` renders a game's next frames with and without its partner, to find the puppet on screen. `session_progress.arrive(run, game, stage, roomId, x, y)` sends a game anywhere (CMD_ARRIVE), and `take()` stands it on a pickup. `Session(..., session_file=path)` runs the couch launcher's joint saves (`link/jointsave.py`).

## Autonomous playtests
`python playtest.py [tour ...] [--minutes N] [--seed S]` plays both games with bots for minutes at a time. The tours are `entrance`, `nz0`, `no0`, `no1`, and `castle`, which hops between stages through the game's own stage doors. The bots cycle through phases: together, apart, regroup by map teleport, room hops, and no healing.

**Flagged automatically:**
- a game stuck out of play;
- a frozen screen;
- dropped events;
- shared-room roles flapping;
- a guest whose enemies differ from the authority's;
- diverged progress.

**Output:** `.env/out/playtest/<tour>/` holds `report.json` and a screenshot of each anomaly. It also holds contact sheets, plus `suspect_*.png`: the six moments when the two screens differed most while sharing a camera, so look at those first.

## Launcher bookmarks
F9 in the playtest launcher saves `bookmarks/<time>/` next to the `.bat` files:
- both games' states now (`*_now.state`) and from 5–10 s before;
- the last 20 s of both pads;
- the window.

`python replay.py <bookmark dir>` replays it in the harness, saving both screens every 10 frames. The link isn't deterministic in the launcher, so a replay can differ a little; the `_now` states are exact.

## Things to know
- **The harness reads module addresses from `build/coop/coop.map`.** Don't rebuild the module (`make`) while tests run against the current disc: a moved `g_CoopLink` makes every mailbox read garbage. Rebuilding also needs `savestates.py` again, because savestates hold the module's code.
- **Savestates are per disc image.** SwanStation refuses a state made on a different image, so rebuild the library after every `build_disc.sh` (it takes about 20 s).
- **Harness-only shortcuts** (never in the mod): `savestates.skip_prologue` (the game's own Richter-game-over path), `savestates.warp` (the debug module's stage load, keeping the player's status), the RAM transplant in `no_effect_on_play`, and `heal()` in the soak.
- Savestates, discs and GIFs contain game data. They live in git-ignored `.env/` and are never committed.
