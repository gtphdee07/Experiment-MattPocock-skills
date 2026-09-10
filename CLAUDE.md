## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout (one `CONTEXT.md` + `docs/adr/` at the repo root). See `docs/agents/domain.md`.

## Working rules

### Verify before touching anything outside this repo, or before a multi-target delete

Before running a command that (a) deletes more than one file, or (b) writes or deletes anything at all outside this project directory, do a check-then-execute pass instead of running it straight:

- **Single literal, fully-named target, inside this project directory** — no extra step needed, run it directly.
- **Anything where a variable, glob, wildcard, `~`, or other home/environment-relative path resolves the target** — first run a non-destructive command that shows exactly what will be touched (e.g. `printf '%s\n' "$VAR"` for a variable, `printf '%s\n' pattern*` or `ls -d` for a glob, `echo ~/path` or `Resolve-Path ~/path` for a tilde). Read the output back and confirm it matches expectations — a blank result usually means a variable was unset. Only then run the real command, reusing the exact string/pattern just verified. `~` and `$HOME`/`Path.home()` count as expansion here: they resolve at runtime just like a variable, and this project has been bitten by exactly that ambiguity before (bash `$HOME` vs. Windows' real user profile).
- **Anything outside this project directory** — not exempt from the check just because it's a single named literal target. A path outside the repo has a much higher blast radius (it can hit real, non-recoverable data), so it gets the same check-then-execute treatment regardless of whether the path resolved cleanly. This applies to destructive **writes**, not just deletes.

Git operations (branch delete, worktree remove, etc.) are exempt — recoverable via reflog/remotes.

This rule needs to be restated explicitly by name when briefing a sub-agent for work likely to touch the filesystem outside its assigned worktree — inheriting it silently isn't reliable.

### Keep development activity off the app's real default data path

The app's default database lives at `~/.towing_app/garage.db` (via `resolve_db_path` in `apps/cli/towing_cli/cli.py`) — that's the correct, conventional location for the *shipped* CLI's real user data, and should not change. But every manual CLI invocation or smoke test run during development (by a human or an agent, directly via `towing-app ...`/`uv run ...`, not through pytest) must instead point at a project-local path, so development never touches real data:

```
export TOWING_APP_DB_PATH="$(pwd)/.dev-data/garage.db"   # bash
$env:TOWING_APP_DB_PATH = "$PWD\.dev-data\garage.db"     # PowerShell
```

`.dev-data/` is gitignored. After setting the override, echo it back before running the actual command to confirm it took effect — this is the general "verify before touching a resolved path" rule above, applied to this specific case; it's exactly the gap that let a piped command (`VAR=x cmd | othercmd`, where the export doesn't reach the second command) silently write a test profile into the real `~/.towing_app/garage.db` during a merge smoke test. Pytest-based tests are unaffected by this — they already isolate their own database path via fixtures, not this env var.
