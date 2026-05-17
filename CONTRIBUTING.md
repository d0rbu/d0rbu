# Contributing

## Setup

```bash
make setup     # uv venv + dev deps + pre-commit hooks
```

## Day-to-day

```bash
make check     # lint + typecheck + test + format-check (the CI gate)
make test      # tests with coverage (≥90% enforced)
make precommit # run all pre-commit hooks
```

## Conventions

- **Conventional Commits** are enforced (`feat:`, `fix:`, `chore:`, `ci:`,
  `build:`, `docs:`, `test:`, `perf:`, `refactor:`). PR titles are linted too.
- `uv.lock` is committed; if you change dependencies run `uv lock` and commit
  it. CI verifies it with `uv lock --locked`.
- Code must pass `ruff` (lint + format) and `ty` (typing). New behavior needs
  tests; coverage is gated at 90%.

## Releasing

Maintainers: bump `__version__` in `src/henry_castillo/__init__.py`, update
nothing else (the changelog is generated), then:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

The release workflow builds, generates the changelog, publishes to PyPI via
Trusted Publishing, and creates a GitHub Release with an SBOM. Use the
workflow's `workflow_dispatch` with `dry_run=true` to rehearse without
publishing.

The only supported real-release path is pushing a `vX.Y.Z` tag (which builds,
publishes to PyPI, and creates a GitHub Release with the changelog + SBOM).
`workflow_dispatch` with `dry_run=false` publishes to PyPI **without** creating
a GitHub Release — use it only for exceptional manual recovery, not as the
normal release path.

## One-time PyPI Trusted Publishing setup (maintainer)

Before the first real publish, create the project on PyPI and add a Trusted
Publisher: PyPI → project → Publishing → add GitHub publisher with
owner `d0rbu`, repo `d0rbu`, workflow `release.yml`, environment `pypi`.
Until then, use `workflow_dispatch` with `dry_run=true` to rehearse.

### Action pinning policy

The PyPI publish action (`pypa/gh-action-pypi-publish`) is pinned to a full
commit SHA (with a `# vX.Y.Z` comment so Dependabot still bumps it) because it
receives the OIDC publish token. All other GitHub Actions are tag-pinned and
kept current by Dependabot (`github-actions` ecosystem); `zizmor`'s
`unpinned-uses` policy enforces at least ref-pinning repo-wide.
