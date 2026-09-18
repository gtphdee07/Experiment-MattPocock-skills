# Testing methodology

Five test categories, a regression-scoping rule that runs only the tests a
change could actually break, and a security-audit gate that runs before any
push touching security-sensitive code. Decided 2026-09-18, informed by
another project's testing framework (names and specifics reworked for this
repo — see `docs/adr/0012-dependency-graph-regression-scoping.md` for the one
piece that was a real trade-off, not just a naming choice).

## Test categories

Every module (file) gets two kinds of test at two granularities, plus one
category that exists specifically to catch what those two structurally
cannot see, plus two cross-cutting categories for interfaces between
modules and boundaries outside the codebase.

### 1. Unit tests (solitary)

One function, its real collaborators replaced with fakes. For each function,
cover:

- **The interface contract** — given valid inputs, does it accept/reject the
  shapes it's supposed to?
- **Correct operation** — does it do the thing it's for, across the
  meaningfully different cases, not just one happy path?
- **Expected errors** — do the failure modes it's *supposed* to raise
  actually get raised, and are they the right ones?

Example: `packages/towing-core/tests/test_models.py`'s `pytest.raises(ValueError)`
tests for each domain dataclass's `__post_init__` (expected errors — added
when issue #22 found the four dataclasses had no positivity floor at all,
letting a sign-typo'd weight silently flip a real overload into a false
PASS). `test_calculations.py`'s coverage of the six `check_*` overload
functions across distinct overload/no-overload/near-limit cases (correct
operation).

### 2. Interaction tests (sociable, within a module)

For functions in the *same file* that share implicit mutable state — not
just parameters and return values. This is the category unit tests
structurally cannot see, because a solitary test replaces the real
collaborator with a fake and never observes what actually happens between
two functions that both touch the same state. Drive the real sequence of
calls in the real order the system executes them (including reruns, where
that's how the real system behaves), and assert on the net shared-state
outcome.

**Current instance in this repo**: `apps/streamlit/streamlit_app.py`'s
wizard step functions, which all read and write `st.session_state` across
reruns with no explicit contract between them. **Not yet tested at this
level** — `apps/streamlit/tests/test_wizard_eval.py` only exercises
`evaluate_weigh_event` with canned inputs, never the actual session-state
sequence a real run through the wizard produces. This is the confirmed
backfill target for this category (tracked separately from writing this
document — see "Backfill" below).

Practical scope-limiter: don't test every function against every other
function in a file. Keep a short, explicit list of which functions in a
module actually share which piece of mutable state, and write interaction
tests only for the sequences the module's real control flow produces.

### 3. Surface tests

What the rest of the codebase actually calls into this file for — the
file's exported boundary, not its internals. Same three checks as unit
tests, applied at the public surface instead of one internal function.

Example: `apps/cli/tests/test_weigh_event_cli.py` drives `run_weigh_event`
end-to-end via a fake `read` and asserts on printed output via `capsys` —
this is the CLI's actual public entry point, not its internal collectors.
(The inverse gap this category can leave, if relied on alone: issue #29
found Solo Ticket linking's 6 internal functions had surface-test coverage
only, nothing unit-tested in isolation, until 14 direct tests were added.
Both categories are needed — neither substitutes for the other.)

### 4. Contract tests

When a change modifies the interface *between* two modules — a function
signature, a return shape, an HTTP request/response contract, a shared
config format — both modules' relevant tests run (via the regression-scoping
table below) plus a dedicated test asserting the contract itself, not just
that each side independently still passes its own tests.

**No live instance in this repo yet** — everything is Python today, and
`mypy --strict` across package boundaries already catches most signature/
shape drift for free (a real, honest difference from a multi-language
codebase, where no single type checker spans the boundary). That coverage
disappears the day Phase 3 (Android/Kotlin) starts consuming Phase 2's JSON
API — the exact shape of risk this category exists for. Defined here now,
before there's a live instance, so a future agent doesn't have to
rediscover the need the hard way.

### 5. External tests

Verifies a real third-party boundary (the Anthropic API; later, a real
Postgres instance) hasn't silently changed — nothing internal to this
codebase can prove a *provider's* behavior is still what it was. One
trigger only, diff-driven: a change touching boundary-calling code (today:
`packages/towing-app/towing_app/field_acquisition.py`'s Claude calls; later:
Postgres-calling code in `apps/backend`) means attempting the matching
`test_real_*` suite. If it can't run (no API credit, no reachable database),
the response has to explicitly record *why* rather than silently treating
the offline suite as sufficient — that distinction was skipped once already
in this project's own history (issue #27 touched Claude-calling code and
only the offline suite was confirmed; the credit-exhaustion skip was already
known, but wasn't tied explicitly to that specific diff).

