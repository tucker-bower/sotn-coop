# AGENTS.md: how we build SOTN Co-op

This file is how we work together. Before doing anything, read:
1. `docs/TECHNICAL_SUMMARY.md`: what we've built and how it works.
2. The [tracker](https://github.com/users/tucker-bower/projects/1): where we are and what's next. Critical comes first, then Up Next.

Then run `scripts/doctor.py`, which checks the toolchain, discs and build. Setup and paths are in `DEVELOPER_GUIDE.md`. If `LOCAL.md` exists, read it too: it's git-ignored and covers this machine and its devices.

## Where things live
Each fact has one home. Read these only when the task needs them, and search the long ones instead of reading them through.

| File | Holds | Update it when |
|---|---|---|
| `docs/TECHNICAL_SUMMARY.md` | What exists and how it works | The architecture changes |
| [GitHub issues](https://github.com/tucker-bower/sotn-coop/issues) | All project tracking: bugs, features, test gaps, open decisions | As the work moves |
| `docs/ROADMAP.md` | The final goal, and the milestones already built | The goal changes |
| `docs/DECISION_LOG.md` | Why we chose what we chose (Dnn) | A decision is made |
| `docs/research.md` | What we've learned: game internals, tools, hard-won lessons | You learn something a future agent would otherwise rediscover |
| `docs/design/` | Designs for bigger work, with their acceptance criteria, for future agents | Before and while building it |
| `docs/link-protocol.md` | The wire protocol | The protocol changes |
| `harness/README.md` | How to write tests | The test API changes |
| `LOCAL.md` (git-ignored) | This machine, its devices, playtest workflow | The setup changes |

Every folder has a `README.md`: one sentence, then a table of its files. Update it when you add, remove, rename or retire a file. Mark a file **Vestigial** when nothing needs it to build, ship or test, and **Manual** when it's a tool no runner includes. `.github/` is the one exception, because a README there would replace the repo's front page on GitHub.

Git and PRs hold the history, so don't write session logs. Replace what's out of date rather than adding to it: less is more.

## Roles
- **Tucker (owner):** owns architecture, design, scope and game feel, and approves milestone designs and PRs. He is an experienced engineer, but his time is the scarcest resource on this project. Optimize for minimal owner time, not minimal agent effort.
- **Agent (implementer):** owns implementation, testing and evidence. Work autonomously for long stretches. Don't stop mid-task to report: checkpoint and continue until it's done or truly blocked.

## The loop (issue-driven)
The game is mostly built, so the work is now feature requests and bug fixes, and every piece of it is a GitHub issue.
1. **Every piece of work has an issue.** Bugs, features and test gaps each get one, labelled `bug`, `feature` or `test coverage`, on the [tracker](https://github.com/users/tucker-bower/projects/1). If you find something and won't fix it now, open an issue rather than writing it in a doc. Don't track work in markdown files.
2. **Work the tracker in order:** Critical, then Up Next. Tucker owns the columns and moves Backlog items up. Set an issue to In Progress when you start it.
3. **Design bigger work.** For a new feature or anything hard to reverse, write a one-page `docs/design/<name>.md` with 2–3 options, a recommendation, risks and **testable acceptance criteria**, link it from the issue, and don't write the code until Tucker approves it. Small spikes are fine. Bug fixes and small features need no design: the issue's "Done when" list is the spec. Designs are for future agents: record what was chosen and why, not status.
4. **Build autonomously** on a branch named `coop-<short-name>`.
5. **Open a PR** using the template below, with a `Fixes #n` line for each issue: one keyword covers one issue only. If PRs are stacked, confirm the work actually reached `main` after merging. Merging closes the issues; check that it did.
6. **Playtest** at bigger releases: deliver an installer and APK, with a short sheet of what to try.

## Decisions
- **Reversible:** pick a sensible default, log it in `docs/DECISION_LOG.md` (choice, options considered, why, marked `agent-default`), and keep going. Don't block on Tucker.
- **Expensive to reverse, or changes game feel or scope:** stop, write up the options in the issue, and work on something else that isn't blocked.
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
- **Releases:** Tucker publishes them. Upload only to a release that's still a draft, and never replace a published installer: make a new version. Every release's notes (`docs/releases/`) include a clear, concise changelog written for players, and Tucker approves the text first.
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
| Everyday (293 tests) | 10 minutes | Before committing a major change, and before opening or updating a PR with code changes |
| `--full` (395 tests) | 30 minutes | Only before a release, playtest betas included, together with `scripts/redux_check.sh` |

**After a module change, rebuild first:** `scripts/rebuild_fixtures.sh` (about 15 minutes) rebuilds the disc, Maria's patches and every savestate, because savestates hold the module's code. Don't rebuild while tests are running.

**New tests:** `harness/README.md` shows how to write them. Name a test for what it checks, with no milestone prefix: `<feature>_<what>`, and `_<A>_and_<B>` for character pairings (`_vs_` for PvP), e.g. `boss_olrox_richter_and_maria`. New tests go in the everyday tier unless they're a soak or one more pairing of something everyday covers (`full=True`). Keep everyday at 10 minutes or less by moving repetition to `--full`.

## PR template
Before Issuing a PR, run the everyday test suite. The full test suite should only be run before creating a new release. Additonally, check that all documentation is up-to-date before issuing the PR, including the md roadmap, repo root readme, and status.

```
Fixes #<issue>
Fixes #<issue>

## Acceptance criteria
- [x] <criterion>: <evidence: test name / clip / numbers>
## Defaults I chose (reversible)
- <decision>: <why>
## Risks / known issues
```
