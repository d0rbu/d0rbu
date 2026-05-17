# d0rbu — Milestone 1.5: Best-Practices Dev Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the d0rbu scaffold into a robust, "all the bells and whistles" codebase: reproducible package management, linting, typing, testing+coverage, pre-commit, conventional commits, security scanning, CLI auto-update + dependency automation, full CI, release automation, and deployment scaffolding — for both Python and a pre-staged TypeScript toolchain.

**Architecture:** A single feature branch `milestone-1.5-dev-infra`, opened as a **Draft PR early (Iteration 1)** and filled in across 15 small, independently-green iterations (progressive hardening). Python tooling is `uv`/`ruff`/`ty`/`pytest`; the only runtime code added is a fully-tested `update` module. TypeScript tooling (`packages/npm/`) is scaffolded now (Biome + tsup + Vitest) so Milestone 4 just drops code in. CI/release/deploy workflows are created now and self-activate as later milestones land.

**Tech Stack:** Python ≥3.10 · uv (committed lockfile) · ruff · ty · pytest + pytest-cov · pre-commit · gitleaks · pip-audit · zizmor · git-cliff · CycloneDX · GitHub Actions (CI, CodeQL, Trusted-Publishing release, Pages) · Dependabot · TypeScript + Biome + tsup + Vitest + Node 20.

---

## Conventions (apply to EVERY iteration)

- **Branch:** all work on `milestone-1.5-dev-infra` (created in Iteration 1). Never commit to `main`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `ci:`, `build:`, `docs:`, `test:`, `refactor:`). Append the trailer line `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` to every commit message.
- **Green gate:** after each iteration, `uv run pytest -q` must pass. From Iteration 9 on, `make check` must pass locally before commit.
- **Working dir:** `/home/d0rb/Documents/Github/d0rbu` for all commands.
- **No `main` changes:** the plan doc file is currently uncommitted on `main`'s working tree; Iteration 1 carries it onto the branch and commits it there.
- **Deliberate reversal (call out in PR):** Milestone 1 gitignored `uv.lock`. Milestone 1.5 **commits** `uv.lock` (Iteration 1). Rationale: this is an application-style CLI; a committed lockfile gives reproducible dev/CI (`uv sync --locked`), while published wheels still use version ranges so library consumers are unaffected. This is an intentional best-practices change, not a regression.

---

## File Structure

| Path | Responsibility |
|---|---|
| `uv.lock` | Committed, hash-pinned reproducible dependency lock |
| `.editorconfig` / `.gitattributes` | Cross-editor + git normalization |
| `src/henry_castillo/py.typed` | PEP 561 marker — ship type information |
| `src/henry_castillo/update.py` | Update-check + self-update logic (the only new runtime code) |
| `src/henry_castillo/__main__.py` | Extended: `--version/--check-update/--update` + throttled TTY notice |
| `tests/test_update.py` / `tests/test_cli.py` | Tests for update logic and CLI flags |
| `pyproject.toml` | Adds ruff/ty/pytest/coverage config, `packaging` dep, expanded dev extra |
| `.pre-commit-config.yaml` | ruff, ruff-format, ty, gitleaks, conventional-commit, uv-lock, std hooks |
| `Makefile` | One-touch dev tasks (`setup/lint/format/typecheck/test/check/build`) |
| `cliff.toml` / `CHANGELOG.md` | git-cliff config + seeded changelog |
| `CONTRIBUTING.md` / `SECURITY.md` | Contributor + security policy docs |
| `.github/workflows/ci.yml` | Lint, type, test-matrix, build, lockfile, pre-commit, security, TS |
| `.github/workflows/codeql.yml` | CodeQL (python + javascript-typescript) |
| `.github/workflows/release.yml` | Tag/dispatch → build, changelog, PyPI Trusted Publishing, GH Release + SBOM |
| `.github/workflows/pages.yml` | GitHub Pages deploy, guarded/no-op until web/ exists (M3) |
| `.github/dependabot.yml` | Automated updates: uv, github-actions, npm |
| `.github/ISSUE_TEMPLATE/*`, `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS` | Repo collaboration scaffolding |
| `packages/npm/*` | TypeScript toolchain scaffold (package.json, tsconfig, biome, tsup, vitest, src, test) |
| `README.md` | Badges + roadmap note for M1.5 |

---

## Iteration 1: Branch, lockfile, Draft PR

**Files:**
- Modify: `.gitignore`
- Create: `uv.lock` (generated, then committed)
- Commit (already on disk, uncommitted): `docs/superpowers/plans/2026-05-17-d0rbu-milestone-1.5-dev-infra.md`

- [ ] **Step 1: Create the branch from up-to-date main**

```bash
git fetch origin
git switch -c milestone-1.5-dev-infra origin/main
```
Expected: new branch created at the same commit as `origin/main` (`6f8bc04…`). The uncommitted plan file remains in the working tree.

- [ ] **Step 2: Stop ignoring `uv.lock`**

In `.gitignore`, delete exactly these two lines (added in Milestone 1):

```
# uv lockfile — not committed for a registry-published package
uv.lock
```

- [ ] **Step 3: Generate the lockfile**

Run:
```bash
uv lock
```
Expected: `uv.lock` created/updated at repo root; exit 0.

- [ ] **Step 4: Commit branch baseline + plan + lock**

```bash
git add .gitignore uv.lock docs/superpowers/plans/2026-05-17-d0rbu-milestone-1.5-dev-infra.md
git commit -m "$(printf 'chore: start milestone 1.5; commit uv.lock\n\nReverses the Milestone 1 decision to gitignore uv.lock. This CLI is\napplication-style; a committed lockfile gives reproducible dev/CI via\n`uv sync --locked`. Published wheels still use version ranges.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>')"
```

- [ ] **Step 5: Push and open a Draft PR**

