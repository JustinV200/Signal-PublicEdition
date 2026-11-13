# Coding Rules

Every agent that writes or reviews code in this repo follows these rules. Reviewers reject work that breaks them. If a rule truly doesn't fit a case, say why in a code comment and in your result report. The orchestrator carries it into the commit message.

## 1. Small files, small functions

- One file, one responsibility. If describing the file needs the word "and", split it.
- Aim for under 200 lines per file. Past 300 lines, split the file before adding anything else.
- Functions do one thing and stay under ~40 lines.
- Max 3 levels of nesting. Use early returns or extract a helper instead of going deeper.
- Max ~4 parameters. Beyond that, pass an options object / struct.

## 2. Reuse before you write

- Search the codebase for an existing helper before writing a new one.
- If the same logic shows up twice, extract it into a shared module. No copy-paste.
- Write functions so they can be reused: inputs come in as parameters, no hidden global state, return values instead of mutating arguments.
- Shared code lives in a shared package (e.g. `shared/`, `common/`, `core/`), not buried inside one feature's folder.
- Extract on real reuse, not imagined future reuse. Don't build abstractions nobody calls yet.

## 3. Many packages, clear boundaries

- Split the code into many small packages/modules by feature or domain, each with a single purpose.
- Each package exposes a small public API through one entry point (`index.ts`, `__init__.py`, `mod.rs`, etc.). Other packages import from that entry point only and never reach into its internals.
- Dependencies point one way: features depend on shared/core code, never the reverse. No circular imports.
- Each package has a short `README.md` covering what it does, its public API, and what it depends on.

## 4. Folder hygiene

- No more than ~10 source files in one folder. When a folder passes that, group the files into subfolders by concern.
- Keep nesting reasonable: no more than ~5 levels below the source root.
- Folder names say what's inside. No `misc/`, `stuff/`, `temp/`, `new/`. A `utils/` folder is fine only if it's split by topic (`utils/strings/`, `utils/dates/`).
- Tests mirror the source structure so a file's tests are easy to find.

## 5. Comments

- Every source file starts with a header comment: what the file is for and where it fits in the system.
- Every public function, class, and method gets a doc comment: purpose, parameters, return value, and errors it can throw.
- Comment non-obvious logic inline, especially the *why*: business rules, workarounds, edge cases, performance tricks.
- Update comments in the same change as the code they describe. A stale comment is a bug.
- Known gaps get a `TODO:` with enough context for someone else to act on it.
- No commented-out code. Delete it; git remembers.

## 6. Naming

- Descriptive names over short ones: `retryDelayMs`, not `rd`.
- Functions are verbs (`loadConfig`), booleans read as yes/no questions (`isReady`, `hasAccess`), collections are plural (`users`).
- Follow the language's casing conventions and stay consistent across the repo.
- No magic numbers or strings. Name them as constants; keep tunable values in config files.

## 7. Errors and safety

- Handle an error where you can actually do something about it. Otherwise let it propagate with added context.
- Never swallow an error silently.
- Validate input at the boundaries: user input, network responses, files, environment variables.
- Secrets come from environment variables or a secrets manager, never from source code.
- Local servers (TCP, HTTP, WebSocket) bind to 127.0.0.1 only and require a per-user random token, which they write to a gitignored state file and check with a constant-time compare. Any web page can reach localhost, so close the connection on the first malformed or unauthenticated request.

## 8. Testing

- Test key behavior: core logic, real edge cases, security boundaries, and integrations that could break. Trivial code (pass-throughs, constants, simple glue) doesn't need its own test. See AGENTS.md section 6.
- Every bug fix ships with a test that would have caught the bug.
- Tests are small, independent of each other, and named for the behavior they check.
- All tests pass before review and before push.

## 9. Style and tooling

- Use the formatter and linter configured for the language. Code is lint-clean before review.
- Use static types where the language supports them (TypeScript over plain JS, type hints in Python).
- Prefer the standard library. Every new dependency needs a reason stated in your result report (the orchestrator carries it into the commit message), and versions are pinned.
- No dead code, unused imports, or leftover debug prints.

## Reviewer checklist

- [ ] Each changed file has one responsibility and is under 300 lines
- [ ] No duplicated logic; existing helpers were reused where they exist
- [ ] Package boundaries respected: imports go through entry points, no circular deps
- [ ] No folder over 10 source files
- [ ] Header comment on every source file, doc comments on public APIs, inline comments on non-obvious logic
- [ ] Clear names, no magic values
- [ ] Errors handled or propagated, never swallowed; inputs validated at boundaries
- [ ] Key behavior tested (not everything), and tests passing
- [ ] Lint-clean, no dead code
