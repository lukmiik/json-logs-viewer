# Releasing

Releases go to PyPI from GitHub Actions with
[trusted publishing](https://docs.pypi.org/trusted-publishers/): PyPI
trusts `.github/workflows/release.yml` in this repository, so no API token
is stored anywhere.

## Steps

1. Bump `project.version` in `pyproject.toml` (SemVer), run `uv lock`, and
   commit.
2. Push `main` and wait for CI to pass.
3. Tag the commit and push the tag:
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```
4. The `release` workflow runs the CI checks, checks that the tag matches
   the version, builds, and runs `twine check`. The publish job then waits
   in the `pypi` environment: approve it in the run's page on GitHub.
5. Check the release installs:
   ```bash
   uv tool install --reinstall json-logs-viewer && jlv --help
   ```
   A fresh install resolves the newest dependencies, not `uv.lock`'s, so
   run the tests against it too (pytest, pytest-asyncio,
   pytest-textual-snapshot and textual-serve installed beside it).

PyPI never accepts the same version twice: a failed or wrong release needs
a new version number.

## Setup (done once)

- PyPI: a trusted publisher for project `json-logs-viewer`, owner
  `lukmiik`, repository `json-logs-viewer`, workflow `release.yml`,
  environment `pypi`.
- GitHub: an environment named `pypi` with a required reviewer, so every
  release waits for approval.

## TestPyPI (optional dry run)

Versions up to 0.2.0 were published to TestPyPI by hand. To try a build
there first, with a TestPyPI API token (`read -s` is zsh syntax: it asks
without echoing or saving the token to the shell history):

```bash
uv build
read -s "UV_PUBLISH_TOKEN?TestPyPI token: " && export UV_PUBLISH_TOKEN \
  && uv publish --index testpypi dist/json_logs_viewer-X.Y.Z*; \
  unset UV_PUBLISH_TOKEN
uv tool install --index-url https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple json-logs-viewer
```