```bash
git push -u origin milestone-1.5-dev-infra
gh pr create --draft \
  --base main --head milestone-1.5-dev-infra \
  --title "Milestone 1.5: best-practices dev infrastructure" \
  --body "$(cat <<'EOF'
## Summary
Sets up robust dev infrastructure (package mgmt, lint, typing, tests, CI,
release/deploy automation, CLI auto-update, dependency automation, TS toolchain
scaffold). Filled in across the iterations of
`docs/superpowers/plans/2026-05-17-d0rbu-milestone-1.5-dev-infra.md`.

Note: intentionally commits `uv.lock` (reverses the M1 gitignore decision) for
reproducible dev/CI on this application-style CLI.

## Test Plan
- [ ] `make check` green locally
- [ ] CI green on this PR
EOF
)"
```
Expected: branch pushed; a **draft** PR opened against `main`. Record the PR URL.

- [ ] **Step 6: Verify**

```bash
git log --oneline -1
gh pr view --json isDraft,baseRefName,headRefName,url
```
Expected: one new commit; PR is `isDraft=true`, base `main`, head `milestone-1.5-dev-infra`.

---

## Iteration 2: Editor & repo hygiene

**Files:**
- Create: `.editorconfig`, `.gitattributes`, `src/henry_castillo/py.typed`

- [ ] **Step 1: Create `.editorconfig`**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{js,ts,json,jsonc,yml,yaml,toml,md}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

- [ ] **Step 2: Create `.gitattributes`**

```gitattributes
* text=auto eol=lf
*.png binary
*.jpg binary
*.pdf binary
uv.lock linguist-generated=true
*.lock linguist-generated=true
docs/** linguist-documentation=true
```

- [ ] **Step 3: Create `src/henry_castillo/py.typed`**

Create an empty file (PEP 561 marker):
```bash
: > src/henry_castillo/py.typed
```

- [ ] **Step 4: Ship the marker in the wheel — modify `pyproject.toml`**

In `pyproject.toml`, replace the block:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/henry_castillo"]
```
with:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/henry_castillo"]

[tool.hatch.build.targets.wheel.force-include]
"src/henry_castillo/py.typed" = "henry_castillo/py.typed"
```

- [ ] **Step 5: Verify build still includes the package and the marker**

```bash
uv build 2>&1 | tail -1
python3 -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); print('henry_castillo/py.typed' in z.namelist())"
rm -rf dist
```
Expected: build succeeds; prints `True`.

- [ ] **Step 6: Commit**

