# d0rbu — Personal Website + CLI Business Card

**Date:** 2026-05-17
**Status:** Approved (design phase complete)
**Owner:** Henry Castillo (@d0rbu)

## 1. Summary

`d0rbu` is a single GitHub repository containing a personal website and a CLI
"business card" for Henry Castillo, an ML / interpretability researcher. Both
surfaces present the same content — about, projects/research, résumé, contact,
and a link to a Substack — rendered for the browser and for the terminal
respectively. The CLI is published to **PyPI and npm under the name
`henry-castillo`**. A heavier, opt-in "lab" of torch/transformers experiments
is planned as a later phase and is explicitly out of scope for v1.

## 2. Goals / Non-goals

**Goals**

- One repository, one source of truth for content.
- A fast, simple, good-looking CLI that browses all site content offline.
- A clean static website deployed to GitHub Pages.
- Publishable to PyPI and npm, runnable with zero setup (`uvx`/`npx`).

**Non-goals (v1)**

- No blog engine — writing is just an external link to Substack.
- No backend/server, no auth, no analytics.
- No `lab` (torch/transformers) functionality in v1 — designed later, separate
  spec/plan.
- No custom domain in v1 (GitHub Pages default URL; custom domain can come
  later).

## 3. Naming & identity

- **GitHub repo:** `d0rbu`.
- **Distribution package (PyPI + npm):** `henry-castillo` (both confirmed
  available 2026-05-17).
- **Python import package:** `henry_castillo`.
- **Command aliases (all launch the same CLI):** `henry-castillo`, `d0rbu`,
  `d0rb`, `hc`, `henry`, `secret-string-lol`.

## 4. Architecture

Python monorepo, shared JSON content, lean CLI now / heavy lab later.

```
d0rbu/
├── content/                  # SINGLE SOURCE OF TRUTH (edit here only)
│   ├── profile.json          #   identity, about, contact, links, résumé
│   └── projects.json         #   list of projects/research
├── src/henry_castillo/
│   ├── __init__.py
│   ├── __main__.py           # CLI entrypoint: subcommands + interactive default
│   ├── content.py            # loads content/*.json bundled into the wheel
│   ├── render.py             # rich rendering of each section
│   ├── tui.py                # interactive default (rich + questionary loop)
│   └── lab/                  # OPTIONAL extra, LATER PHASE; lazy-imported
├── web/                      # Astro static site; reads ../content at build
├── packages/npm/             # thin npm wrapper shipping a frozen binary
├── .github/workflows/        # pages.yml · release-pypi.yml · release-npm.yml
├── pyproject.toml            # lean deps; [lab] optional-dependency group
├── .gitignore
└── README.md
```

**Content flow:** `content/*.json` is edited in exactly one place. It is
packaged into the Python wheel (so the CLI works fully offline) and read by
Astro at build time (so the site always matches the CLI). No duplication.

## 5. Content — single source of truth

Actual values are placeholders to be supplied during implementation; the
schema below is the contract both surfaces consume.

**`content/profile.json`**

```json
{
  "name": "Henry Castillo",
  "handle": "d0rbu",
  "tagline": "ML / interpretability researcher",
  "about": "Short bio paragraph(s).",
  "contact": { "email": "<email>" },
  "links": {
    "github": "https://github.com/d0rbu",
    "substack": "https://<sub>.substack.com",
    "other": []
  },
  "resume": {
    "pdf": "resume.pdf or URL",
    "experience": [
      { "org": "", "role": "", "period": "", "summary": "" }
    ],
    "education": [
      { "school": "", "degree": "", "period": "" }
    ],
    "highlights": []
  }
}
```

**`content/projects.json`**

```json
[
  { "name": "SAEBench", "blurb": "sparse autoencoder eval suite",
    "url": "https://github.com/d0rbu/SAEBench", "tags": ["interp"] }
]
```

## 6. CLI design

**Engine — decoupled by layer:**

- **Card (base, what everyone runs):** `rich` (rendering) + `questionary`
  (arrow-key menu). No async runtime, no CSS engine — instant startup, small
  frozen binary. Textual is **not** a base dependency.
- **Lab (later, opt-in):** may use Textual; it lives only in the `[lab]`
  optional-dependency group and never touches the base card path.

**Default run (`henry-castillo`, no args) → interactive card:**

- Identity banner (name · `@d0rbu` · tagline).
- Arrow-key menu over **About · Projects · Résumé · Contact · Substack**, with
  **Lab** shown locked until the `[lab]` extra is installed.
