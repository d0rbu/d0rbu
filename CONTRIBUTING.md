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
  `build:`, `docs:`, `test:`, `refactor:`). PR titles are linted too.
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

## One-time PyPI Trusted Publishing setup (maintainer)

Before the first real publish, create the project on PyPI and add a Trusted
Publisher: PyPI → project → Publishing → add GitHub publisher with
owner `d0rbu`, repo `d0rbu`, workflow `release.yml`, environment `pypi`.
Until then, use `workflow_dispatch` with `dry_run=true` to rehearse.
