# Dependency-graph regression scoping, not a test-impact tool

`TESTING.md`'s regression scoping (only run the tests a change could break) is implemented as a hand-maintained file→member→dependents table, not a tool that derives coverage automatically. The workspace graph is small (4-5 nodes) and changes rarely — adding a workspace member already means editing that member's own `pyproject.toml`, so updating one more table alongside it is a small ask. A derivation tool would be self-maintaining but is itself a new moving part to trust and debug; revisit if the graph grows enough that manual drift becomes a real risk.

## Considered Options

- **A coverage-tracking tool** (e.g. `pytest-testmon`), which reruns only the tests whose covered lines actually changed. Finer-grained than member-level scoping, but adds a dependency and a cache whose staleness has to be trusted rather than read.
- **No scoping at all** (run the full suite every time). Rejected per the same decision this ADR exists to record — the full suite is fast today, but that won't hold once `apps/backend`, a promoted `apps/web`, and Android exist.