There is deliberately **no calendar-based trigger** for this category. A
prior draft of this document considered one (to catch drift with zero code
change on our side, the way issue #23's unbound `streamlit` dependency was
found) — dropped once the security-audit gate's dependency-manifest
trigger (below) started covering the same class of risk on every relevant
diff, making a time-based backstop redundant with something now
enforced mechanically instead of remembered.

Existing instances: `test_real_photo_smoke.py`, `test_real_trailer_photo_smoke.py`,
`test_real_scale_ticket_photo_smoke.py` — all prefixed `test_real_*`,
excluded from the default `-k "not real"` gate, run only when explicitly
invoked and credentials/credit are available.

## Regression scoping

The full offline suite runs in under 3 seconds today (352 tests). Scoping
isn't solving a today problem — it's getting ahead of the point where
`apps/backend`, a promoted `apps/web`, and eventually Android make "just run
everything" slow enough to actually discourage running tests at all.

**Mechanism**: a hand-maintained file→member→dependents table, no new
tooling. When a change touches files under a given workspace member, run
that member's own tests plus every member that transitively depends on it:

| Changed member | Also run (dependents) |
|---|---|
| `packages/towing-core` | `packages/towing-app`, `apps/cli`, `apps/streamlit`, `apps/backend` |
| `packages/towing-app` | `apps/cli` |
| `apps/cli` | — |
| `apps/streamlit` | — |
| `apps/backend` | — |

A change to root-level shared config (`pyproject.toml`, `uv.lock`) touches
every member's build — run everything.

Keep this table in sync by hand whenever a workspace member's own
dependencies change (its own `pyproject.toml`'s `dependencies` list) — see
`docs/adr/0012-dependency-graph-regression-scoping.md` for why this is a
hand-maintained table rather than a tool that derives the graph
automatically.

**Two diff bases, two purposes**:
- **Working-tree / staged changes** — the fast local loop while actively
  iterating on one change. Run only the scoped members' tests.
- **Merge-base against `main`** — what a merge checks. The *full* suite
  (`uv run pytest -k "not real"` · `uv run mypy .` · `uv run ruff check .` ·
  `uv run ruff format --check .`) is still mandatory here, every time,
  regardless of scope — scoped testing is for local iteration, not a
  replacement for the pre-merge safety net. `mypy`/`ruff` are never
  scoped — both are whole-repo checks by nature (in particular, `mypy`
  benefits from whole-program analysis; a scoped run could miss a real
  cross-file type error the full run would catch).

## Security-audit gate

A real pre-push hook (`.claude/settings.json`'s `PreToolUse`/`Bash` hook,
filtered to `git push*`) checks the diff being pushed against these
patterns, and if any match, requires confirming before the push proceeds:

- Auth/session/password code: `apps/backend/**/auth*`, `**/*session*`,
  `**/*password*` (forward-looking — `apps/backend` doesn't exist yet, but
  the pattern is ready for when it does).
- Files reading secret keys: `field_acquisition.py` (reads
  `ANTHROPIC_API_KEY`) today; extend this list when a future DB connection
  string or payment-provider key reader is added — it's a hand-maintained
  list, same reasoning as the scoping table above.
- Dependency manifests: `pyproject.toml`, `uv.lock`, `package.json`,
  `package-lock.json`, `.env*` — issue #23's unbound `streamlit` dependency
  was a real vulnerability introduced entirely through a manifest edit, no
  auth code involved.

When triggered, run the `security-audit` skill in **guidance mode** (a
focused review of just the touched area — not the full six-phase audit)
against the matched files before confirming the push. Full audit mode is
reserved for whenever `apps/backend` gets its first real production
deploy, and for any change significant enough to be its own release event —
not for routine pushes.

No calendar cadence — see the "External tests" note above for why.

## Backfill

One concrete target from this document, tracked as a follow-up, not part of
writing this document itself: interaction tests (category 2) for the
Streamlit wizard's `st.session_state` sequence. Category 4 (contract tests)
has no backfill target — it's defined for when Phase 3 needs it, not
retrofitted against code that doesn't exist yet.
