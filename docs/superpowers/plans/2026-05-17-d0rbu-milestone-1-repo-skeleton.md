# d0rbu — Milestone 1: Repo Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `d0rbu` repository as a clean, valid scaffold (directory skeleton, content stubs, installable Python package shell, README, license) and publish it to GitHub.

**Architecture:** Python monorepo per `docs/superpowers/specs/2026-05-17-d0rbu-design.md`. This milestone produces *no functional features* — just a correct, installable, pushed skeleton that later milestones (CLI, website, npm, lab) build on. The one piece of real code is a minimal `henry-castillo` entrypoint stub so the package + all six console aliases are verifiably wired.

**Tech Stack:** Python ≥3.10, `hatchling` build backend, `uv` for env/install, `pytest` for the smoke test, `gh` CLI for GitHub.

**Repo state at start:** `/home/d0rb/Documents/Github/d0rbu` is already `git init`'d on branch `main`, with one commit containing `.gitignore` and the design spec. No GitHub remote yet. Work proceeds with `/home/d0rb/Documents/Github/d0rbu` as the working directory for every command.

**Conventions decided (call out to user if undesired):**
- GitHub repo visibility: **public** (it is a personal site + public npm/PyPI package).
- License: **MIT**, copyright "Henry Castillo", 2026.

---

## File Structure

| Path | Responsibility |
|---|---|
| `content/profile.json` | Identity/about/contact/links/résumé data stub (schema contract) |
| `content/projects.json` | Projects/research list stub |
| `src/henry_castillo/__init__.py` | Package marker + `__version__` (single source of version) |
| `src/henry_castillo/__main__.py` | Minimal CLI entrypoint stub (`main()`), wired to all 6 aliases |
| `src/henry_castillo/lab/__init__.py` | Empty placeholder for the later opt-in lab |
| `tests/test_smoke.py` | Verifies package imports, version, entrypoint runs |
| `pyproject.toml` | Package metadata, 6 console scripts, base/lab/dev deps, build backend |
| `LICENSE` | MIT license text |
| `README.md` | Project overview, structure, status/roadmap |
| `web/.gitkeep`, `packages/npm/.gitkeep`, `.github/workflows/.gitkeep` | Keep empty milestone-2+ dirs tracked |

---

## Task 1: Directory skeleton

**Files:**
- Create: `content/.gitkeep`, `web/.gitkeep`, `packages/npm/.gitkeep`, `.github/workflows/.gitkeep`, `tests/.gitkeep`, `src/henry_castillo/lab/__init__.py`

- [ ] **Step 1: Create the directory skeleton**

Run (from `/home/d0rb/Documents/Github/d0rbu`):

```bash
mkdir -p content web packages/npm .github/workflows tests src/henry_castillo/lab
touch content/.gitkeep web/.gitkeep packages/npm/.gitkeep .github/workflows/.gitkeep tests/.gitkeep
printf '"""Opt-in lab (torch/transformers experiments). Implemented in a later milestone."""\n' > src/henry_castillo/lab/__init__.py
```

- [ ] **Step 2: Verify the structure**

Run:

```bash
find content web packages .github tests src -type f | sort
```

Expected output (exactly these paths):

```
.github/workflows/.gitkeep
content/.gitkeep
packages/npm/.gitkeep
src/henry_castillo/lab/__init__.py
tests/.gitkeep
web/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add content web packages .github tests src
git commit -m "chore: scaffold monorepo directory skeleton"
```

---

## Task 2: Content stubs

**Files:**
- Create: `content/profile.json`
- Create: `content/projects.json`

- [ ] **Step 1: Write `content/profile.json`**

```json
{
  "name": "Henry Castillo",
  "handle": "d0rbu",
  "tagline": "ML / interpretability researcher",
  "about": "Replace with a short bio paragraph.",
  "contact": { "email": "you@example.com" },
  "links": {
    "github": "https://github.com/d0rbu",
    "substack": "https://example.substack.com",
    "other": []
  },
  "resume": {
    "pdf": "",
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

- [ ] **Step 2: Write `content/projects.json`**

```json
[
  {
    "name": "SAEBench",
    "blurb": "sparse autoencoder eval suite",
    "url": "https://github.com/d0rbu/SAEBench",
    "tags": ["interp"]
  }
]
```

- [ ] **Step 3: Verify both files are valid JSON**

Run:

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in sorted(glob.glob('content/*.json'))]; print('content JSON OK')"
```

