# d0rbu — M2 Content Re-Architecture Design

**Status:** Approved 2026-05-19. Supersedes the content-loading portions of
`2026-05-17-d0rbu-design.md` §4/§5 (bundled/offline content). The interactive
card, subcommands, and preserved update-check contract remain as in M2.

## 1. Goal

Replace bundled, force-included `content/*.json` with a single **remotely
hosted, versioned `card.json`** that is the one source of truth for both the
CLI and the (future M3) website, editable without a package release. Load it
**once**, validate it **strictly** into **no-default** dataclasses, cache the
last good copy, and fail with a **guided, friendly screen** when there is no
usable data. Remove all defensive fallbacks/defaults.

## 2. Data contract — `card.json`

One JSON document, the shared contract for CLI + website:

```jsonc
{
  "schema_version": 1,                      // int; CLI supports a fixed major
  "profile": {
    "name": "Henry Castillo",
    "handle": "d0rbu",
    "tagline": "Interpretability and safety researcher",
    "about": "DRAFT — …",                   // draft text, but a valid string
    "email": "henryandrecastillo@gmail.com",
    "links": { "github": "https://github.com/d0rbu",
               "blog": "https://…"}          // blog optional-but-typed (see §3)
  },
  "projects": [
    { "name": "mc-dreamer", "blurb": "…", "url": "https://github.com/d0rbu/mc-dreamer", "tags": ["…"] },
    { "name": "nano-gpt-pretrain-steer", "blurb": "DRAFT — …",
      "url": "https://github.com/Algorithmic-Alignment-Lab/nano-gpt-pretrain-steer", "tags": ["…"] }
  ],
  "resume": { "pdf": "", "experience": [ … ], "education": [ … ], "highlights": [ … ] }
}
```

- **Canonical URL:** `https://d0rbu.github.io/d0rbu/data/card.json` (GitHub
  Pages, deployed by the existing `pages.yml`). Overridable via env
  `HENRY_CASTILLO_CARD_URL` (testing/smoke only).
- **Source of truth in-repo:** `web/data/card.json`. Edited & pushed by the
  maintainer; Pages redeploys; users see updates with **no package update**.
  The DRAFT placeholders are the maintainer's to fill post-deploy.
- The private project URL (`…/nano-gpt-pretrain-steer`) is included per
  explicit instruction; the maintainer can relabel/swap it by editing the
  hosted file at any time.

## 3. Strict typed model (no defaults, no fallbacks)

Frozen dataclasses, **every field required** (no `= ""`,
no `field(default_factory=…)`), built only by a single validating parser:

- `Resume(pdf: str, experience: list[dict], education: list[dict], highlights: list[str])`
- `Links(github: str, blog: str)` — `blog` is a required key in the artifact;
  an empty string `""` is the explicit "no blog yet" sentinel (the Blog tab
  then shows a "not configured" panel; nothing is opened).
- `Profile(name, handle, tagline, about, email, links: Links)`
- `Project(name, blurb, url, tags: list[str])`
- `Card(schema_version: int, profile: Profile, projects: list[Project], resume: Resume)`

`parse_card(data: object) -> Card` raises `CardError` (a single typed
exception with a human message naming the offending path) on: non-dict root;
missing/empty required string field (name/handle/tagline/about/email,
links.github); wrong types anywhere; `projects` not a non-empty list of valid
objects; `resume` missing required keys; `schema_version` absent/not the
supported major. Sanitization (§5) is applied to every string during parsing.
There is exactly one entry point: `load_card() -> Card` (fetch → cache →
parse) which raises `CardError` when no usable data exists.

## 4. Loading, caching, failure

`load_card()`:
1. Fetch the URL via stdlib `urllib` (HTTPS only, ~3 s timeout, ≤256 KiB body
   cap, `User-Agent: henry-castillo/<ver>`). The fetcher is an injected seam
   (`fetch: Callable[[str], bytes]`) like `tui.run`'s collaborators — unit
   tests inject; the real `_default_fetch` is integration/smoke tested against
   a real localhost HTTP server serving the real `card.json`.
