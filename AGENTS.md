# AGENTS.md

Rules for every AI agent working in this repo. Read this whole file before doing anything. These rules apply to you and to every subagent you spawn, so point each subagent at this file.

## 0. First run and setup

If `.setup/progress.json` doesn't exist (the repo isn't set up yet), or the user says "setup", "set up", "get started" or "setup <tool>", use the `setup` skill ([.claude/skills/setup/SKILL.md](.claude/skills/setup/SKILL.md)); it opens the setup window (the wizard in the Signal console) unless the user wants it in chat. If they say "tour", "how does this work" or "explain <tool>", use its guided tour. To change a tool's settings ("change the digest time", "use a different voice"), use the skill's `setup config` commands. Setup and the tour are run by the top-level agent directly; section 3's delegation rules apply to code changes, not to setup.

## 1. Coding rules

All code follows [refdocs/codingrules.md](refdocs/codingrules.md). Read it before writing or reviewing any code.

The short version: small single-purpose files, reuse before you write, many small packages, frequent comments, no crowded folders.

Also apply the `ponytail` skill ([.claude/skills/ponytail/SKILL.md](.claude/skills/ponytail/SKILL.md), at "full" level) to cut tokens and code you don't need. It isn't auto-injected into subagents, so read it yourself before coding. Where it conflicts with `refdocs/codingrules.md`, codingrules wins.

## 2. Outbound writing

Outbound writing (emails, messages, posts, documents written for other people) goes through the `copytone` skill ([.claude/skills/copytone/SKILL.md](.claude/skills/copytone/SKILL.md)) once you've added writing samples to it (`setup copytone`). Internal repo files are exempt.

## 3. Delegate every task, review every result

- **The top-level agent is an orchestrator.** It plans, splits work into tasks, spawns subagents, and relays results. It does not write code or docs itself, except handoff docs (section 4).
- **Every task goes to an implementer subagent.** Give it the goal, the relevant files, clear acceptance criteria, and a pointer to this file and `refdocs/codingrules.md`.
- **Every result gets reviewed by a fresh reviewer subagent.** Fresh means a new agent with no shared context: it starts with only the task description, the diff/output, and the rules, and may read the rest of the repo and run tests/build to verify. Never reuse the implementer as its own reviewer.
- **The reviewer's model must be equal to or higher than the implementer's.** Sonnet work is reviewed by Sonnet or Opus, never by Haiku. This means model tier (Haiku < Sonnet < Opus), not version number.
- **The reviewer checks:** correctness, acceptance criteria met, `refdocs/codingrules.md` compliance (use its checklist), and that tests/build pass. It returns either PASS or a list of concrete findings with file and line.
- **Findings loop back.** An implementer fixes them, then a *new* fresh reviewer reviews again. Repeat until PASS.
- **Subagents don't re-delegate.** Implementer and reviewer subagents do their task directly. They don't hand it to another subagent, and a review is not itself reviewed.
- **The orchestrator reports its tasks** for the console's Tasks page and the board's task grid: it runs `uv run --project tools/console --frozen --no-sync console tasks set <id> --name "..." --pct N --status building|review|needs_you|queued --next "..." [--you "..."]` from the repo root whenever it spawns a task, sends it to review, gets PASS or needs the owner (`needs_you` requires `--you`), and `console tasks done <id>` once it's committed. Hooks can't do this, since `SubagentStart` carries only an id and a type.
- **Only the orchestrator commits and pushes**, and only work that has passed review. Implementers and reviewers never commit. Handoff docs are the one exception and are committed without review.

## 4. Context management

When you (the orchestrator or any subagent) reach **<!-- setting:context-handoff-percent -->75<!-- /setting -->% of your context window**, stop starting new work and hand off. (`setup config agents` changes this number.) If you can't see an exact number, estimate conservatively and hand off early rather than late.

1. **Write a handoff doc** at `refdocs/handoffs/<YYYY-MM-DD-HHMM>-<task-slug>.md` using the template below.
2. **Save your state.**
   - *Orchestrator:* commit and push all reviewed, passing work, then commit and push the handoff doc as its own commit, so the successor starts from a clean state.
   - *Subagent:* don't commit. Leave your work in the working tree and list every changed file in the handoff doc.
