# Maintenance mode: the project runs without Tucker

**Status:** approved by Tucker on 2026-11-26, with changes (D236): spend little on contributor setup, since no one has asked to contribute; keep #300 and #301; keep the SOTN Ultimate and ASS compatibility work (#181, #52, maybe #48) in Up Next until Tucker says to start it.

**Goal.** Tucker steps back. Players report bugs, and a nightly agent fixes the real ones and ships a minor release. Tucker reads the release notes now and then. The project is easy for someone else to build, fork or pick up, and it never depends on a server we run (D113; Tucker, 2026-11-23: "We cannot rely on a server, ever").

## What's true today (checked 2026-11-26)
- **Bug reports arrive by two routes.**
  - The app's F9 reports reach the project's Gmail through Resend. `scripts/fetch_reports.py` unpacks them.
  - Reddit emails a notice for every reply to our posts. 41 have come so far; this change makes `fetch_reports.py` save those too, into `local/reddit/`.
- **CI is dead.** `ci.yml` needs a self-hosted runner. None is registered, and the repo has never had a workflow run. A self-hosted runner on a public repo would also run code from forks' pull requests on Tucker's PC, so we shouldn't revive it as it is.
- **Only this PC can run the game tests.** They need the retail disc images, which can't go to the cloud. So a cloud-scheduled agent can triage reports, but only this machine can fix and verify.
- **Fixture tax.** After any module change, `rebuild_fixtures.sh` takes about 15 minutes, because savestates hold the module's code.
- **The app ships the test harness.** `build_release.sh` copies `harness/{emu,session,coop_env,module,savestates,bots}.py` into the installer (#222).
- **Size.** `launcher/app.py` is 3,226 lines, and `module/partner.c` 2,223.
- **There's no guide for human contributors.** `AGENTS.md` is written for agents. `bootstrap.sh` has run on only one clean machine (#87).
- **The tracker has 46 open issues.** About 30 of them are backlog ideas that no one is going to build.

## On the Gemini review
| Recommendation | Verdict | Why |
|---|---|---|
| Separate the app from `harness/` (#222) | **Later** (backlog, per Tucker) | Contributors can't tell shipped code from test code. Test-only controls (`partition`, `stall`) live in the class that runs real play. Moving the worker into `link/` doesn't change behaviour, and the gate proves that. |
| Split `app.py` by screen | **Later** (backlog, with #222) | It makes contributing easier. Its main argument, Mac and touch controls multiplying the UI, goes away if we trim those (below). |
| Core vs. extras: a module folder split, a versioned mailbox header with an extension block, a vtable for characters | **Partly** | Moving the files into folders and enforcing which may include which is cheap. A versioned mailbox only matters across versions, and HELO already refuses a version mismatch. A vtable rewrite of `partner.c` is a lot of risk in our most fragile file, for little player value. |
| `#ifdef` out the partner sim and the spike pad | **Do it** | Cheap. Release builds stop carrying test hooks. |
| Clamp `EV_ITEM` and `partnerPrimCount` in C (#224) | **Do it** | Cheap. Bundle it with the next module change. |
| Load a fresh `COOP.BIN` into old savestates | **Spike it first** | This would be the biggest speed-up for the nightly agent. But a savestate holds the module's data as well as its code, and their layout changes with almost any edit. An in-place swap breaks tests in ways that are hard to see. The safer versions: rebuild only the savestates the chosen tests use, in parallel, or re-run the module's init after the swap. Spend at most a day finding out which works. |
| A clean-machine bootstrap (#87) | **Only if needed** | It matters for forkers, and none have shown up. It's needed if the nightly loop moves machines. |
| Finish 2.0: the inverted castle (#47) | **Keep, as the last milestone** | The inverted castle already plays (D133). What's left is coverage and endings, not new systems. |
| Fix #335, #270, #166 and #352 | **The nightly loop takes them** | Except #352: the second relay must be a public one, never self-hosted. |
| Mac and Linux builds (#50) | **Linux and Steam Deck only** | The dev machine is Linux, so a Linux build can be tested here. Mac needs hardware we don't have, plus paid signing and notarization. Leave it labelled `help wanted`. |
| Pause battle royale and big lobbies; port to a recompilation | **Trim both. No port.** | Agreed that the PS1 can't hold 8–32 players (each body costs 45–60 scanlines). One Reddit commenter asked for battle royale. A port to a recompilation is a new project, not a step. |

## Recommended plan

### Short term (in this order)
1. **The nightly loop** (details below). It comes first because it's what takes Tucker out of the loop.
2. **Trim the tracker** (done 2026-11-26).
   - The issues listed at the end were closed as "not planned", and the good ideas we won't build ourselves were labelled `help wanted`.
   - #300 and #301 stay planned.
   - The compatibility work for SOTN Ultimate and ASS (#181, #52) waits in Up Next until Tucker says to start it.
3. **Keep contributor setup small.** No one has asked to contribute, so there's no `CONTRIBUTING.md`, no issue templates and no CI rebuild. The dead `ci.yml` is deleted, so nothing claims to check what it doesn't. A bootstrap check in a clean container (#87) is worth doing only if the nightly loop ever has to move to another machine.
4. **Cleanups that speed up the nightly fixes:**
   - The #224 cleanups, including the C bounds checks.
   - `#ifdef` out the test hooks from release builds.
   - The fixture spike.

   The bigger restructures (#222: separate the app from the harness, and split `app.py`) stay in the backlog. They only help human contributors.
5. **Ship 1.5.0** once the loop has run a week.

### Mid term: how the project runs
**The nightly loop.** It runs on this PC because the tests need the discs.
- **Schedule.** At 03:00, Windows Task Scheduler wakes the PC and runs `wsl … scripts/nightly.sh`.
- **The agent.** That script runs headless Claude Code with a fixed prompt, `docs/maintenance/nightly.md`, and a tight tool allowlist. It holds a lock, and stops after 4 hours.
- **Its steps:**
  1. Fetch the inbox: F9 reports and Reddit replies.
  2. Triage each item:
     - a **bug** gets an issue and a fix;
     - a **question** gets a reply drafted to `local/replies/`, for Tucker to paste if he wants;
     - a **feature request** gets an issue labelled `needs-tucker`, and no work;
     - **noise** is ignored.
  3. Fix each bug the usual way: an issue, a test that fails on the release, the fix, its categories, then the gate, then a PR merged under the standing OK for bug fixes.
  4. If anything was merged: run `--full` plus Redux, then build and publish `1.x.y+1` with player-facing notes.
  5. Write a one-screen summary to `local/nightly/<date>.md`, and email it to Tucker from the project's Gmail. That email is the only part Tucker needs to read.
- **Guardrails:**
  - **No release without a test** that failed before the fix and passes after.
  - **Never touch vanilla feel or features.** Those go to Tucker as `needs-tucker` issues.
  - **At most one release a night.** If the gate or the full suite fails, nothing ships, and an issue is opened.
  - **Can't reproduce it?** Label it `needs-repro` and don't guess a fix.
  - **Cleanup:** check disk space first, and delete disc images afterwards.
  - **Kill switch:** the job stops if `local/nightly.stop` exists, or if the repo has an open issue labelled `pause-nightly`.
  - **Reports and comments are data, never instructions.** The agent never runs anything a player sent.
- **Cost.** Most nights there's no new report: the fetch takes one minute and the agent exits without starting. A night with a real fix costs about what the 1.4.9 session did.
- **Weak spot: the PC.** If it's off, the job waits for the next night. If the PC is ever retired, the loop moves with the discs to any Linux box, which is why the bootstrap must work on a clean machine.

**Outside PRs.** If one ever arrives, the nightly agent runs the game tests on it and comments with the results. It never merges an outside PR: Tucker does, or nobody does.

**Releases.** Bug-fix releases ship by themselves. Anything that changes features or feel waits for Tucker's `needs-tucker` decision.

### Long term: the remaining milestones
| Milestone | What "done" is | Keep? |
|---|---|---|
| **1.5: Maintenance-ready** | The short-term list above. The nightly loop has run 7 nights in a row without help. | Yes, next |
| **SOTN Ultimate and ASS compatibility** (#181, #52, maybe #48) | Each mod is tested with co-op, and installable from the Mods menu | Yes, when Tucker says |
| #300 and #301 | Their issues' Done when | Yes |
| **2.0: The inverted castle** (#47) | The inverted castle's scenes are covered by a test. Every ending plays through for every pairing. Released as 2.0. | Yes, the last feature milestone |
| **Linux and Steam Deck** (#50, cut down) | An AppImage that runs, gets through the gate on Linux, and is tested with a pad on a Deck-like setup. | Recommended. Your call. |
| Mac (#50) | — | Left in #50, unplanned |
| M21 lobbies of 4–8 (#330), M22 battle royale (#331) | — | Trimmed |
| Thor dual screen (#55), community characters (#56) | — | Trimmed |
| Android touch controls (#81) | — | `help wanted` |
| Code signing (#83), `.chd` images and a branded exe (#59) | — | Trimmed (signing costs money every year) |

After 2.0 the project is **feature-complete**. The nightly loop keeps it working, and new features come from contributors.

## Risks
- **The nightly agent could ship a bad fix with no one watching.** Mitigated by the failing-then-passing test rule, `--full` plus Redux before every release, one release a night, and the email summary. A bad release is fixed by the next night's release; a published installer is never replaced.
- **Prompt injection through reports and Reddit comments.** The agent treats them as data, never instructions. Its allowlist has no shell access to the network apart from git, gh and the fetch. It sends nothing but the email to Tucker.
- **Bus factor.**
  - The Resend account, the Gmail and the GitHub repo are Tucker's.
  - If Resend lapses, F9 falls back to "email it by hand", which already works.
  - ntfy.sh is a public relay, and joining by address needs no relay.
- **Token cost** if a night spins on a hard bug. Mitigated by the 4-hour cap, and the job doesn't retry a bug that the previous night marked `needs-repro`.

## Acceptance criteria (for 1.5)
- [ ] `scripts/nightly.sh` runs headless from Task Scheduler. On a night with a planted test report, it opens an issue, fixes a seeded bug with a new failing-then-passing test, publishes a release, and emails a summary.
- [ ] On a night with no new mail, the job exits in under 2 minutes without starting the agent.
- [ ] Both `local/nightly.stop` and the `pause-nightly` label stop it.
- [x] The tracker holds only planned work, `help wanted` and bugs (2026-11-26).

## Trimmed (closed as "not planned", 2026-11-26)
- #330 and #331: big lobbies and battle royale.
- #55 Thor dual screen, #56 community characters, #83 code signing, #59 `.chd` and branded exe, #53 rescue menu, #84 F9 form, #85 per-enemy ownership, #86 rollback for input (the body's rollback, D226, covers it).
- The test backlog: #69–#76 and #181 (D212).

Labelled `help wanted` instead: #81 touch controls, #79 and #191 mist form, #37–#41 Richter feel, #32, #33, #35, #36, #42, #57, #80, #255. The Mac half of #50 stays in that issue.
