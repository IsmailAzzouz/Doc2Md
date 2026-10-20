# Releasing (maintainers)

1. Merge a reviewed PR after CI passes. Check [LIMITATIONS.md](LIMITATIONS.md).
2. Update `project.version` in `pyproject.toml` and `CHANGELOG.md` in a PR.
3. Ensure CI is green on `main` and the version has not been used already.
4. Tag the **tested commit** as `vX.Y.Z` and push the tag:
   ```bash
   git tag -a v0.1.0 -m 'Release v0.1.0'
   git push origin v0.1.0
   ```
5. The single release job runs in a `python:3.11-alpine` container. It verifies
   that the tag matches the package version, runs tests, builds wheel/sdist,
   checks metadata and publishes a GitHub Release using GitHub CLI.
   Inspect the run and published release.
6. If any job fails, fix the issue on a new commit and use a **new** tag; avoid
   moving or force-pushing published tags.

**Important:** A merged PR does not itself publish a release. The tag is a
separate intentional maintainer action. PyPI publishing is **not** configured.
Configure GitHub Releases permissions (`contents: write`) and release settings
before the first tagged release. Do not put PyPI API tokens in this repository.
