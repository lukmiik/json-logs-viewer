# Releasing

Builds and publishing use uv. Both indexes are already configured in
`pyproject.toml` (`[[tool.uv.index]]` named `testpypi` and `pypi`).

Current state: versions up to 0.2.0 have been published to TestPyPI only.
The package is not on PyPI yet.

## Steps

1. Bump `project.version` in `pyproject.toml` (SemVer).
2. Run the checks:
   ```bash
   uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
   ```
3. Build and validate:
   ```bash
   uv build
   uv tool run twine check dist/*
   ```
4. Publish to TestPyPI with a TestPyPI API token. `read -s` (zsh syntax)
   asks for it without echoing it or saving it in the shell history:
   ```bash
   read -s "UV_PUBLISH_TOKEN?TestPyPI token: " && export UV_PUBLISH_TOKEN \
     && uv publish --index testpypi dist/json_logs_viewer-X.Y.Z*; \
     unset UV_PUBLISH_TOKEN
   ```
5. Verify the install:
   ```bash
   uv tool install --index-url https://test.pypi.org/simple \
     --extra-index-url https://pypi.org/simple json-logs-viewer
   jlv --help
   ```
   A fresh install resolves the newest dependencies, not `uv.lock`'s, so
   run the tests against it too (pytest, pytest-asyncio,
   pytest-textual-snapshot and textual-serve installed beside it).
6. Publish to PyPI the same way with a PyPI token and `--index pypi`.
7. Tag the release: `git tag vX.Y.Z`.

`uv publish` uploads every file in `dist/`, and the index rejects versions it
already has. Clear `dist/` or pass the specific files.

## Before the first PyPI release

- Add `project.urls` (repository, issues) once a public remote exists.
- Textual 8 renders two greys in the command palette slightly lighter, so
  `test_command_palette` fails against it while `uv.lock` pins 7.5:
  upgrade the lock (`uv lock --upgrade`) and refresh that snapshot.
