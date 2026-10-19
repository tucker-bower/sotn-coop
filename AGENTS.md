# AGENTS.md: working on SOTN Co-op

These instructions are for any AI coding agent working in `mods/co-op/`. Read this file, then `docs/STATUS.md`, before doing anything. The project goal changed on 2026-10-18 to independent exploration with one game per player (`docs/DECISIONS.md` D19–D31). Then run `scripts/doctor.py`: it checks the toolchain, discs and build. Every path (discs, emulators, savestates) is in `env.example.toml` / `env.toml`, and setup is in `SETUP.md`.

## Roles
- **Tucker (owner):** owns architecture, design, scope and game feel, and approves milestone designs and PRs. He is an experienced engineer, but his time is the scarcest resource on this project. Optimize for minimal owner time, not minimal agent effort.
- **Agent (implementer):** owns implementation, testing and evidence. You are expected to work autonomously for long stretches.

## The loop (spec-driven)
1. **Design first.** Before each milestone, write a one-page proposal in `docs/design/Mx-<name>.md`. It should give 2–3 options, a recommendation, risks, and **testable acceptance criteria**. Don't write milestone code until Tucker approves it. Small spikes to de-risk the proposal are fine.
2. **Build autonomously** on a branch named `coop-mx-<short-name>` (git can't nest under the existing `coop` branch).
3. **Open a PR** using the template below.
4. **Playtest** at milestones: deliver a patched disc image and short testing instructions.

## Decisions
- **Reversible decision:** pick a sensible default, log it in `docs/DECISIONS.md` (choice, options considered, why, marked `agent-default`), and keep going. Don't block on Tucker.
- **Expensive to reverse, or changes game feel / scope:** stop, write up the options in `docs/STATUS.md` under "Decisions needed", and work on something else that isn't blocked.
- Batch questions. Never send Tucker one question at a time.

## Communication
- Be brief and lead with outcomes. Tucker wants results and decisions, not narration.
- Never ask Tucker to read webpages, docs or Discord himself. Read them yourself and summarize into `docs/research.md`.
- Keep `docs/STATUS.md` current at the end of every work session: done, in flight, next, budget used, decisions needed.
- Report problems early, especially anything that changes what Tucker will get or what it costs.

## Engineering rules
- **Never commit game data.** That covers disc images, extracted files, ROM-derived assets and savestates containing game RAM. Check `git status` before every commit.
- **Keep each instance deterministic.** No uninitialized reads, and no timing- or emulator-dependent behavior inside the game. Harness reproducibility depends on it, and so may shared rooms (D23). Timing-dependent behavior belongs in the host, never in the game.
- **Emulator-specific code stays in the adapter.** The product emulator isn't chosen yet (R1, D28). Anything that talks to an emulator (RAM read/write, frame callback, input) goes through one thin adapter.
- **Minimize upstream diffs.** Put mod code in `mods/co-op/` and touch upstream `src/` through small, well-commented hooks. That keeps rebasing on upstream sotn-decomp cheap.
- **Tooling in Python** where practical (test harness, bots, scripts), so Tucker can read and modify it easily.
- **Evidence over claims.** "Works" means a harness test passes. Attach the results, plus a short clip or screenshot for anything visual.
- Commit messages end with the session attribution lines. PR descriptions end with the Claude Code footer.

## Testing
- **Primary:** a headless, frame-stepped harness with savestates, scripted and bot inputs, and RAM assertions.
- **Multi-instance session tests:** run two game instances plus the host yourself, with scripted inputs on both and assertions across both games. Co-op features count as working only when a session test proves it. Don't wait for Tucker to run a two-player check.
- **Secondary:** emulators on Tucker's PC at `C:\Users\tucke\OneDrive\Desktop\Emulators`. Install anything needed there and use it for cross-emulator compatibility checks. Ask before installing anything outside that folder.
- **Before any playtest build:** boot-and-run checks on the dev platform, plus PCSX-Redux, and on the product emulator once R1 has chosen it.

## PR template
```
## What
<one paragraph, outcome-focused>
## Acceptance criteria
- [x] <criterion>: <evidence: test name / clip / numbers>
## Defaults I chose (reversible)
- <decision>: <why>
## Risks / known issues
## Budget
<sessions or usage spent vs. milestone budget>
```

## Budget
The project runs on a Claude **Pro** subscription, with a target of **finishing in about a month**. Pro has rolling usage limits (resetting every 5 hours, plus possible weekly caps), so the budget is measured in usage windows, not tokens. See `docs/ROADMAP.md`.
- Prefer RAM-text state over screenshots, and cache-friendly long sessions over many cold starts.
- If a milestone runs about 50% over its budget, stop and report in `docs/STATUS.md` before continuing. Tucker may consider a plan upgrade.
