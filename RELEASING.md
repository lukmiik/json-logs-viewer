# Releasing

Builds and publishing use uv. Both indexes are already configured in
`pyproject.toml` (`[[tool.uv.index]]` named `testpypi` and `pypi`).

Current state: versions up to 0.1.4 have been published to TestPyPI only.
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
4. Publish to TestPyPI with a TestPyPI API token:
   ```bash
   UV_PUBLISH_TOKEN=<testpypi-token> uv publish --index testpypi
   ```
5. Verify the install:
   ```bash
   uv tool install --index-url https://test.pypi.org/simple \
     --extra-index-url https://pypi.org/simple json-logs-viewer
   jlv --help
   ```
6. Publish to PyPI with a PyPI token:
   ```bash
   UV_PUBLISH_TOKEN=<pypi-token> uv publish --index pypi
   ```
7. Tag the release: `git tag vX.Y.Z`.

`uv publish` uploads every file in `dist/`, and the index rejects versions it
already has. Clear `dist/` or pass the specific files.

## Before the first PyPI release

- Add `project.urls` (repository, issues) once a public remote exists.
- Update the Installation section of README.md to `uv tool install
  json-logs-viewer` (and `'json-logs-viewer[serve]'` for `--serve`).