Expected output:

```
content JSON OK
```

- [ ] **Step 4: Commit**

```bash
git add content/profile.json content/projects.json
git commit -m "feat(content): add profile and projects JSON stubs"
```

---

## Task 3: pyproject.toml and LICENSE

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "henry-castillo"
dynamic = ["version"]
description = "Henry Castillo's personal website + CLI business card."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Henry Castillo" }]
keywords = ["cli", "business-card", "personal-website"]
classifiers = [
  "Programming Language :: Python :: 3",
  "License :: OSI Approved :: MIT License",
  "Environment :: Console",
]
dependencies = [
  "rich>=13",
  "questionary>=2",
]

[project.optional-dependencies]
lab = ["torch", "transformers", "textual"]
dev = ["pytest>=8"]

[project.urls]
Homepage = "https://github.com/d0rbu/d0rbu"
Repository = "https://github.com/d0rbu/d0rbu"

[project.scripts]
henry-castillo = "henry_castillo.__main__:main"
d0rbu = "henry_castillo.__main__:main"
d0rb = "henry_castillo.__main__:main"
hc = "henry_castillo.__main__:main"
henry = "henry_castillo.__main__:main"
secret-string-lol = "henry_castillo.__main__:main"

[tool.hatch.version]
path = "src/henry_castillo/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/henry_castillo"]
```

- [ ] **Step 2: Write `LICENSE` (MIT)**

```text
MIT License

Copyright (c) 2026 Henry Castillo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Commit**

