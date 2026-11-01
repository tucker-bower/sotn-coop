# AGENTS.md: how we build SOTN Co-op

This file is how we work together. Before doing anything, read:
1. `docs/TECHNICAL_SUMMARY.md`: what we've built and how it works.
2. `docs/ROADMAP.md`, the "Now" section: where we are, what's next, and any open decisions.

Then run `scripts/doctor.py`, which checks the toolchain, discs and build. Setup and paths are in `SETUP.md`. If `LOCAL.md` exists, read it too: it's git-ignored and covers this machine and its devices.

## Where things live
Each fact has one home. Read these only when the task needs them, and search the long ones instead of reading them through.

| File | Holds | Update it when |
|---|---|---|
| `docs/TECHNICAL_SUMMARY.md` | What exists and how it works | The architecture changes |
| `docs/ROADMAP.md` | Where we are, what's next, known issues, open decisions | At every checkpoint |
| `docs/DECISION_LOG.md` | Why we chose what we chose (Dnn) | A decision is made |
| `docs/research.md` | What we've learned: game internals, tools, hard-won lessons | You learn something a future agent would otherwise rediscover |
| `docs/design/` | One design per milestone, with its acceptance criteria | Before and while building it |
| `docs/link-protocol.md` | The wire protocol | The protocol changes |
| `harness/README.md` | How to write tests | The test API changes |
| `LOCAL.md` (git-ignored) | This machine, its devices, playtest workflow | The setup changes |

Git and PRs hold the history, so don't write session logs. Replace what's out of date rather than adding to it: less is more.

## Roles
- **Tucker (owner):** owns architecture, design, scope and game feel, and approves milestone designs and PRs. He is an experienced engineer, but his time is the scarcest resource on this project. Optimize for minimal owner time, not minimal agent effort.
- **Agent (implementer):** owns implementation, testing and evidence. Work autonomously for long stretches. Don't stop mid-milestone to report: checkpoint and continue until it's done or truly blocked.

## The loop (spec-driven)
1. **Design first.** Before each milestone, write a one-page proposal in `docs/design/Mx-<name>.md`, with 2–3 options, a recommendation, risks and **testable acceptance criteria**. Don't write milestone code until Tucker approves it. Small spikes to de-risk the proposal are fine.
2. **Build autonomously** on a branch named `coop-mx-<short-name>`.
3. **Open a PR** using the template below. If PRs are stacked, confirm the work actually reached `main` after merging.
4. **Playtest** at milestones: deliver an installer and APK, with a short sheet of what to try.

## Decisions
- **Reversible:** pick a sensible default, log it in `docs/DECISION_LOG.md` (choice, options considered, why, marked `agent-default`), and keep going. Don't block on Tucker.
- **Expensive to reverse, or changes game feel or scope:** stop, write up the options in `docs/ROADMAP.md` under "Decisions needed", and work on something else that isn't blocked.
- Batch questions. Never send Tucker one question at a time.

## Communication
- Be brief and lead with outcomes. Tucker wants results and decisions, not narration.
- Never ask Tucker to read webpages or docs himself. Read them yourself and put what matters in `docs/research.md`.
- Report problems early, especially anything that changes what Tucker will get.

## Engineering rules
- **Never end a session with unsaved work.** At every natural checkpoint, and before you could run out of usage, update the docs, then commit and push, even if the work is unfinished. Mark unfinished work as such.
- **Keep the repo clean of personal setup.** Local paths, device workflow and playtest sheets go in `LOCAL.md` and `local/`, which are git-ignored.
- **Never commit game data:** disc images, extracted files, ROM-derived assets, or savestates containing game RAM. Check `git status` before every commit.
- **Keep each game deterministic.** Timing-dependent behavior belongs in the host, never in the game.
- **Emulator calls go through the one thin adapter.**
- **DRA hooks stay size-neutral, and no retail file moves on the disc.** `build_disc.sh` enforces both.
- **Minimize upstream diffs.** Mod code lives in this repo. Changes to sotn-decomp and SwanStation go in `patches/`, as small, well-commented hooks, so updating the pinned versions stays cheap.
- **Tooling in Python** where practical, so Tucker can read and modify it easily.
- **Evidence over claims.** "Works" means a test passes. Attach the results, plus a short clip or screenshot for anything visual. Prefer reading RAM to reading screenshots: it's cheaper and exact.
- **Releases:** Tucker publishes them. Upload only to a release that's still a draft, and never replace a published installer: make a new version.
- Commit messages end with the session attribution lines. PR descriptions end with the Claude Code footer.

## Testing
Co-op features count as working only when a test proves it, and that usually means two real games. Run those yourself; don't wait for Tucker to do a two-player check.

**Every test runs through one runner**, side by side, each in its own process. That covers one-game scenarios, two-game sessions, launcher checks, UI flows of the real app, and the patcher. Use the bootstrap's venv:
```
PY=.env/src/sotn-decomp/.venv/bin/python
$PY harness/run.py --list -k WORD     # what would run, without running it
$PY harness/run.py -k pvp -k boss_rush   # every test with a word in its name
$PY harness/run.py pvp_off            # tests by exact name
$PY harness/run.py                    # the everyday suite
$PY harness/run.py --full             # everyday plus the full-only tests
```
Each test's report, clip and log are in `.env/out/<name>/`. The exit code is 0 only if all passed.

**Pick the smallest tier that covers the change** (D138):
| Tier | About | When |
|---|---|---|
| A handful, by name or `-k` | seconds to minutes | A small change |
| Everyday (212 tests) | 10 minutes | Before committing a major change, and before opening or updating a PR with code changes |
| `--full` (299 tests) | 30 minutes | Only before a release, playtest betas included, together with `scripts/redux_check.sh` |

**After a module change, rebuild first:** `scripts/rebuild_fixtures.sh` (about 15 minutes) rebuilds the disc, Maria's patches and every savestate, because savestates hold the module's code. Don't rebuild while tests are running.

**New tests:** `harness/README.md` shows how to write them. Name a test for what it checks, with no milestone prefix: `<feature>_<what>`, and `_<A>_and_<B>` for character pairings (`_vs_` for PvP), e.g. `boss_olrox_richter_and_maria`. New tests go in the everyday tier unless they're a soak or one more pairing of something everyday covers (`full=True`). Keep everyday at 10 minutes or less by moving repetition to `--full`.

## PR template
```
## Acceptance criteria
- [x] <criterion>: <evidence: test name / clip / numbers>
## Defaults I chose (reversible)
- <decision>: <why>
## Risks / known issues
```
