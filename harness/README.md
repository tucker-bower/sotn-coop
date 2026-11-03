# Test harness

Headless SOTN games for testing, plus the tests that drive them.

## Files
| File | What it does |
|---|---|
| `bots.py` | Scripted players. |
| `commands.py` | Registers the launcher checks, UI flows and patcher test with the runner. |
| `coop_env.py` | Loads `env.example.toml` and `env.toml`. |
| `core_check.py` | **Manual.** Checks a SwanStation core build on this machine. |
| `data/` | Reference data for the tests. |
| `emu.py` | One headless, frame-stepped game on SwanStation. |
| `fixtures_m12.py` | Builds the savestates the coverage tests start from. |
| `lockstep.py` | **Manual.** Checks determinism: two processes, same inputs, RAM hashes compared. |
| `module.py` | Reads the co-op module's symbols and state from RAM. |
| `playtest.py` | **Manual.** Bots play two games for minutes and flag anything odd. |
| `power_curve.py` | **Vestigial.** One-off balance measurement across the boss starts; nothing runs it. |
| `redux_check.lua` | Checks the module in PCSX-Redux, run by `scripts/redux_check.sh`. |
| `replay.py` | **Manual.** Replays a player's F9 report. |
| `requirements.txt` | Python packages for the harness. |
| `run.py` | The test runner. |
| `savestates.py` | Builds the savestate library from the player's own disc. |
| `scenario.py` | Runs one-game tests and writes their evidence. |
| `scenarios.py` | Basic one-game tests of the module. |
| `scenarios_m12.py` | One-game coverage: Maria's guardians, test castles and more. |
| `scenarios_m13.py` | One-game tests of the partner as a real player. |
| `scenarios_m8.py` | One-game tests of Richter and Maria in Alucard's castle. |
| `scenarios_movement.py` | Checks Richter and Maria move at least as far as Alucard at each relic step. |
| `scenarios_relics.py` | Relics, per character. |
| `session.py` | Runs two linked games, on the couch or online. |
| `session_bossrush.py` | Boss rush, end to end. |
| `session_inverted.py` | Inverted castle: travel and what partners share there. |
| `session_m11.py` | Castles, solo and the shared level. |
| `session_m12.py` | Cutscenes, bosses and story scenes together. |
| `session_m15.py` | PvP. |
| `realtime.py` | **Manual.** Two games at full speed on their own clocks, over a simulated connection: routes, screenshots, hangs. |
| `session_netplay.py` | Online play on the game's own route, with a playtest-like connection. |
| `session_rooms.py` | What the 0.14 playtest's reports found: doors, camera limits, the partner's body, scene votes. |
| `session_carry.py` | Hanging onto Bat Alucard, a castle rule. |
| `session_rules.py` | Each castle rule, turned off or moved, in two games. |
| `session_m4b.py` | Fixes from the first playtest. |
| `session_m5.py` | Bosses together. |
| `session_m8.py` | Mixed-character teams. |
| `session_m9.py` | Android's way of running a game, online with a PC. |
| `session_net.py` | **Vestigial.** Measures a session over simulated bad networks; left out of `run.py`. |
| `session_online.py` | Online PC co-op: connect codes and version checks. |
| `session_progress.py` | Shared progression. |
| `session_saverooms.py` | Joint saves in the game's save rooms. |
| `session_scenarios.py` | The link between two games, and presence. |
| `session_shared.py` | Shared rooms and enemies. |
| `session_travel.py` | Teleport, respawn, pause rules and joint saves. |
| `spec_test.py` | A partner written from `docs/link-protocol.md` alone, against a real game. |
| `vram_survey.py` | **Vestigial.** One-off survey of which VRAM the stages use. |

## Running things
Headless, frame-stepped SOTN on the SwanStation libretro core, at about 25× real time. Two linked games (`session.py`) run as two processes at about 30× each. Setup is in `../DEVELOPER_GUIDE.md`.
Run these with the venv: `.env/src/sotn-decomp/.venv/bin/python <script>`. How to run the tests is in `../AGENTS.md`.

| Command | What it does |
|---|---|
| `python savestates.py [disc.cue]` | Builds the savestate library for that disc (~20 s): `entrance` (after Death takes the gear), `nz0` Alchemy Lab, `no0` Marble Gallery, `no1` Outer Wall. |
| `python run.py` | The test runner: see `../AGENTS.md`. Writes `.env/out/<name>/report.json`, `clip.gif` and `log.txt`. |
| `python lockstep.py --minutes 10` | Determinism check from M0: two processes, same inputs, rollback-style state reloads, RAM hashes compared every second. `--inject-desync N` proves it can fail. A check that each game is deterministic. |
| `../scripts/build_disc.sh` | Builds `.env/out/disc/sotn_coop.us.cue`: DRA with its hooks, the boot stub, and `COOP.BIN`. Fails if a hook changes DRA's size or a retail file moves (`check_disc_layout.py`). Then run `savestates.py` on it. |
| `../scripts/redux_check.sh` | The same module check in the Windows PCSX-Redux, headless, via `redux_check.lua`. |

## Writing a scenario
Name it for what it checks (no milestone prefix): `<feature>_<what>`, pairings `_<A>_and_<B>` (`_vs_` for PvP). `@scenario(..., full=True)` / `@session_scenario(..., full=True)` puts it in `--full` only: for soaks and for more pairings of what the everyday suite already covers.
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
`run.s.a` / `run.s.b` proxy every `Emu` call, plus `mailbox(...)`, `unlink()` / `link()` (stop or resume a game's host), and `proc` (its worker process). The driver steps the games alternately, one frame each, so B gets A's presence for frame N before B's frame N+1. `session_scenarios.partner_pixels(game)` renders a game's next frames with and without its partner, to find the partner on screen. `session_progress.arrive(run, game, stage, roomId, x, y)` sends a game anywhere (CMD_ARRIVE), and `take()` stands it on a pickup. `Session(..., session_file=path)` runs the couch launcher's joint saves (`link/jointsave.py`).

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

## F9 reports
`python replay.py <report.zip> [--from N]` replays a player's F9 report in the harness, saving both screens every 10 frames next to the zip. The link isn't deterministic in the launcher, so a replay can differ a little; the states in `now/` are exact, for inspecting RAM.

## Things to know
- **The harness reads module addresses from `build/coop/coop.map`.** Don't rebuild the module (`make`) while tests run against the current disc: a moved `g_CoopLink` makes every mailbox read garbage. Rebuilding also needs `savestates.py` again, because savestates hold the module's code.
- **Savestates are per disc image.** SwanStation refuses a state made on a different image, so rebuild the library after every `build_disc.sh` (it takes about 20 s).
- **Harness-only shortcuts** (never in the mod): `savestates.skip_prologue` (the game's own Richter-game-over path), `savestates.warp` (the debug module's stage load, keeping the player's status), the RAM transplant in `no_effect_on_play`, and `heal()` in the soak.
- Savestates, discs and GIFs contain game data. They live in git-ignored `.env/` and are never committed.