```bash
git add .editorconfig .gitattributes src/henry_castillo/py.typed pyproject.toml
git commit -m "chore: add editorconfig, gitattributes, PEP 561 py.typed marker

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 3: Ruff (lint + format)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ruff to the dev extra and ruff config — modify `pyproject.toml`**

Replace the `[project.optional-dependencies]` table:
```toml
[project.optional-dependencies]
lab = ["torch", "transformers", "textual"]
dev = ["pytest>=8"]
```
with:
```toml
[project.optional-dependencies]
lab = ["torch", "transformers", "textual"]
dev = [
  "pytest>=8",
  "pytest-cov>=5",
  "ruff>=0.6",
  "ty",
  "pre-commit>=3.8",
]
```

Append these tables to the END of `pyproject.toml`:
```toml
[tool.ruff]
line-length = 88
target-version = "py310"
src = ["src", "tests"]
extend-exclude = ["packages/npm"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM", "PTH", "RUF", "TID", "PL", "S"]
ignore = ["PLR0913"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004"]

[tool.ruff.lint.isort]
known-first-party = ["henry_castillo"]

[tool.ruff.format]
docstring-code-format = true
```

- [ ] **Step 2: Sync the environment**

```bash
uv sync --extra dev --extra lab 2>&1 | tail -1 || uv sync --extra dev 2>&1 | tail -1
```
Expected: environment resolves (if `lab`/torch is heavy or unavailable, the `--extra dev` fallback must succeed). Exit 0.

- [ ] **Step 3: Auto-fix and format the codebase**

```bash
uv run ruff check --fix .
uv run ruff format .
```
Expected: completes; may modify files in `src/`/`tests/`. Review the diff is reasonable (import sorting / quoting only).

- [ ] **Step 4: Verify clean + tests still pass**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
Expected: `All checks passed!`; format check passes; `4 passed`.

- [ ] **Step 5: Re-lock (dev deps changed) and commit**

```bash
uv lock
git add pyproject.toml uv.lock src tests
git commit -m "build: configure ruff lint+format; apply autofixes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 4: Typing (ty)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ty config — append to `pyproject.toml`**

```toml
[tool.ty.environment]
python-version = "3.10"
root = ["src"]
```
(ty 0.0.37 deprecated `[tool.ty.src]`; `root` is an array under `[tool.ty.environment]`.)

- [ ] **Step 2: Run the type checker**

```bash
uv run ty check 2>&1 | tail -20
```
Expected: ty runs. The minimal stub + `__init__`/`__main__` should type-check cleanly. If ty reports a genuine issue in `src/henry_castillo/*.py`, fix it minimally (e.g., add a return type annotation) — do NOT suppress with blanket ignores.

- [ ] **Step 3: Verify tests still pass**

```bash
uv run pytest -q
```
Expected: `4 passed`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src
git commit -m "build: configure ty type checking

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 5: pytest + coverage gate

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Append pytest + coverage config to `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers --strict-config --cov=henry_castillo --cov-report=term-missing --cov-report=xml --cov-fail-under=90"

[tool.coverage.run]
branch = true
source = ["henry_castillo"]

[tool.coverage.report]
show_missing = true
exclude_lines = [
  "pragma: no cover",
  "if __name__ == .__main__.:",
  "raise NotImplementedError",
]
```

- [ ] **Step 2: Run tests with coverage**

```bash
uv run pytest
```
Expected: `4 passed`; a coverage table prints; total coverage ≥ 90% (the current package is the tiny stub, fully exercised by the smoke tests); `coverage.xml` generated. If coverage is < 90% because of an untested line, that line will be covered by the dedicated tests added in Iteration 6 — for now, if and only if the gate fails here, temporarily confirm the failing lines are only in `update.py` (which does not exist yet) — it is not; the stub is fully covered, so this must pass. If it does not, STOP and report. — except the `argv is None` default branch, which Iteration 5 covers by adding `test_main_uses_sys_argv_when_argv_is_none` to `tests/test_smoke.py`.

- [ ] **Step 3: Ignore coverage artifact — modify `.gitignore`**

Under the `# Python` section of `.gitignore`, after `.pytest_cache/`, add:
```
.coverage
coverage.xml
htmlcov/
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: enforce pytest coverage gate (90%)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 6: CLI auto-update module (TDD)

**Files:**
- Test: `tests/test_update.py`, `tests/test_cli.py`
- Create: `src/henry_castillo/update.py`
- Modify: `src/henry_castillo/__main__.py`, `pyproject.toml`

- [ ] **Step 1: Add the `packaging` runtime dependency — modify `pyproject.toml`**

Replace:
```toml
dependencies = [
  "rich>=13",
  "questionary>=2",
]
```
with:
```toml
dependencies = [
  "rich>=13",
  "questionary>=2",
  "packaging>=23",
]
```
Then: `uv lock && uv sync --extra dev`.

- [ ] **Step 2: Write the failing tests — create `tests/test_update.py`**

```python
import json
from pathlib import Path

from henry_castillo import update


def test_is_outdated_true_and_false():
    assert update.is_outdated("0.1.0", "0.2.0") is True
    assert update.is_outdated("1.0.0", "1.0.0") is False
    assert update.is_outdated("2.0.0", "1.9.9") is False


def test_is_outdated_handles_garbage():
    assert update.is_outdated("0.1.0", "not-a-version") is False


def test_fetch_latest_version_parses_payload(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"info": {"version": "9.9.9"}}'

    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: FakeResp()
    )
    assert update.fetch_latest_version(url="https://example/x") == "9.9.9"


def test_fetch_latest_version_returns_none_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(update.urllib.request, "urlopen", boom)
    assert update.fetch_latest_version(url="https://example/x") is None


def test_check_for_update_uses_cache_and_throttles(tmp_path: Path):
    cache = tmp_path / "u.json"
    calls = []

    def fetcher():
        calls.append(1)
        return "9.9.9"

    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert got == "9.9.9"
    assert len(calls) == 1
    # Within the interval: served from cache, fetcher NOT called again.
    got2 = update.check_for_update(
        now=1050.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert got2 == "9.9.9"
    assert len(calls) == 1
    assert json.loads(cache.read_text())["latest"] == "9.9.9"


def test_check_for_update_none_when_current(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "9.9.9")
    got = update.check_for_update(
        now=1.0,
        cache_path=tmp_path / "u.json",
        interval=0,
        fetcher=lambda: "9.9.9",
    )
    assert got is None
```

- [ ] **Step 3: Write the failing tests — create `tests/test_cli.py`**

```python
import subprocess
import sys

from henry_castillo.__main__ import main


def test_version_flag(capsys):
    rc = main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_check_update_reports(monkeypatch, capsys):
    import henry_castillo.update as up

    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    rc = main(["--check-update"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "9.9.9" in out


def test_check_update_up_to_date(monkeypatch, capsys):
    import henry_castillo.update as up

    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    rc = main(["--check-update"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "up to date" in out.lower()


def test_update_invokes_perform(monkeypatch):
    import henry_castillo.update as up

    called = {}
    monkeypatch.setattr(up, "perform_update", lambda: called.setdefault("x", 0) or 0)
    rc = main(["--update"])
    assert rc == 0
    assert "x" in called


def test_default_run_is_quiet_and_zero(capsys):
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_console_entrypoint_still_runs():
    r = subprocess.run(["henry-castillo"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "henry-castillo" in r.stdout
```

- [ ] **Step 4: Run the new tests to verify they FAIL**

```bash
uv run pytest tests/test_update.py tests/test_cli.py -q
```
Expected: failures/errors — `henry_castillo.update` does not exist and `__main__.main` does not accept these flags. (Do not proceed until you see RED.)

- [ ] **Step 5: Create `src/henry_castillo/update.py`**

```python
"""Update checking and best-effort self-update for the henry-castillo CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.version import InvalidVersion, Version

PACKAGE = "henry-castillo"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
CHECK_INTERVAL_SECONDS = 60 * 60 * 24


def current_version() -> str:
    """Installed distribution version, falling back to the package attribute."""
    try:
        return version(PACKAGE)
    except PackageNotFoundError:  # pragma: no cover - only when not installed
        from henry_castillo import __version__

        return __version__


def cache_path() -> Path:
    """Per-user cache file for the throttled update check."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "henry-castillo" / "update-check.json"


def fetch_latest_version(timeout: float = 2.0, *, url: str = PYPI_URL) -> str | None:
    """Return the latest version string from PyPI, or None on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            data = json.load(resp)
        return str(data["info"]["version"])
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def is_outdated(current: str, latest: str) -> bool:
    """True if `latest` is a strictly newer version than `current`."""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _read_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_cache(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except OSError:  # pragma: no cover - cache is best-effort
        pass


def check_for_update(
    *,
    now: float | None = None,
    cache_path: Path | None = None,
    interval: int = CHECK_INTERVAL_SECONDS,
    fetcher=fetch_latest_version,
) -> str | None:
    """Return the newer version string if one exists, else None.

    Throttled to at most once per `interval` seconds via an on-disk cache so
    normal CLI runs never pay a network round-trip more than daily.
    """
    now = time.time() if now is None else now
    path = cache_path if cache_path is not None else globals()["cache_path"]()
    cache = _read_cache(path)
    latest = cache.get("latest")
    last = cache.get("last_check", 0)
    if now - last >= interval:
        fetched = fetcher()
        if fetched is not None:
            latest = fetched
        # Advance the throttle even on a failed fetch so an offline machine
        # does not pay the network timeout on every run; preserve any
        # previously cached `latest`.
        _write_cache(path, {"last_check": now, "latest": latest})
    if latest and is_outdated(current_version(), latest):
        return latest
    return None


def update_notice(latest: str) -> str:
    """Human-facing one-liner shown when a newer release exists."""
    return (
        f"A new release of henry-castillo is available: "
        f"{current_version()} -> {latest}. "
        f"Run `henry-castillo --update` to upgrade."
    )


def perform_update() -> int:
    """Best-effort self-upgrade. Returns the upgrade process exit code."""
    if shutil.which("uv"):
        cmd = ["uv", "tool", "upgrade", PACKAGE]
    elif shutil.which("pipx"):
        cmd = ["pipx", "upgrade", PACKAGE]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE]
    print("Running:", " ".join(cmd))
    try:
        return subprocess.call(cmd)  # noqa: S603
    except OSError as exc:  # pragma: no cover - environment dependent
        print(f"Update failed: {exc}")
        return 1
```

Note: the `path = ... globals()["cache_path"]()` indirection lets tests monkeypatch `current_version` while the default `cache_path` is still resolved lazily; when `cache_path` arg is passed (tests/CLI) it is used directly.

- [ ] **Step 6: Replace `src/henry_castillo/__main__.py`**

```python
"""CLI entrypoint.

Milestone 1.5 wires version reporting and auto-update. Real interactive
card + content subcommands arrive in Milestone 2; the default run is still
an intentional placeholder.
"""

from __future__ import annotations

import argparse
import os
import sys

from henry_castillo import __version__
from henry_castillo import update as _update

_BANNER = "henry-castillo {version}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="henry-castillo",
        description="Henry Castillo's personal CLI business card.",
    )
    parser.add_argument(
        "--version", action="store_true", help="print version and exit"
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="check whether a newer release exists and exit",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="upgrade henry-castillo to the latest release",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="skip the background update check on this run",
    )
    return parser


def _maybe_notice(args: argparse.Namespace) -> None:
    """Print a one-line update notice, only when interactive and allowed."""
    if args.no_update_check or os.environ.get("HENRY_CASTILLO_NO_UPDATE_CHECK"):
        return
    if not sys.stdout.isatty():  # never in pipes/CI/tests
        return
    latest = _update.check_for_update()
    if latest:
        print(_update.update_notice(latest))


def main(argv: list[str] | None = None) -> int:
    """Entry point for all six console aliases."""
    if argv is None:
        argv = sys.argv[1:]
    args = _build_parser().parse_args(argv)

    if args.version:
        print(_BANNER.format(version=__version__))
        return 0

    if args.update:
        return _update.perform_update()

    if args.check_update:
        latest = _update.check_for_update()
        if latest:
            print(
                f"henry-castillo {__version__}: a newer release {latest} "
                f"is available. Run `henry-castillo --update`."
            )
        else:
            print(f"henry-castillo {__version__} is up to date.")
        return 0

    print(_BANNER.format(version=__version__))
    print("Personal website + CLI business card — scaffold.")
    print("CLI features land in a later release.")
    print("Repo: https://github.com/d0rbu/d0rbu")
    _maybe_notice(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 7: Update the Milestone 1 smoke test for the new banner — modify `tests/test_smoke.py`**

`tests/test_smoke.py` currently asserts `main([])` prints `"henry-castillo"` and runs the `henry-castillo`/`d0rbu` subprocesses. All still hold (the default run still prints `henry-castillo <version>` and exits 0). **Do not change `tests/test_smoke.py`.** Confirm by reading it — if any assertion would now fail, STOP and report; none should.

- [ ] **Step 8: Run the full suite — verify GREEN**

```bash
uv run pytest -q
```
Expected: all tests pass (the original 4 smoke + new update/cli tests), coverage ≥ 90%.

- [ ] **Step 9: Lint/type the new code**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: clean. Fix any genuine issues minimally, re-run until clean.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock src/henry_castillo/update.py src/henry_castillo/__main__.py tests/test_update.py tests/test_cli.py
git commit -m "feat: CLI update check and self-update (--version/--check-update/--update)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 7: Pre-commit framework

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

```yaml
minimum_pre_commit_version: "3.8.0"
default_install_hook_types: [pre-commit, commit-msg]
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: [--fix=lf]
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.6.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
  - repo: local
    hooks:
      - id: ruff
        name: ruff lint
        entry: uv run ruff check --fix
        language: system
        types_or: [python, pyi]
        require_serial: true
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types_or: [python, pyi]
        require_serial: true
      - id: ty
        name: ty type check
        entry: uv run ty check
        language: system
        types: [python]
        pass_filenames: false
      - id: uv-lock-check
        name: uv lock is up to date
        entry: uv lock --locked
        language: system
        pass_filenames: false
        files: ^(pyproject\.toml|uv\.lock)$
```

(ruff/ruff-format run via `uv run` as local hooks so pre-commit and CI use the project's single pinned ruff — no version skew.)

- [ ] **Step 2: Install hooks and run on all files**

```bash
uv run pre-commit install --install-hooks
uv run pre-commit run --all-files
```
Expected: hooks install; first pass may auto-fix whitespace/EOF — re-run until it reports all `Passed`. If `gitleaks` flags the intentional `secret-string-lol` alias, add an allowlist: create `.gitleaks.toml` with:
```toml
[extend]
useDefault = true
[allowlist]
description = "Intentional public alias, not a secret"
regexes = ['''secret-string-lol''']
```
then re-run until green, and `git add .gitleaks.toml`.

- [ ] **Step 3: Verify tests still pass**

```bash
uv run pytest -q
```
Expected: all pass.

- [ ] **Step 4: Commit (use --no-verify ONLY if the conventional-commit hook blocks the trailer; the message below is conventional and must pass normally)**

```bash
git add .pre-commit-config.yaml .gitleaks.toml 2>/dev/null; git add -A
git commit -m "build: add pre-commit (ruff, gitleaks, conventional commits, ty, uv-lock)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
Expected: commit succeeds and the `commit-msg` hook accepts this Conventional Commit.

---

## Iteration 8: Makefile + contributor docs

**Files:**
- Create: `Makefile`, `CONTRIBUTING.md`, `SECURITY.md`

- [ ] **Step 1: Create `Makefile`**

```makefile
.DEFAULT_GOAL := help
.PHONY: help setup lint format typecheck test cov check build clean precommit

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## Create the venv and install dev deps + hooks
	uv sync --extra dev
	uv run pre-commit install --install-hooks

lint: ## Ruff lint
	uv run ruff check .

format: ## Ruff format (write)
	uv run ruff format .

typecheck: ## ty type check
	uv run ty check

test: ## Run tests
	uv run pytest

cov: ## Tests with coverage (already enforced via addopts)
	uv run pytest

precommit: ## Run all pre-commit hooks
	uv run pre-commit run --all-files

check: lint typecheck test ## Lint + type + test + format-check (the CI gate)
	uv run ruff format --check .

build: ## Build sdist + wheel
	uv build

clean: ## Remove build/coverage artifacts
	rm -rf dist build .coverage coverage.xml htmlcov .pytest_cache .ruff_cache
```

- [ ] **Step 2: Create `CONTRIBUTING.md`**

```markdown
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
```

- [ ] **Step 3: Create `SECURITY.md`**

```markdown
# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab) rather than a
public issue. You will get an acknowledgement within a reasonable timeframe.

## Supported versions

This project is pre-1.0; only the latest released version is supported.

## Automated hardening

- `gitleaks` (pre-commit + CI) blocks committed secrets.
- `pip-audit` (CI) flags vulnerable Python dependencies.
- `zizmor` (CI) statically analyzes GitHub Actions workflows.
- CodeQL scans Python and TypeScript on a schedule and on PRs.
- Dependabot keeps dependencies and Actions pinned and current.
```

- [ ] **Step 4: Verify Makefile works**

```bash
make help && make check
```
Expected: help table prints; `check` runs lint+type+test+format-check all green.

- [ ] **Step 5: Commit**

```bash
git add Makefile CONTRIBUTING.md SECURITY.md
git commit -m "docs: add Makefile, CONTRIBUTING and SECURITY policy

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 9: CI workflow (Python + quality + security)

**Files:**
- Create: `.github/workflows/ci.yml`
- Delete: `.github/workflows/.gitkeep`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  quality:
    name: lint · type · lock · pre-commit
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv sync --extra dev
      - run: uv run ruff check --output-format=github .
      - run: uv run ruff format --check .
      - run: uv run ty check
      - run: uv lock --locked
      - run: uv run pre-commit run --all-files --show-diff-on-failure

  test:
    name: test (py${{ matrix.python }})
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        python: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --extra dev --python ${{ matrix.python }}
      - run: uv run --python ${{ matrix.python }} pytest
      - uses: actions/upload-artifact@v4
        if: matrix.python == '3.12'
        with:
          name: coverage-xml
          path: coverage.xml

  build:
    name: build (sdist+wheel)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv build
      - run: uvx twine check dist/*

  security:
    name: security (pip-audit · gitleaks)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
      - run: uv export --frozen --no-emit-project --no-dev -o requirements-audit.txt
      - run: uvx pip-audit -r requirements-audit.txt
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  actions-lint:
    name: workflow static analysis (zizmor)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uvx zizmor --persona=pedantic .github/workflows

  pr-title:
    name: conventional PR title
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      pull-requests: read
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Remove the now-unneeded placeholder**

```bash
git rm .github/workflows/.gitkeep
```

- [ ] **Step 3: Lint the workflow locally before pushing**

```bash
uvx zizmor --persona=pedantic .github/workflows 2>&1 | tail -20
```
Expected: no findings (or only informational). Fix any `error`/`warning` (e.g., missing `permissions`, unpinned dangerous patterns) before committing.

- [ ] **Step 4: Commit and push (CI runs on the PR)**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add lint/type/test-matrix/build/security pipeline

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

- [ ] **Step 5: Verify CI on the PR**

```bash
sleep 20 && gh pr checks --watch
```
Expected: all jobs eventually succeed. If a job fails, read the log (`gh run view --log-failed`), fix the root cause on the branch, commit, push, re-watch. Do NOT proceed to the next iteration with red CI.

---

## Iteration 10: TypeScript toolchain scaffold

**Files:**
- Create: `packages/npm/package.json`, `packages/npm/tsconfig.json`, `packages/npm/biome.json`, `packages/npm/tsup.config.ts`, `packages/npm/vitest.config.ts`, `packages/npm/src/index.ts`, `packages/npm/test/index.test.ts`, `packages/npm/.gitignore`, `packages/npm/README.md`
- Delete: `packages/npm/.gitkeep`

- [ ] **Step 1: Create `packages/npm/package.json`**

```json
{
  "name": "henry-castillo",
  "version": "0.0.0",
  "private": true,
  "description": "Thin npm wrapper for the henry-castillo CLI (scaffold; wired in Milestone 4).",
  "type": "module",
  "bin": {
    "henry-castillo": "dist/index.js",
    "d0rbu": "dist/index.js",
    "d0rb": "dist/index.js",
    "hc": "dist/index.js",
    "henry": "dist/index.js",
    "secret-string-lol": "dist/index.js"
  },
  "files": ["dist"],
  "engines": { "node": ">=20" },
  "packageManager": "npm@10.9.0",
  "scripts": {
    "build": "tsup",
    "typecheck": "tsc --noEmit",
    "lint": "biome check .",
    "format": "biome format --write .",
    "test": "vitest run"
  },
  "devDependencies": {
    "@biomejs/biome": "1.9.4",
    "tsup": "8.3.5",
    "typescript": "5.7.2",
    "vitest": "2.1.8"
  }
}
```

- [ ] **Step 2: Create `packages/npm/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src", "test"]
}
```

- [ ] **Step 3: Create `packages/npm/biome.json`**

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "files": { "ignore": ["dist"] },
  "formatter": { "enabled": true, "indentStyle": "space", "indentWidth": 2 },
  "linter": { "enabled": true, "rules": { "recommended": true } },
  "javascript": { "formatter": { "quoteStyle": "double" } }
}
```

- [ ] **Step 4: Create `packages/npm/tsup.config.ts`**

```typescript
import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  target: "node20",
  clean: true,
  dts: false,
  banner: { js: "#!/usr/bin/env node" },
});
```

- [ ] **Step 5: Create `packages/npm/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { globals: true, environment: "node", include: ["test/**/*.test.ts"] },
});
```

- [ ] **Step 6: Create `packages/npm/src/index.ts`** (placeholder; M4 replaces with the real binary launcher)

```typescript
/**
 * Scaffold entrypoint for the henry-castillo npm wrapper.
 * Milestone 4 replaces this with a launcher that execs the bundled binary.
 */
export const PACKAGE = "henry-castillo";

export function banner(version = "0.0.0"): string {
  return `${PACKAGE} ${version} — scaffold (npm wrapper wired in Milestone 4)`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // eslint-disable-next-line no-console
  console.log(banner());
}
```

- [ ] **Step 7: Create `packages/npm/test/index.test.ts`**

```typescript
import { describe, expect, it } from "vitest";
import { PACKAGE, banner } from "../src/index.js";

describe("scaffold", () => {
  it("exposes the package name", () => {
    expect(PACKAGE).toBe("henry-castillo");
  });
  it("renders a banner with the version", () => {
    expect(banner("1.2.3")).toContain("henry-castillo 1.2.3");
  });
});
```

- [ ] **Step 8: Create `packages/npm/.gitignore`**

```gitignore
node_modules/
dist/
*.tsbuildinfo
```

- [ ] **Step 9: Create `packages/npm/README.md`**

```markdown
# henry-castillo (npm)

Scaffold for the npm distribution of the `henry-castillo` CLI. The real thin
wrapper that ships and execs the prebuilt binary is implemented in Milestone 4.
Toolchain: TypeScript · Biome · tsup · Vitest.

```bash
npm ci && npm run lint && npm run typecheck && npm test && npm run build
```
```

- [ ] **Step 10: Install, verify the toolchain end-to-end**

```bash
cd packages/npm && npm install && npm run lint && npm run typecheck && npm test && npm run build && cd ../..
```
Expected: install OK; Biome clean; `tsc` clean; Vitest `2 passed`; `tsup` emits `packages/npm/dist/index.js`. Then `rm -rf packages/npm/dist packages/npm/node_modules` (build artifacts are gitignored; `npm install` will be re-run in CI). Keep `package-lock.json` (commit it).

- [ ] **Step 11: Remove placeholder and commit**

```bash
git rm packages/npm/.gitkeep
git add packages/npm
git commit -m "build(ts): scaffold TypeScript toolchain (Biome, tsup, Vitest)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Iteration 11: Wire TS into CI + CodeQL

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `.github/workflows/codeql.yml`

- [ ] **Step 1: Add a TypeScript job to `.github/workflows/ci.yml`**

Insert this job under `jobs:` (sibling of `quality`, before `pr-title`):
```yaml
  typescript:
    name: typescript (lint·type·test·build)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: packages/npm
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: packages/npm/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
```

- [ ] **Step 2: Create `.github/workflows/codeql.yml`**

```yaml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "27 3 * * 1"

permissions:
  contents: read

concurrency:
  group: codeql-${{ github.ref }}
  cancel-in-progress: true

jobs:
  analyze:
    name: analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: ["python", "javascript-typescript"]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          language: ${{ matrix.language }}
      - uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
```

- [ ] **Step 3: Lint workflows locally**

```bash
uvx zizmor --persona=pedantic .github/workflows 2>&1 | tail -20
```
Expected: no `error`/`warning`. Fix before committing.

- [ ] **Step 4: Commit, push, verify CI**

```bash
git add .github/workflows/ci.yml .github/workflows/codeql.yml
git commit -m "ci: add TypeScript job and CodeQL analysis

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
sleep 20 && gh pr checks --watch
```
Expected: all checks (including the new `typescript` and CodeQL) succeed. Fix-forward on red.

---

## Iteration 12: Release automation (Trusted Publishing + changelog + SBOM)

**Files:**
- Create: `.github/workflows/release.yml`, `cliff.toml`, `CHANGELOG.md`

- [ ] **Step 1: Create `cliff.toml`**

```toml
[changelog]
header = "# Changelog\n\nAll notable changes to this project are documented here.\n"
body = """
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {{ commit.message | upper_first }}{% endfor %}
{% endfor %}
"""
trim = true

[git]
conventional_commits = true
filter_unconventional = true
commit_parsers = [
  { message = "^feat", group = "Features" },
  { message = "^fix", group = "Bug Fixes" },
  { message = "^docs", group = "Documentation" },
  { message = "^perf", group = "Performance" },
  { message = "^refactor", group = "Refactor" },
  { message = "^test", group = "Testing" },
  { message = "^ci|^build|^chore", group = "Build & CI" },
]
tag_pattern = "v[0-9]*"
filter_commits = false
```

- [ ] **Step 2: Create the seed `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Milestone 1: repository scaffold.
- Milestone 1.5: best-practices dev infrastructure.
```

- [ ] **Step 3: Create `.github/workflows/release.yml`**

```yaml
name: Release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Build + changelog only; do not publish"
        type: boolean
        default: true

permissions:
  contents: read

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false

jobs:
  build:
    name: build + changelog + SBOM
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
      - run: uv build
      - run: uvx twine check dist/*
      - run: uvx git-cliff --latest --output RELEASE_NOTES.md
      - run: uv export --frozen --no-emit-project --no-dev -o requirements-sbom.txt
      - run: uvx cyclonedx-py requirements requirements-sbom.txt -o sbom.json
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: |
            dist/*
            sbom.json
            RELEASE_NOTES.md

  publish:
    name: publish to PyPI (Trusted Publishing)
    needs: build
    if: github.event_name == 'push' || inputs.dry_run == false
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: .
      - run: mkdir -p dist && find dist -maxdepth 1 -type f -name '*.whl' -o -name '*.tar.gz' | head -1
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist

  github-release:
    name: GitHub Release
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: artifacts
      - run: gh release create "${GITHUB_REF_NAME}" artifacts/dist/* artifacts/sbom.json --notes-file artifacts/RELEASE_NOTES.md
        env:
          GH_TOKEN: ${{ github.token }}
```

- [ ] **Step 4: Lint workflows + rehearse the build job logic locally**

```bash
uvx zizmor --persona=pedantic .github/workflows 2>&1 | tail -20
uv build && uvx twine check dist/* && uvx git-cliff --latest --output /tmp/RN.md && cat /tmp/RN.md && rm -rf dist
```
Expected: zizmor clean; `uv build` + `twine check` pass; git-cliff produces non-empty notes. Fix issues before commit.

- [ ] **Step 5: Document the required manual PyPI setup — append to `CONTRIBUTING.md`**

Append:
```markdown

## One-time PyPI Trusted Publishing setup (maintainer)

Before the first real publish, create the project on PyPI and add a Trusted
Publisher: PyPI → project → Publishing → add GitHub publisher with
owner `d0rbu`, repo `d0rbu`, workflow `release.yml`, environment `pypi`.
Until then, use `workflow_dispatch` with `dry_run=true` to rehearse.
```

- [ ] **Step 6: Commit, push, verify the dry-run**

```bash
git add .github/workflows/release.yml cliff.toml CHANGELOG.md CONTRIBUTING.md
git commit -m "ci: add release automation (Trusted Publishing, changelog, SBOM)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
gh workflow run release.yml -f dry_run=true --ref milestone-1.5-dev-infra
sleep 25 && gh run list --workflow=release.yml -L 1
gh run watch "$(gh run list --workflow=release.yml -L 1 --json databaseId -q '.[0].databaseId')"
```
Expected: the `build` job succeeds; `publish` is skipped (dry_run); `github-release` is skipped (not a tag). Fix-forward on failure.

---

## Iteration 13: Deployment scaffold + dependency automation + collaboration files

**Files:**
- Create: `.github/workflows/pages.yml`, `.github/dependabot.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`, `.github/CODEOWNERS`

- [ ] **Step 1: Create `.github/workflows/pages.yml`** (guarded; no-ops until `web/` has a site — Milestone 3)

```yaml
name: Deploy site

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  guard:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    outputs:
      has_site: ${{ steps.check.outputs.has_site }}
    steps:
      - uses: actions/checkout@v4
      - id: check
        run: |
          if [ -f web/package.json ] || [ -f web/index.html ]; then
            echo "has_site=true" >> "$GITHUB_OUTPUT"
          else
            echo "has_site=false" >> "$GITHUB_OUTPUT"
            echo "No site in web/ yet (arrives in Milestone 3); skipping."
          fi

  deploy:
    needs: guard
    if: needs.guard.outputs.has_site == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - working-directory: web
        run: npm ci && npm run build
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule: { interval: "weekly" }
    commit-message: { prefix: "build" }
    groups:
      python-deps: { patterns: ["*"] }
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
    commit-message: { prefix: "ci" }
    groups:
      actions: { patterns: ["*"] }
  - package-ecosystem: "npm"
    directory: "/packages/npm"
    schedule: { interval: "weekly" }
    commit-message: { prefix: "build" }
    groups:
      ts-deps: { patterns: ["*"] }
```

- [ ] **Step 3: Create `.github/PULL_REQUEST_TEMPLATE.md`**

```markdown
## Summary

<!-- What changed and why -->

## Checklist

- [ ] `make check` passes locally
- [ ] Tests added/updated (coverage ≥ 90%)
- [ ] Conventional Commit title
- [ ] Docs/changelog impact considered
```

- [ ] **Step 4: Create `.github/ISSUE_TEMPLATE/bug_report.md`**

```markdown
---
name: Bug report
about: Something isn't working
labels: bug
---

**What happened**

**Expected**

**Repro steps**

**Environment** (OS, install method, `henry-castillo --version`)
```

- [ ] **Step 5: Create `.github/ISSUE_TEMPLATE/feature_request.md`**

```markdown
---
name: Feature request
about: Suggest an idea
labels: enhancement
---

**Problem**

**Proposed solution**

**Alternatives considered**
```

- [ ] **Step 6: Create `.github/CODEOWNERS`**

```text
* @d0rbu
```

- [ ] **Step 7: Lint workflows + commit/push/verify**

```bash
uvx zizmor --persona=pedantic .github/workflows 2>&1 | tail -20
git add .github
git commit -m "ci: add Pages deploy scaffold, Dependabot, issue/PR templates, CODEOWNERS

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
sleep 20 && gh pr checks --watch
```
Expected: zizmor clean; CI still green (the Pages workflow's `guard` job runs and reports "skipping"; `deploy` is skipped).

---

## Iteration 14: Hardening + polish refinement pass

**Files:**
- Modify: `README.md`; review-only: all `.github/workflows/*.yml`

- [ ] **Step 1: Hardening audit of every workflow**

Read each file in `.github/workflows/`. Verify ALL of these hold (fix any that don't):
- top-level `permissions: contents: read` present; jobs that need more declare the minimal extra (`id-token: write`, `contents: write`, `pages: write`, `security-events: write`, `pull-requests: read`) and nothing broader.
- every job has `timeout-minutes`.
- `concurrency` is set on `ci.yml`, `codeql.yml`, `pages.yml`, `release.yml`.
- no use of `pull_request_target`; no inline `${{ }}` interpolation of untrusted input into `run:`.
Re-run `uvx zizmor --persona=pedantic .github/workflows` — expected: no `error`/`warning`.

- [ ] **Step 2: Add status badges + M1.5 note — modify `README.md`**

Directly under the first line `# d0rbu`, insert a blank line then:
```markdown
[![CI](https://github.com/d0rbu/d0rbu/actions/workflows/ci.yml/badge.svg)](https://github.com/d0rbu/d0rbu/actions/workflows/ci.yml)
[![CodeQL](https://github.com/d0rbu/d0rbu/actions/workflows/codeql.yml/badge.svg)](https://github.com/d0rbu/d0rbu/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
```
In the `## Roadmap` list, change the line `1. **Repo skeleton** — this milestone.` to:
```markdown
1. **Repo skeleton** — done.
1. **Dev infrastructure** — done (uv/ruff/ty/pytest, CI, release & deploy automation, auto-update, TS toolchain).
```
(Keep the remaining items; Markdown auto-numbers.)

- [ ] **Step 3: Full local gate**

```bash
make check && (cd packages/npm && npm ci && npm run lint && npm run typecheck && npm test && npm run build && cd ../.. ) && uvx zizmor --persona=pedantic .github/workflows
```
Expected: everything green.

- [ ] **Step 4: Commit + push**

```bash
rm -rf packages/npm/dist packages/npm/node_modules
git add README.md .github
git commit -m "ci: harden workflow permissions; docs: README badges and roadmap

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

---

## Iteration 15: Final verification & mark PR ready

**Files:** none (verification + PR state)

- [ ] **Step 1: Confirm full green on the PR**

```bash
gh pr checks --watch
```
Expected: every check passes (`quality`, `test` ×4, `build`, `security`, `actions-lint`, `typescript`, `pr-title`, CodeQL ×2).

- [ ] **Step 2: Confirm the PR diff is coherent**

```bash
gh pr view --json url,additions,deletions,files -q '{url:.url, files:(.files|length)}'
git log --oneline origin/main..HEAD
```
Expected: ~14 conventional commits telling the iteration story; file list matches the File Structure table.

- [ ] **Step 3: Mark the PR ready for review**

```bash
gh pr ready
gh pr view --json isDraft -q .isDraft
```
Expected: `false` (no longer a draft).

- [ ] **Step 4: Report completion**

Report the PR URL, the green check summary, and that Milestone 1.5 is ready for review/merge. Do NOT merge — the user reviews and merges (handled via the finishing-a-development-branch skill: Option 2, PR already open).

---

## Self-Review

**1. Spec/requirement coverage** (user's request: package mgmt, linting, typing, testing, CI, deployment scripts, auto-update, "etc.", robust, all bells & whistles; uv/ruff/ty/pytest/GHA for Python; TS scaffolded; auto-update = both; full CI/CD; via a PR):
- Package management → uv + committed `uv.lock` + `uv lock --locked` CI check (It 1, 9). ✓
- Linting → ruff lint+format, config, pre-commit, CI (It 3, 7, 9). ✓
- Typing → ty config + py.typed + pre-commit + CI (It 2, 4, 7, 9). ✓
- Testing → pytest + coverage gate + matrix CI 3.10–3.13 (It 5, 9). ✓
- CI → ci.yml (lint/type/test/build/security/zizmor/pr-title) + CodeQL (It 9, 11). ✓
- Deployment scripts → release.yml (PyPI Trusted Publishing, changelog, SBOM, GH Release) + pages.yml guarded scaffold (It 12, 13). ✓
- Auto-update → both: CLI `--update`/`--check-update`/throttled notice (It 6) + Dependabot (It 13). ✓
- "etc."/bells & whistles → pre-commit, gitleaks, pip-audit, zizmor, conventional commits, editorconfig/gitattributes, Makefile, CONTRIBUTING/SECURITY, issue/PR templates, CODEOWNERS, badges, hardening pass (It 2,7,8,9,13,14). ✓
- TS scaffolded now → packages/npm Biome/tsup/Vitest + CI lane (It 10, 11). ✓
- Via a PR → Draft PR opened It 1, marked ready It 15. ✓
- Many refinement iterations → 15 iterations of progressive hardening. ✓
No gaps.

**2. Placeholder scan:** No "TBD/TODO/handle errors" instructions; every step has concrete file contents or exact commands + expected output. The TS `src/index.ts` and pages.yml are intentionally inert scaffolds (explicitly documented as Milestone-4/3 activation), not plan placeholders. The only deliberately "do nothing real yet" artifacts are documented as such.

**3. Type/identifier consistency:** `update.py` public API — `current_version`, `cache_path`, `fetch_latest_version(url=)`, `is_outdated(current, latest)`, `check_for_update(*, now, cache_path, interval, fetcher)`, `update_notice(latest)`, `perform_update()` — is used consistently by `__main__.py` (`_update.check_for_update()`, `_update.perform_update()`, `_update.update_notice`) and by `tests/test_update.py`/`tests/test_cli.py` with matching signatures and keyword names. `main(argv: list[str] | None = None) -> int` unchanged from Milestone 1, so existing `tests/test_smoke.py` stays valid. Console name `henry-castillo`, import package `henry_castillo`, and the 6 aliases are consistent across pyproject, npm `bin`, tests, and docs.

**4. Independent-greenness:** every iteration ends with tests passing and (from It 9) CI green; configs are introduced with their dependency in the same or prior iteration (ruff/ty/pytest-cov/pre-commit added to the dev extra in It 3 before use; `packaging` added in It 6 before `update.py` imports it). The `uv.lock` reversal is called out explicitly for the PR description and CONTRIBUTING.

No issues found.
