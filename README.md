# d0rbu

Henry Castillo's personal website and CLI "business card".
One repository, one source of truth for content — rendered both as a static
website and as a terminal CLI published to PyPI and npm as `henry-castillo`.

> **Status:** scaffold (Milestone 1). The CLI, website, and packaging land in
> subsequent milestones — see the design spec and roadmap below.

## What this is

- **Website** — a clean, static personal site (deployed to GitHub Pages).
- **CLI** — `henry-castillo`: an interactive terminal card (about, projects,
  résumé, contact, Substack), plus direct subcommands. Built on `rich` +
  `questionary` for fast startup.
- **Shared content** — the site and the CLI both read `content/*.json`, so
  there is exactly one place to edit.

## Try it (coming soon — not yet published)

```bash
uvx henry-castillo     # Python / PyPI
npx henry-castillo     # Node / npm
```

Aliases that will all launch the same CLI: `henry-castillo`, `d0rbu`, `d0rb`,
`hc`, `henry`, `secret-string-lol`.

## Repository layout

```
content/      JSON single source of truth (profile, projects)
src/          henry_castillo Python package (the CLI)
web/          static site (Milestone 3)
packages/npm/ thin npm wrapper (Milestone 4)
docs/         design spec and implementation plans
```

## Roadmap

1. **Repo skeleton** — this milestone.
2. **CLI** — interactive card + subcommands, published to PyPI.
3. **Website** — static site, deployed to GitHub Pages.
4. **npm distribution** — thin wrapper shipping a frozen binary.
5. **Lab** *(later)* — opt-in torch/transformers experiments (`henry-castillo[lab]`).

Design details: [`docs/superpowers/specs/2026-05-17-d0rbu-design.md`](docs/superpowers/specs/2026-05-17-d0rbu-design.md).

## License

[MIT](LICENSE) © 2026 Henry Castillo
