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
- **CLI** — `henry-castillo`: an interactive terminal card (About · Projects ·
  Résumé · Contact · Blog), plus direct subcommands. Built on `rich` +
  `questionary` for fast startup.
- **Shared content** — the CLI and the (future) site both consume a single
  hosted `card.json` at `https://d0rbu.github.io/d0rbu/data/card.json`, sourced
  from `web/data/card.json` in this repo. Edit that file and push to `main` —
  users get the update on their next run with no package release.

## The CLI

```bash
uvx henry-castillo                 # interactive card (About · Projects · Résumé · Contact · Blog)
henry-castillo about               # or jump straight to a section
henry-castillo projects --tag interp
henry-castillo resume --open       # open the résumé link
henry-castillo contact
henry-castillo blog
henry-castillo --version | --check-update | --update | --no-update-check
henry-castillo --debug             # or HENRY_CASTILLO_DEBUG=1
```

Content is fetched over HTTPS from GitHub Pages on first run, then cached
locally (so it keeps working offline after that). If no data is available at
all, the CLI shows a friendly guided failure screen. `HENRY_CASTILLO_CARD_URL`
overrides the source URL (useful for testing). On a non-interactive pipe it
prints the full card. Aliases: `henry-castillo`, `d0rbu`, `d0rb`, `hc`,
`henry`, `secret-string-lol` (also `python -m henry_castillo`).

## Repository layout

```
web/data/     card.json — single source of truth (deployed to GitHub Pages)
src/          henry_castillo Python package (the CLI)
web/          static site (Milestone 3)
packages/npm/ thin npm wrapper (Milestone 4)
```

## Roadmap

1. **Repo skeleton** — done.
1. **Dev infrastructure** — done (uv/ruff/ty/pytest, CI, release & deploy automation, auto-update, TS toolchain).
2. **CLI** — done (interactive card + subcommands; gated PyPI release — see CONTRIBUTING).
3. **Website** — static site, deployed to GitHub Pages.
4. **npm distribution** — thin wrapper shipping a frozen binary.
5. **Demos** *(later)* — opt-in torch/transformers experiments (`henry-castillo[lab]`).

## License

[MIT](LICENSE) © 2026 Henry Castillo