- Enter renders the chosen section as a `rich` panel; link-type entries
  (GitHub, Substack, résumé) open in the browser.
- `q` / `Esc` to quit.

**Direct subcommands (scriptable, fast):** `about`, `projects` (optional
`--tag`), `resume`, `contact`, `substack`, plus `--version` / `--help`.

**Résumé:** displayed everywhere as **"Résumé"** (with accents). The typed
subcommand is ASCII `resume` for terminal usability; the accented `résumé` is
also accepted. Stored structured in `content/` so it renders in the terminal
*and* on the site; `resume --open` opens the PDF/web version.

**Offline:** content is bundled into the wheel; the card never requires a
network connection. Link-opening obviously needs one.

**Lab gating:** the Lab menu item and `lab` subcommand attempt a lazy import;
if `torch`/`transformers` are absent they print an install hint
(`uvx --with 'henry-castillo[lab]' henry-castillo`) instead of crashing.

## 7. Website

**Direction: B — minimal / academic.** Light, typographic, whitespace-heavy
clean researcher homepage. Sections: hero (name + tagline), About,
Projects (clean list/cards from `projects.json`), Résumé (rendered + PDF
download), Contact, Substack link.

**Prominent CLI callout (first-class element):** a strong, visible section
promoting the CLI — copyable install commands (`uvx henry-castillo`,
`npx henry-castillo`) and links to the **PyPI** and **npm** package pages.
Not a footnote.

**Tech:** Astro, fully static. Reads `content/*.json` at build so it always
matches the CLI. Deployed to GitHub Pages via Actions on push to `main`.
Default Pages URL for v1; custom domain later if desired.

## 8. Lab — later phase (out of scope for v1)

`src/henry_castillo/lab/` holds full torch/transformers,
interpretability-style experiments. It is lazy-imported, gated behind
`pip install 'henry-castillo[lab]'`, never bundled into the lean card or the
npm binary, and gets its own spec + plan when built. Recorded here only so the
boundary (lazy import, optional-dependency group, graceful "not installed"
message) is designed in from the start.

## 9. Distribution & CI

- **PyPI `henry-castillo`** (primary): lean deps (`rich`, `questionary`).
  `uvx henry-castillo` / `pipx run henry-castillo`. `[lab]` extra adds
  `torch`, `transformers`, `textual`. All six command aliases declared as
  `[project.scripts]`.
- **npm `henry-castillo`:** thin wrapper shipping a per-platform frozen binary
  (PyInstaller) of the lean card; `bin` maps all six alias names;
  `npx henry-castillo` needs zero Python. Most complex piece — its own
  milestone.
- **GitHub Actions:**
  - `pages.yml` — build Astro + deploy Pages on push to `main`.
  - `release-pypi.yml` — on tag `v*`: build sdist + wheel, publish via PyPI
    Trusted Publishing (OIDC).
  - `release-npm.yml` — on tag `v*`: build frozen binaries
    (linux/macOS/Windows × arch matrix), assemble per-platform npm packages,
    publish.

## 10. Milestones / phasing

1. **Repo skeleton (the "just a README for now" deliverable):** create GitHub
   repo `d0rbu`, README, directory skeleton, content stubs, `pyproject.toml`
   scaffold, `.gitignore`; push to GitHub. *No functional code yet.*
2. **CLI v1:** content schema + loader, `rich`+`questionary` interactive card,
   direct subcommands; publish to PyPI as `henry-castillo`.
3. **Website:** Astro site (Direction B + prominent CLI callout) reading
   `content/`; deploy to GitHub Pages.
4. **npm distribution:** frozen-binary build matrix + thin npm wrapper;
   publish npm `henry-castillo`.
5. **Lab (later, separate spec/plan):** `[lab]` torch/transformers
   experiments.

## 11. Risks & open questions

- **npm frozen-binary packaging** (PyInstaller × per-platform × npm
  `optionalDependencies`) is the highest-risk/most-finicky milestone; it is
  isolated to milestone 4 so it cannot block the website or PyPI release.
- **PyPI Trusted Publishing** must be configured on PyPI for the project
  before the first automated release.
- **macOS binary signing/notarization** is intentionally skipped in v1
  (unsigned binary; revisit if Gatekeeper friction matters).
- **Actual content values** (bio text, real project list, résumé entries,
  Substack URL, contact email, résumé PDF source) are required before the
  first public publish; collected during milestone 1–2.
- **Alias collisions:** `hc`/`henry` are short and could shadow other tools on
  a user's PATH — accepted as the owner's explicit choice.