2. On success: `parse_card` it; if valid, **atomically** write the raw bytes
   to the XDG cache (`$XDG_CACHE_HOME/henry-castillo/card.json`, mirroring
   `update.py`'s XDG logic) and return the `Card`.
3. On fetch failure OR invalid fetched body: read the cache; parse+validate
   it; return that `Card` (the CLI keeps working offline after first run).
4. If there is no usable data (fetch failed AND no/invalid cache): raise
   `CardError`. No bundled snapshot, no per-field defaults.

`__main__` catches `CardError` once at the top and invokes the §6 screen.

## 5. Sanitization (replaces `_CSI_RE`)

The regex is removed. Every string in the parsed `Card` is run through
`_sanitize(s)` = drop every Unicode category-`Cc` character except `\n` and
`\t`. This is provably complete (ESC `\x1b` is `Cc` → removed → no
ANSI/OSC/CSI sequence can survive because its introducer is gone) and
trivially testable: **exhaustive** over U+0000–U+00FF plus Hypothesis
properties ("no `Cc` except `\n`/`\t` ever survives"; "output never contains
`\x1b`/`\x9b`/`\x07`"; idempotent; returns `str`). Nested `experience`/
`education` strings are sanitized recursively during parsing.

## 6. No-usable-data UX

When `load_card()` raises `CardError`:

- **TTY** (interactive): print a friendly, descriptive panel — "Couldn't load
  profile data. Try `uvx --refresh henry-castillo`, or update the package;
  if it persists, contact henryandrecastillo@gmail.com." — then a **live
  countdown** ("Opening d0rbu.github.io in 5… 4… 3…  (press any key to exit)").
  If a key is pressed before 0 → exit cleanly (code 0). If the countdown
  reaches 0 → open `https://d0rbu.github.io/d0rbu/` in the browser and exit.
- **Non-TTY / pipe:** print the same message to **stderr**, no countdown, no
  browser, exit non-zero (code 1).
- Collaborators injected for testability: `wait_for_keypress(timeout) -> bool`
  (real impl: POSIX `termios` cbreak + `select`, covered for real via
  `os.openpty()` tests — zero pragmas), `open_url`, `console`, and a
  `sleep`/clock seam for the countdown so tests are instant & deterministic.

## 7. Logging — loguru

`loguru` becomes a **pinned runtime dependency** (exact `==`, ≥7 days old at
add time, per the supply-chain stance — `[project.dependencies]`). A small
`logging.py` module removes loguru's default sink at import; a stderr sink at
`DEBUG` is attached **only** when `HENRY_CASTILLO_DEBUG` is truthy or
`--debug` is passed. `logger.error(...)` is emitted for soft diagnostics
(e.g., a string that *would* be empty/was sanitized to empty where the schema
expects content) but such cases are still hard validation failures routed to
§6 — the log is for the maintainer/debugging, never user-facing noise.

## 8. CLI surface changes

- `Lab (locked)` menu entry → **`Demos (under construction)`**. When the
  preserved PyPI update-check (`update.py`, unchanged contract) reports a
  newer release, the Demos entry/panel shows a badge: "● a newer henry-castillo
  is available — new demos may be included (`henry-castillo --update`)".
- `Substack` → **`Blog`** everywhere: section title `Blog`, subcommand
  `blog` (no `substack`), `links.blog`, helper `blog_url(profile)`. Selecting
  Blog opens `links.blog` if set; if `links.blog == ""` → "Blog not configured
  yet" panel, nothing opened.
- `banner` no longer does `profile.name or "henry-castillo"` — `name` is a
  required validated field; emptiness is impossible past validation.
- Preserved verbatim: `--version/--check-update/--update/--no-update-check`,
  precedence, throttled TTY-only notice, `allow_abbrev=False`, the 6 aliases +
  `python -m` parity, conventional-commit/CI infra. `tui.run`'s injected-
  collaborator design and the rich-`Text`-everywhere rule remain.

## 9. Hosting / deploy

- `web/` minimal site so `pages.yml`'s guard (`web/package.json` or
  `web/index.html`) fires: `web/data/card.json` (source of truth),
  `web/index.html` (placeholder pointing at the CLI + a link to the JSON),
  `web/package.json` + a zero-dependency `build` (Node script staging
  `web/dist/` = `index.html` + `data/card.json`), `web/package-lock.json`
  (empty deps so `npm ci` works). `.npmrc ignore-scripts=true` consistent.
  M3 later replaces the placeholder but keeps emitting `dist/data/card.json`
  at the same path. `web/` is NOT linted by the `packages/npm` Biome job
  (different dir); it must pass the repo pre-commit hooks (json/eol/etc.).
- **Maintainer one-time action:** set repo Settings → Pages → Source =
  "GitHub Actions". Documented in `CONTRIBUTING.md` (alongside Trusted
  Publishing). NOT done by the agent. Pages deploys on push to `main` only
  (the maintainer's merge).

## 10. Removed

`content/profile.json`, `content/projects.json`, the `content/` dir, the
`pyproject.toml` `[tool.hatch…force-include]` content mappings, the M2
dual-path resolver / `_packaged_resource` / `_repo_content_file`, every
per-field default and "never raises → empty default" path, `_CSI_RE`. The M2
"fully offline, bundled" property is intentionally replaced by
"remote + cached + guided failure".

## 11. Testing strategy (maximum correctness)

- Unit: `parse_card` strict-validation matrix (every required field missing/
  wrong-type → `CardError` with the right path; valid → exact `Card`);
  fetch→cache→parse with injected fetcher (success, fetch-fail-with-cache,
  fetch-fail-no-cache, invalid-fetch-valid-cache, invalid-both); sanitization
  exhaustive + property; §6 screen TTY vs non-TTY, keypress-before-timeout vs
  timeout→open, with injected seams; loguru silent-by-default vs `--debug`;
  Blog/Demos behavior; update-badge wiring; no-default dataclasses reject
  partial construction.
- Property (Hypothesis, existing pinned dep): `parse_card` never accepts an
  invalid doc / never returns a `Card` with a control char or wrong type for
  ARBITRARY JSON; sanitize invariants; `blog_url` invariant.
- Real-impl coverage with zero pragmas: `_default_fetch` via a localhost
  `http.server` in a test; `_default_wait_for_keypress` via `os.openpty()`.
- Integration/smoke (real data + real API, run after the PR is pushed):
  build the wheel, install into a clean venv, serve the **real**
  `web/data/card.json` from a localhost server, point the CLI at it via
  `HENRY_CASTILLO_CARD_URL`, exercise every subcommand/alias/the interactive
  card/offline-cache/the #6 countdown (pty); hit the **real PyPI** JSON API
  for the Demos update badge. (No ML models are involved — `lab` is still a
  deferred stub; "models" N/A.) Symlink `web/data/` into the smoke workspace
  as needed.
- Gate unchanged: exactly 100% line+branch, zero `# pragma: no cover` in
  `src/`, ruff/ruff-format/ty/pre-commit/zizmor/dependency-age(/incl. the new
  pinned loguru)/`uv lock --locked`/`make check`, all 13 CI checks green,
  Python 3.10-safe.

## 12. Scope / delivery

Additional conventional commits on `milestone-2-cli` / **PR #3** (still
unmerged — keeps one cohesive reviewable unit; the maintainer reviews &
merges, never auto-merge). Subagent-driven per-task two-stage reviews +
corrective loops + a final whole-implementation review, then push and watch
all 13 CI checks green, then real-data/API smoke tests. This design spec is
committed; the implementation plan is kept untracked per the maintainer's
standing preference.