3. **Spin up a successor agent** (same model or higher). Its first instruction: read `AGENTS.md`, then the handoff doc, then continue the task.
   - *Orchestrator:* you're the top-level session, so your successor must be a new top-level session. Tell the user the handoff doc's path and the line to start the new session with: `Read AGENTS.md, then <handoff doc path>, and continue.`
   - *Subagent:* make the handoff doc path your final output. The orchestrator spawns your successor right away, so results keep flowing back to the orchestrator.
4. **Terminate yourself.** End your turn and do no further work.

The successor deletes the handoff doc, and any earlier ones in the same chain, once the task is finished. Committed handoff docs stay in git history.

### Handoff doc template

```markdown
# Handoff: <task name>

**From:** <agent role / model>   **Date:** <YYYY-MM-DD HH:MM>

## Goal
What the task is and what "done" looks like.

## Done so far
What's finished, with file paths and commit hashes.

## In progress
What was mid-flight when you stopped, and its exact state.

## Next steps
Ordered list of what the successor should do next.

## Decisions and gotchas
Choices made and why, dead ends already tried, anything surprising.

## Key files
Paths the successor should read first.
```

## 5. Repo rules

- Remote is `origin`, default branch `main`.
- Commit small and often, one logical change per commit.
- **Push after every moderate or major update** (the orchestrator pushes; see section 3).
  - *Moderate:* a new feature or module, a behavior-changing bug fix, a refactor touching more than one file, a dependency or config change.
  - *Major:* a new package, an architecture change, or anything spanning multiple tasks.
  - *Minor* changes (typos, comment tweaks) can ride along with the next push.
- The orchestrator always pushes before a handoff (see section 4).
- Push only work that has passed review and has passing tests/build. Handoff docs are the one exception.
- Pull and rebase on `main` before pushing so you're never pushing onto stale history (skip this if `origin/main` doesn't exist yet).
- Commit messages: a short imperative summary line (under ~72 chars), then a body explaining *why*.
- Commit attribution (for example `Co-Authored-By` lines) follows the owner's Claude Code `attribution` setting.
- Never force-push `main`. Never commit secrets, `.env` files, build output, or large binaries.

## 6. Test what matters, not everything

Be thorough but quick. Tests and test runs cost time and tokens, so spend them where they catch real bugs. Test only critical and moderately critical behaviour. If a bug wouldn't cost data, money, safety or a broken main flow, don't test it.

- **Test the key things:** core logic, edge cases that would really bite, security boundaries, and anything that talks to hardware, networks or other processes (use fakes). Every bug fix gets one regression test.
- **Skip the trivial:** pass-through wrappers, simple glue, and things the type checker or linter already catch. No tests that just assert defaults or constants (a check that the example config matches the code defaults is fine if it guards real drift). No exhaustive permutation tests, and no five tests where one good one does the job.
- **Keep it small:** aim for about 3-6 tests per new module, and justify more. Several cases of one behaviour go in one `parametrize`, not separate functions. One test covers a whole fallback family, not one per tiny branch. Test the public API, not private helpers or message wording. Security-boundary tables (permission, bypass, redaction, path checks) are exempt from the count, but stay parametrized.
- **Trim as you go:** when you touch a module, merge or drop its redundant tests instead of adding more.
- **Run tests in a targeted way:** while working, run only the tests for what you changed. The implementer runs the full suite once before review, the reviewer re-runs only what it needs to verify, and the orchestrator runs it once before push.
- **Reviewers check both directions:** missing tests on key behavior is a finding. Excessive or redundant tests are also a finding and block PASS: name the specific tests to cut or merge (no general complaints), and the fix round trims them.

## 7. Owner context

An optional, gitignored knowledge base for the owner (responsibilities, weekly plans, an inbox) can live in `life/`; see [life/README.md](life/README.md). If it exists, read its README for context and keep it updated when you learn something relevant. Never commit anything under `life/`.
