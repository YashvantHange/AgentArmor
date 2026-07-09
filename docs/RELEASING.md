# Releasing AgentArmor

Releases are cut by pushing a `v*` tag. The [release workflow](../.github/workflows/release.yml)
then builds the Windows installer, creates the GitHub release with assets, and
publishes the wheel to PyPI.

## One-time setup: PyPI publishing (API token)

The `pypi` job publishes with an **API token**. Add it once:

1. On [pypi.org](https://pypi.org): **Account settings → API tokens → Add API token**.
   Scope it to the `agentarmor` project (create the project first by uploading a
   wheel manually if it does not exist yet).
2. Copy the token (starts with `pypi-...`).
3. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Name it exactly **`PYPI_API_TOKEN`** and paste the token.

Until this secret is set the `pypi` job fails, but it is `continue-on-error`, so
the Windows installer release still succeeds. After adding the secret you can
re-run the failed `pypi` job on the most recent release run to publish that
version.

## Cutting a release

Version strings must stay in sync across:

- `pyproject.toml` (`version`)
- `gui/package.json` (`version`)
- `gui/src-tauri/tauri.conf.json` (`version`)
- `gui/src-tauri/Cargo.toml` (`version`)
- `README.md` (version badge, "Latest release" link, installer filename)
- `CHANGELOG.md` (new dated section)

Then:

```bash
git commit -am "Release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "AgentArmor vX.Y.Z — ..."
git push origin vX.Y.Z
```

Pushing the tag triggers the full pipeline. No pull request is required for a
release.
