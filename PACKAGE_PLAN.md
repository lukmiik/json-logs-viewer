# Packaging Plan (TestPyPI and PyPI)

This plan uses uv for building and publishing.

## 1) Prep the project metadata
- Confirm `pyproject.toml` has a clear description, keywords, and `readme = "README.md"`.
- Ensure `project.urls` includes repository and issues links.
- Decide license and add a `LICENSE` file; reference it in `pyproject.toml`.
- Ensure the console entrypoint exists: `json-logs-viewer = "json_logs_viewer:main"`.

## 2) Build artifacts
- Produce sdist and wheel:
```bash
uv build
```
- Validate artifacts:
```bash
uv run python -m pip install --upgrade twine
uv run twine check dist/*
```

## 3) Configure TestPyPI and PyPI credentials
- Create accounts and API tokens for TestPyPI and PyPI.
- Export tokens for publishing (recommended):
```bash
export UV_PUBLISH_TOKEN="<token>"
```
- Alternatively set in CI secrets.

## 4) Publish to TestPyPI
- Add TestPyPI index config to `pyproject.toml`:
```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple"
publish-url = "https://test.pypi.org/legacy/"
```
- Publish:
```bash
uv publish --index testpypi
```
- Verify install from TestPyPI:
```bash
uv run python -m pip install -i https://test.pypi.org/simple --extra-index-url https://pypi.org/simple json-logs-viewer
```

## 5) Publish to PyPI
- Add PyPI index config to `pyproject.toml` (optional if using default):
```toml
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple"
publish-url = "https://upload.pypi.org/legacy/"
```
- Publish:
```bash
uv publish --index pypi
```

## 6) (Optional) Trusted Publishing via GitHub Actions
- Create a release workflow that builds and publishes using `uv publish --trusted-publishing always`.
- Configure OIDC trusted publishing on PyPI/TestPyPI.

## 7) Versioning and release process
- Use SemVer and bump `project.version` in `pyproject.toml` for releases.
- Tag releases (`vX.Y.Z`) to align with published versions.
