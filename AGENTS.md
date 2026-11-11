# Commands

Use `uv` for everything (never bare `python`/`pip`).

- Run: `uv run jlv test_files/sample.jsonl`
- Lint + format: `uv run ruff check --fix . && uv run ruff format .`
- Types: `uv run ty check`
- Tests: `uv run pytest` (one file: `uv run pytest tests/unit/test_filter_engine.py`)
- Perf tests are excluded by default: `uv run pytest -m performance`
- Snapshots (SVG screenshots in `tests/snapshots/`): after an intended UI
  change run `uv run pytest tests/snapshots --snapshot-update` and look at
  the changed SVGs before committing them; a failing run writes
  `snapshot_report.html` with the diff.

Run lint, format, types and tests before calling a change done. CI runs
the same checks without fixing anything.

# Conventions

- New functions take keyword-only args (`def f(*, a: int) -> None`) and are
  called with keywords. Textual overrides/handlers (`compose`, `on_*`,
  `watch_*`, `action_*`) and the `filter_engine` classes are exempt.
- Type every function and non-obvious variable. Docstrings only where the code
  isn't self-explanatory; when present they use Google style (ruff `D`,
  `Args:`/`Returns:` sections optional).
- Line length is 79.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` ...).
- Screens pushed with `push_screen` go in `modals/`, widgets composed into the
  main screen go in `widgets/`.
- Test features through the app with Textual's `run_test()`/Pilot in
  `tests/integration/`; pure logic goes in `tests/unit/`.

# Gotchas

- App state lives in reactive lists on `LogViewerApp`. Replace them
  (`self.logs = [*self.logs, *new]`), never mutate in place, or watchers
  won't fire.
- In filter queries a space means AND (bare words are separate terms; quotes
  make a phrase), and dotted fields reach nested objects and lists.
- When behaviour or keybindings change, update `README.md`,
  `ARCHITECTURE.md` and the help text in `modals/help_modal.py`.
- `.notes/` holds the owner's gitignored notes: the work tracker
  (`tracker.html`) and known bugs (`analysis/`). Don't commit them.