(Validity of `pyproject.toml` is verified by the editable install in Task 4 — `uv` fails loudly on a malformed file. Note: hatchling's `readme = "README.md"` means the editable install in Task 4 **does** require `README.md` to exist; Task 4 therefore creates a throwaway stub `README.md` to unblock the install, and Task 5 replaces it with the real content and commits it. `uv.lock` generated by the install is gitignored.)

```bash
git add pyproject.toml LICENSE
git commit -m "build: add pyproject scaffold (6 aliases, deps) and MIT license"
```

---

## Task 4: Minimal package + smoke test (TDD)

**Files:**
- Test: `tests/test_smoke.py`
- Create: `src/henry_castillo/__init__.py`
- Create: `src/henry_castillo/__main__.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_smoke.py`:

```python
import subprocess

import henry_castillo
from henry_castillo.__main__ import main


def test_version_is_nonempty_string():
    assert isinstance(henry_castillo.__version__, str)
    assert henry_castillo.__version__


def test_main_returns_zero_and_prints_name(capsys):
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_console_entrypoint_runs():
    result = subprocess.run(
        ["henry-castillo"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "henry-castillo" in result.stdout


def test_alias_entrypoint_runs():
    result = subprocess.run(["d0rbu"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "henry-castillo" in result.stdout
```

- [ ] **Step 2: Create the env and run the test to verify it fails**

Run:

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
```

Expected: collection/`ModuleNotFoundError` failure — `henry_castillo` has no `__init__.py`/`__main__.py` yet (tests error out, 0 passed). This confirms the tests are exercising real wiring.

- [ ] **Step 3: Write `src/henry_castillo/__init__.py`**

```python
"""henry-castillo — personal website + CLI business card."""

__version__ = "0.0.0"
```

- [ ] **Step 4: Write `src/henry_castillo/__main__.py`**

```python
"""Minimal CLI entrypoint stub.

Real functionality (interactive card + subcommands) arrives in Milestone 2.
This stub exists so the package and all six console aliases are verifiably
wired by Milestone 1.
"""

import sys

from henry_castillo import __version__


def main(argv: list[str] | None = None) -> int:
    """Print a friendly placeholder and exit 0."""
    if argv is None:
        argv = sys.argv[1:]
    print(f"henry-castillo {__version__}")
    print("Personal website + CLI business card — scaffold.")
    print("CLI features land in a later release.")
    print("Repo: https://github.com/d0rbu/d0rbu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Reinstall (new console scripts) and run the tests to verify they pass**

Run:

```bash
uv pip install -e ".[dev]"
uv run pytest -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_smoke.py src/henry_castillo/__init__.py src/henry_castillo/__main__.py
git commit -m "feat: minimal henry-castillo entrypoint stub + smoke tests"
```

---

## Task 5: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
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
````

- [ ] **Step 2: Verify the referenced files exist (no broken relative links)**

Run:

```bash
test -f docs/superpowers/specs/2026-05-17-d0rbu-design.md && test -f LICENSE && echo "README links OK"
```

Expected output:

```
README links OK
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add project README"
```

---

## Task 6: Create the GitHub repo and push

**Files:** none (remote/publish operation)

- [ ] **Step 1: Confirm clean state and `gh` auth**

Run:

```bash
git status --porcelain && echo "--" && git log --oneline && gh auth status
```

Expected: no uncommitted changes (empty before `--`), a list of commits, and `gh` logged in as `d0rbu` with SSH configured.

- [ ] **Step 2: Create the GitHub repo from the local repo and push**

Run:

```bash
gh repo create d0rbu \
  --public \
  --source=. \
  --remote=origin \
  --description "Henry Castillo's personal website + CLI business card (henry-castillo)" \
  --push
```

Expected: repo created at `https://github.com/d0rbu/d0rbu`, `origin` added, `main` pushed.

If this `gh` version rejects `--source/--push` (older CLI), fall back to:

```bash
gh repo create d0rbu --public --description "Henry Castillo's personal website + CLI business card (henry-castillo)"
git remote add origin git@github.com:d0rbu/d0rbu.git
git push -u origin main
```

- [ ] **Step 3: Verify the push landed**

Run:

```bash
git remote -v && git ls-remote --heads origin main && gh repo view d0rbu --json name,visibility,url
```

Expected: `origin` points at `git@github.com:d0rbu/d0rbu.git`; a `refs/heads/main` hash is listed; JSON shows `"name":"d0rbu"`, `"visibility":"PUBLIC"`, the URL.

- [ ] **Step 4: Final sanity check of the published tree**

Run:

```bash
git ls-files | sort
```

Expected (note `.superpowers/` is correctly absent — it is gitignored):

```
.github/workflows/.gitkeep
.gitignore
LICENSE
README.md
content/.gitkeep
content/profile.json
content/projects.json
docs/superpowers/plans/2026-05-17-d0rbu-milestone-1-repo-skeleton.md
docs/superpowers/specs/2026-05-17-d0rbu-design.md
packages/npm/.gitkeep
pyproject.toml
src/henry_castillo/__init__.py
src/henry_castillo/__main__.py
src/henry_castillo/lab/__init__.py
tests/.gitkeep
tests/test_smoke.py
web/.gitkeep
```

(If this plan file was committed after Task 5, it will appear in the list as shown — that is expected and fine.)

---

## Self-Review

**1. Spec coverage (Milestone 1 scope only):** Spec §10 milestone 1 = "create GitHub repo `d0rbu`, README, directory skeleton, content stubs, `pyproject.toml` scaffold, `.gitignore`; push to GitHub. No functional code yet." → directory skeleton (Task 1), content stubs (Task 2), pyproject scaffold + license (Task 3), minimal stub + smoke test (Task 4, the only code, intentionally non-functional), README (Task 5), GitHub repo + push (Task 6). `.gitignore` already committed pre-plan. Spec §3 naming (package `henry-castillo`, import `henry_castillo`, 6 aliases) → Task 3 `[project.scripts]` + Task 4 alias test. Milestones 2–5 are explicitly out of scope for this plan and each gets its own plan later. No gaps for Milestone 1.

**2. Placeholder scan:** No "TBD/TODO/handle edge cases" instructions. Content JSON contains intentional placeholder *data values* (e.g., `you@example.com`) — that is the spec-sanctioned content stub, not a plan placeholder; every step has concrete commands/code/expected output.

**3. Type consistency:** `__version__` defined in `src/henry_castillo/__init__.py` (Task 4 Step 3), read by `[tool.hatch.version]` (Task 3) and `__main__.py` (Task 4 Step 4) and asserted in tests (Task 4 Step 1) — consistent. `main(argv=None) -> int` signature is identical across the test, the implementation, and the `[project.scripts]` target `henry_castillo.__main__:main`. Console name `henry-castillo` consistent across pyproject, tests, README.

No issues found.
