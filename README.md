# d0rbu

[![CI](https://github.com/d0rbu/d0rbu/actions/workflows/ci.yml/badge.svg)](https://github.com/d0rbu/d0rbu/actions/workflows/ci.yml)
[![CodeQL](https://github.com/d0rbu/d0rbu/actions/workflows/codeql.yml/badge.svg)](https://github.com/d0rbu/d0rbu/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)

Henry Castillo's personal website and CLI "business card".
One repository, one source of truth for content — rendered both as a static
website and as a terminal CLI published to PyPI and npm as `henry-castillo`.

## What this is

- **Website** — a clean, static personal site (deployed to GitHub Pages).
- **CLI** — `henry-castillo`: an interactive terminal card (about, projects,
  résumé, contact, Substack), plus direct subcommands. Built on `rich` +
  `questionary` for fast startup.
- **Shared content** — the site and the CLI both read `content/*.json`, so
  there is exactly one place to edit.

## The CLI

```bash
uvx henry-castillo                 # interactive card (About · Projects · Résumé · Contact · Substack)
henry-castillo about               # or jump straight to a section
henry-castillo projects --tag interp
henry-castillo resume --open       # open the résumé link
henry-castillo contact
henry-castillo substack
henry-castillo --version | --check-update | --update | --no-update-check
```

Runs fully offline (content is bundled). On a non-interactive pipe it prints
the full card. Aliases: `henry-castillo`, `d0rbu`, `d0rb`, `hc`, `henry`,
`secret-string-lol` (also `python -m henry_castillo`).

## Repository layout

```
content/      JSON single source of truth (profile, projects)
src/          henry_castillo Python package (the CLI)
web/          static site (Milestone 3)
packages/npm/ thin npm wrapper (Milestone 4)
docs/         design spec and implementation plans
```

## Roadmap

1. **Repo skeleton** — done.
1. **Dev infrastructure** — done (uv/ruff/ty/pytest, CI, release & deploy automation, auto-update, TS toolchain).
2. **CLI** — done (interactive card + subcommands; gated PyPI release — see CONTRIBUTING).
3. **Website** — static site, deployed to GitHub Pages.
4. **npm distribution** — thin wrapper shipping a frozen binary.
5. **Lab** *(later)* — opt-in torch/transformers experiments (`henry-castillo[lab]`).

Design details: [`docs/superpowers/specs/2026-05-17-d0rbu-design.md`](docs/superpowers/specs/2026-05-17-d0rbu-design.md).

## License

[MIT](LICENSE) © 2026 Henry Castillo
