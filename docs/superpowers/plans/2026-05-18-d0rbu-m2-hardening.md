# d0rbu — Milestone 2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close every robustness gap and test-confidence hole found by three adversarial reviews of PR #3, plus add Hypothesis property tests — without regressing M2 behavior, keeping exactly 100% line+branch coverage (zero pragmas), all 13 CI checks green, and the PR Ready-not-merged.

**Architecture:** Additional conventional commits on the existing `milestone-2-cli` branch (the open PR #3). Source hardening at the content/CLI boundaries (`content.py`, `__main__.py`, `render.py`); a sweep of mutation-resistant tests; DRY consolidation in tests; and a new property-test module backed by a **pinned** `hypothesis` dev dependency (chosen ≥7 days old so the supply-chain dependency-age guard stays green).

**Tech Stack:** Python ≥3.10 · `rich`/`questionary` (already declared) · stdlib `unicodedata`/`importlib.resources`/`io` · `hypothesis` (NEW pinned dev/test dep) · uv · pytest (100% line+branch, zero pragmas).

---

## Conventions (apply to EVERY task)

- **Branch:** continue `milestone-2-cli` (the open PR #3). Never touch `main`. PR stays **Ready, NOT merged** (the user reviews & merges).
- **Commits:** Conventional Commits; append trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` to every commit. Pre-commit + commit-msg hooks active; no `--no-verify`.
- **Green gate after every task:** `uv run pytest -q` → 0 failures at **exactly 100% line+branch** (`--cov-fail-under=100`, **zero** `# pragma: no cover` / `no cover` / `coverage: ignore` in `src/`); `uv run ruff check . && uv run ruff format --check . && uv run ty check` clean; `uv run pre-commit run --all-files` all hooks pass; `uvx zizmor --persona=pedantic --config .github/zizmor.yml .github/workflows` rc 0.
- **Plan doc:** `docs/superpowers/plans/2026-05-18-d0rbu-m2-hardening.md` is **UNTRACKED forever** — never `git add` it, never `git add .`/`git add docs`. `git add` only the explicitly-named files per step. After every commit, `git status --porcelain` shows ONLY the two untracked plan docs (`2026-05-18-d0rbu-milestone-2-cli.md` and `2026-05-18-d0rbu-m2-hardening.md`).
- **No new RUNTIME dependency.** `hypothesis` goes in the **dev/test** dependency group only, pinned to a version whose PyPI upload is on/before **2026-05-11** (≥7 days before today 2026-05-18) so `scripts/check_min_dependency_age.py` stays green in delta mode. No workflow `uses:` edits.
- Working dir `/home/d0rb/Documents/Github/d0rbu` for all commands.
- Behavior preservation: do not change the preserved update-check contract; do not change the update-notice `print()` (it is contract-pinned by exact-stdout tests).

---

## File Structure

| Path | Change |
|---|---|
| `src/henry_castillo/content.py` | Robust zip-safe `importlib.resources` resolver (`_packaged_resource`/`_repo_content_file`/`_read_json`); `RecursionError` caught; `_sanitize`/`_sanitize_json` strip C0/C1 control chars (except `\n`/`\t`) from all loaded string content incl. nested experience/education. |
| `src/henry_castillo/__main__.py` | `_harden_stream` (degrade un-encodable output instead of crashing under restrictive stdout encoding) applied to stdout+stderr; NFC-normalize `argv` before argparse. |
| `src/henry_castillo/render.py` | `substack_url` TODO check case-insensitive. |
| `tests/test_content.py` | Rewritten to the new `_packaged_resource` seam; resolver/recursion/sanitization/utf-8 tests. |
| `tests/test_cli.py` | Tautology fixed; NFC résumé; stdout-hardening unit tests; projects `--tag` match; uses new conftest `stub_tui_run` fixture; section-name coherence test. |
| `tests/test_render.py` | Negative-assertion tests (contact excludes substack, résumé no PDF/blank-summary line, contact labels capitalized); case-insensitive TODO. |
| `tests/test_tui.py` | `"Quit"` string path; Résumé/Contact selection; KI/EOF tests hardened to fail cleanly. |
| `tests/test_integration.py` | All-6-alias byte-identity; `PYTHONIOENCODING=ascii` no-crash functional test. |
| `tests/test_property.py` | **NEW.** Hypothesis property tests (loaders never raise & typed & sanitized; render never raises / never emits ANSI; `substack_url`/`_str` invariants). |
| `conftest.py` | `COLUMNS` env hygiene; `stub_tui_run` fixture; Hypothesis `ci` settings profile (derandomized, deterministic). |
| `pyproject.toml` | Add pinned `hypothesis` to the dev/test dependency group. |
| `uv.lock` | Regenerated for the pinned `hypothesis` (+ its stable transitives). |
| `.gitignore` | Add `.hypothesis/`. |

---

## Task 1: `content.py` — zip-safe robust resolver + RecursionError (TDD)

**Files:** Modify `src/henry_castillo/content.py`; rewrite `tests/test_content.py`.

Rationale: `Path(str(files("henry_castillo")))` is wrong under zipimport/zipapp and only checks `profile.json` as the packaged sentinel; `_read_json` doesn't catch `RecursionError`; `files()` is unguarded. Replace with a per-file `importlib.resources` Traversable lookup (zip-safe), guarded, dev-fallback to repo `content/`, catching `RecursionError`, keeping `encoding="utf-8"`.

- [ ] **Step 1: Read current files**

```bash
cat src/henry_castillo/content.py
cat tests/test_content.py
```

- [ ] **Step 2: Replace the resolver region of `src/henry_castillo/content.py`**

Replace EVERYTHING from the `_packaged_content` definition through the end of `_read_json` (i.e. the `from importlib.resources import files` import, `_packaged_content`, `_content_dir`, `_read_json`) with:

```python
from importlib.resources import files
from importlib.resources.abc import Traversable


def _packaged_resource(name: str) -> Traversable | None:
    """The bundled ``henry_castillo/_content/<name>`` as a Traversable, or
    ``None`` if it is not a readable packaged resource (dev checkout, or a
    loader without resource support). Zip-safe (works under zipimport)."""
    try:
        resource = files("henry_castillo").joinpath("_content", name)
        if resource.is_file():
            return resource
    except (ModuleNotFoundError, TypeError, ValueError, OSError):
        return None
    return None


def _repo_content_file(name: str) -> Path:
    """The repo-root ``content/<name>`` used in an editable/dev checkout."""
    return Path(__file__).resolve().parents[2] / "content" / name


def _read_json(name: str) -> object:
    """Parse a bundled JSON file. Packaged resource first, else repo-root
    ``content/``. Never raises — returns ``None`` on any read/parse failure
    (missing, malformed, undecodable, or pathologically nested input)."""
    resource = _packaged_resource(name)
    try:
        if resource is not None:
            text = resource.read_text(encoding="utf-8")
        else:
            text = _repo_content_file(name).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, ValueError, RecursionError):
        return None
```

(Keep the module docstring, `from __future__ import annotations`, `import json`, `from dataclasses import ...`, `from pathlib import Path`, the dataclasses, `_str`, `load_profile`, `load_projects` as they are for now — Task 2 modifies `_str`/loaders.)

- [ ] **Step 3: Rewrite `tests/test_content.py`** with the new seam (`_packaged_resource`). Full file:

```python
import json
from pathlib import Path

import pytest

from henry_castillo import content


def _pkg(monkeypatch, tmp_path, *, profile=None, projects=None):
    """Write tmp content files and point _packaged_resource at them.
    A pathlib.Path satisfies the Traversable protocol (is_file/read_text)."""
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    if profile is not None:
        (cdir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    if projects is not None:
        (cdir / "projects.json").write_text(json.dumps(projects), encoding="utf-8")

    def fake(name: str):
        f = cdir / name
        return f if f.is_file() else None

    monkeypatch.setattr(content, "_packaged_resource", fake)
    return cdir


def _force_repo_fallback(monkeypatch):
    """Make the packaged lookup return None so the repo content/ is used."""
    monkeypatch.setattr(content, "_packaged_resource", lambda _name: None)


def test_packaged_resource_used_when_present(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "X"})
    assert content.load_profile().name == "X"


def test_repo_fallback_loads_real_committed_content(monkeypatch):
    _force_repo_fallback(monkeypatch)
    p = content.load_profile()
    assert p.handle == "d0rbu"  # the committed content/profile.json
    assert (content._repo_content_file("profile.json")).is_file()


def test_only_one_packaged_file_present_other_falls_back(tmp_path, monkeypatch):
    # Only projects.json is packaged; profile.json must independently
    # resolve (here: repo fallback) — no all-or-nothing coupling.
    _pkg(monkeypatch, tmp_path, projects=[{"name": "P"}])
    assert [x.name for x in content.load_projects()] == ["P"]
    assert content.load_profile().handle == "d0rbu"  # repo fallback


def test_packaged_resource_guarded_against_files_error(monkeypatch):
    def boom(_pkg_name):
        raise ModuleNotFoundError("no metadata")

    monkeypatch.setattr(content, "files", boom)
    assert content._packaged_resource("profile.json") is None


def test_read_json_recursionerror_returns_none(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "ok"})

    def recursive_loads(_text):
        raise RecursionError("too deep")

    monkeypatch.setattr(content.json, "loads", recursive_loads)
    assert content._read_json("profile.json") is None
    assert content.load_profile() == content.Profile()
    assert content.load_projects() == []


def test_read_json_utf8_non_ascii(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "Héctor Castañeda", "handle": "h"})
    assert content.load_profile().name == "Héctor Castañeda"


def test_load_profile_full(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        profile={
            "name": "Henry Castillo",
            "handle": "d0rbu",
            "tagline": "ML / interpretability",
            "about": "Bio.",
            "contact": {"email": "a@b.c"},
            "links": {"github": "https://github.com/d0rbu", "x": 5},
            "resume": {
                "pdf": "r.pdf",
                "experience": [{"org": "O"}, "bad"],
                "education": [{"school": "S"}],
                "highlights": ["h1", 2],
            },
        },
    )
    p = content.load_profile()
    assert (p.name, p.handle, p.tagline, p.about) == (
        "Henry Castillo",
        "d0rbu",
        "ML / interpretability",
        "Bio.",
    )
    assert p.email == "a@b.c"
    assert p.links == {"github": "https://github.com/d0rbu"}
    assert p.resume.pdf == "r.pdf"
    assert p.resume.experience == [{"org": "O"}]
    assert p.resume.education == [{"school": "S"}]
    assert p.resume.highlights == ["h1", "2"]


@pytest.mark.parametrize("blob", ["[]", '"x"', "5", "null", "not json", ""])
def test_load_profile_malformed_returns_empty(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "profile.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda name: (cdir / name) if (cdir / name).is_file() else None,
    )
    assert content.load_profile() == content.Profile()


def test_load_profile_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_packaged_resource", lambda _n: None)
    monkeypatch.setattr(
        content, "_repo_content_file", lambda n: tmp_path / "nope" / n
    )
    assert content.load_profile() == content.Profile()
    assert content.load_projects() == []


def test_load_profile_partial_and_bad_subtypes(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        profile={"name": "N", "contact": "nope", "links": "nope", "resume": "nope"},
    )
    p = content.load_profile()
    assert p.name == "N" and p.email == "" and p.links == {}
    assert p.resume == content.Resume()


def test_load_projects(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        projects=[
            {"name": "A", "blurb": "b", "url": "u", "tags": ["t", 1]},
            "garbage",
            {"name": "B"},
        ],
    )
    ps = content.load_projects()
    assert [x.name for x in ps] == ["A", "B"]
    assert ps[0].tags == ["t"]
    assert (ps[1].blurb, ps[1].url, ps[1].tags) == ("", "", [])


@pytest.mark.parametrize("blob", ["{}", '"x"', "5", "null", "bad", ""])
def test_load_projects_malformed_returns_empty_list(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "projects.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda name: (cdir / name) if (cdir / name).is_file() else None,
    )
    assert content.load_projects() == []


def test_real_repo_content_loads_and_is_coherent(monkeypatch):
    _force_repo_fallback(monkeypatch)
    p = content.load_profile()
    assert isinstance(p, content.Profile)
    assert p.handle == "d0rbu"
    assert p.name
    assert p.links.get("github") == "https://github.com/d0rbu"
    assert isinstance(p.resume, content.Resume)
    projects = content.load_projects()
    assert isinstance(projects, list)
    for proj in projects:
        assert isinstance(proj, content.Project)
        assert proj.name
        assert isinstance(proj.tags, list)
```

- [ ] **Step 4: Run & verify**

```bash
uv run pytest tests/test_content.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; full suite 0 failures at 100%.

- [ ] **Step 5: Commit**

```bash
git add src/henry_castillo/content.py tests/test_content.py
git commit -m "fix: zip-safe importlib.resources content resolver, catch RecursionError

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `content.py` — control-character sanitization (TDD)

**Files:** Modify `src/henry_castillo/content.py`; extend `tests/test_content.py`.

Rationale: `rich.text.Text` does NOT strip embedded ANSI/OSC escape sequences; raw `\x1b…` in content passes to the terminal. Sanitize all loaded string content at the boundary (defense-in-depth; also protects the future website consumer).

- [ ] **Step 1: Write failing tests — append to `tests/test_content.py`**

```python
def test_control_chars_stripped_from_all_string_fields(tmp_path, monkeypatch):
    evil = "a\x1b[31mRED\x1b[0m\x07b\x9bc"  # ESC seq, BEL, C1 CSI
    _pkg(
        monkeypatch,
        tmp_path,
        profile={
            "name": evil,
            "handle": evil,
            "tagline": evil,
            "about": "line1\nline2\ttabbed" + evil,  # \n and \t preserved
            "contact": {"email": evil},
            "links": {"git\x1bhub": "https://x/\x1b]0;pwn\x07"},
            "resume": {
                "pdf": evil,
                "experience": [{"role": evil, "summary": ["nested" + evil]}],
                "education": [{"school": evil}],
                "highlights": ["h" + evil, 1],
            },
        },
        projects=[{"name": evil, "blurb": evil, "url": evil, "tags": ["t" + evil]}],
    )
    p = content.load_profile()
    blob = repr(
        (
            p.name,
            p.handle,
            p.tagline,
            p.about,
            p.email,
            p.links,
            p.resume.pdf,
            p.resume.experience,
            p.resume.education,
            p.resume.highlights,
        )
    )
    assert "\x1b" not in blob and "\x07" not in blob and "\x9b" not in blob
    assert p.name == "aRED" + "b" + "c"
    assert "\n" in p.about and "\t" in p.about  # legitimate whitespace kept
    assert p.links == {"github": "https://x/]0;pwn"}
    assert p.resume.experience == [{"role": "aREDbc", "summary": ["nestedaREDbc"]}]
    assert p.resume.highlights == ["haREDbc", "1"]
    proj = content.load_projects()[0]
    assert "\x1b" not in repr((proj.name, proj.blurb, proj.url, proj.tags))


def test_sanitize_returns_str_and_strips_controls():
    assert content._sanitize("a\x1bb\x00c\nd\te") == "abc\nd\te"
    assert content._sanitize("plain") == "plain"
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_content.py::test_sanitize_returns_str_and_strips_controls -q
```
Expected: FAIL — `content._sanitize` does not exist.

- [ ] **Step 3: Implement in `src/henry_castillo/content.py`**

Add `import unicodedata` to the imports. Add these helpers (place directly above `_str`):

```python
def _sanitize(value: str) -> str:
    """Strip C0/C1 control characters (Unicode category ``Cc``) except
    newline and tab, so terminal control/escape sequences embedded in
    content can never reach the terminal."""
    return "".join(
        c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc"
    )


def _sanitize_json(obj: object) -> object:
    """Recursively sanitize every string inside an already-parsed JSON
    value (bounded: json.loads has already enforced a recursion limit)."""
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {_sanitize_json(k): _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    return obj
```

Change `_str` to:

```python
def _str(value: object) -> str:
    return _sanitize(value) if isinstance(value, str) else ""
```

In `load_profile`, route the link dict, highlights, and the experience/education lists through the sanitizers. Replace the `raw_links`/`links` block with:

```python
    raw_links = data.get("links")
    links = (
        {
            _sanitize(k): _sanitize(v)
            for k, v in raw_links.items()
            if isinstance(k, str) and isinstance(v, str)
        }
        if isinstance(raw_links, dict)
        else {}
    )
```

Replace the `resume` construction's `experience`/`education`/`highlights` so each retained dict is deep-sanitized and highlights are sanitized:

```python
        resume = Resume(
            pdf=_str(r.get("pdf")),
            experience=[
                _sanitize_json(x)
                for x in r.get("experience", [])
                if isinstance(x, dict)
            ]
            if isinstance(r.get("experience"), list)
            else [],
            education=[
                _sanitize_json(x)
                for x in r.get("education", [])
                if isinstance(x, dict)
            ]
            if isinstance(r.get("education"), list)
            else [],
            highlights=[_sanitize(str(x)) for x in r.get("highlights", [])]
            if isinstance(r.get("highlights"), list)
            else [],
        )
```

In `load_projects`, sanitize tags:

```python
                tags=[_sanitize(t) for t in raw_tags if isinstance(t, str)]
                if isinstance(raw_tags, list)
                else [],
```

(`name`/`blurb`/`url` already go through `_str` which now sanitizes.)

- [ ] **Step 4: Run & verify**

```bash
uv run pytest tests/test_content.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; 100%. (`_sanitize_json`'s `dict`/`list`/`str`/passthrough branches are all exercised by `test_control_chars_stripped_from_all_string_fields`.)

- [ ] **Step 5: Commit**

```bash
git add src/henry_castillo/content.py tests/test_content.py
git commit -m "fix: sanitize control/escape sequences from all loaded content

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `__main__.py` — encoding-safe output + NFC argv (TDD)

**Files:** Modify `src/henry_castillo/__main__.py`; extend `tests/test_cli.py` and `tests/test_integration.py`.

Rationale: under `PYTHONIOENCODING=ascii` (CI/Docker/C-locale) rich box-drawing/`—`/`é`/`·` raise an unhandled `UnicodeEncodeError`; and the `résumé` subcommand fails for NFD-normalized argv (macOS shells).

- [ ] **Step 1: Failing unit tests — append to `tests/test_cli.py`**

```python
import io as _io
import unicodedata as _ud


def test_harden_stream_makes_unencodable_writes_not_raise():
    raw = _io.BytesIO()
    w = _io.TextIOWrapper(raw, encoding="ascii", newline="")
    from henry_castillo.__main__ import _harden_stream

    _harden_stream(w)
    w.write("box ─ em — dot · é")  # would raise UnicodeEncodeError pre-fix
    w.flush()
    assert b"?" in raw.getvalue()  # degraded, not crashed


def test_harden_stream_noop_on_stringio():
    from henry_castillo.__main__ import _harden_stream

    _harden_stream(_io.StringIO())  # no reconfigure attr -> silent no-op


def test_resume_accent_alias_accepts_nfd_argv(monkeypatch):
    nfd = _ud.normalize("NFD", "résumé")
    assert nfd != "résumé"  # decomposed form differs
    rc, out = _run([nfd], monkeypatch)
    assert rc == 0 and "Résumé" in out
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_cli.py::test_harden_stream_makes_unencodable_writes_not_raise tests/test_cli.py::test_resume_accent_alias_accepts_nfd_argv -q
```
Expected: FAIL — `_harden_stream` missing / NFD not normalized.

- [ ] **Step 3: Modify `src/henry_castillo/__main__.py`**

Add `import unicodedata` to imports. Add this helper (place near `_open_url`):

```python
def _harden_stream(stream: object) -> None:
    """Degrade un-encodable characters instead of crashing when the
    process stdout/stderr uses a restrictive codec (e.g.
    ``PYTHONIOENCODING=ascii`` in CI/Docker). The test harness swaps in a
    ``StringIO`` (no ``reconfigure``) — silently skipped there."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
```

In `main`, replace the opening of the function:

```python
def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    _harden_stream(sys.stdout)
    _harden_stream(sys.stderr)
    argv = [unicodedata.normalize("NFC", a) for a in argv]
    args = _build_parser().parse_args(argv)
```

(Everything after `parse_args` is unchanged.)

- [ ] **Step 4: Failing functional test — append to `tests/test_integration.py`**

```python
def test_ascii_io_encoding_does_not_crash():
    """Under PYTHONIOENCODING=ascii the CLI must degrade, not traceback."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONIOENCODING": "ascii",
           "HENRY_CASTILLO_NO_UPDATE_CHECK": "1"}
    r = subprocess.run(
        [sys.executable, "-m", "henry_castillo", "about"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r.returncode == 0
    assert "UnicodeEncodeError" not in r.stderr
    assert "Traceback" not in r.stderr

    r2 = subprocess.run(
        [sys.executable, "-m", "henry_castillo"],
        capture_output=True, text=True, env=env, check=False, stdin=subprocess.DEVNULL,
    )
    assert r2.returncode == 0 and "Traceback" not in r2.stderr
```

- [ ] **Step 5: Run & verify**

```bash
uv run pytest tests/test_cli.py tests/test_integration.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; 100%. Both `_harden_stream` branches covered (TextIOWrapper → True; StringIO via `_run` and the explicit noop test → False).

- [ ] **Step 6: Commit**

```bash
git add src/henry_castillo/__main__.py tests/test_cli.py tests/test_integration.py
git commit -m "fix: never crash under restrictive stdout encoding; NFC-normalize argv

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `render.py` — case-insensitive substack TODO guard (TDD)

**Files:** Modify `src/henry_castillo/render.py`; extend `tests/test_render.py`.

- [ ] **Step 1: Failing test — append to `tests/test_render.py`**

```python
import pytest as _pytest


@_pytest.mark.parametrize("placeholder", [
    "https://TODO.substack.com",
    "https://todo.substack.com",
    "https://ToDo.substack.com",
    "  ",
    "",
])
def test_substack_url_rejects_placeholder_any_case(placeholder):
    assert render.substack_url(Profile(links={"substack": placeholder})) is None


def test_substack_url_accepts_real_url():
    assert render.substack_url(
        Profile(links={"substack": "https://real.substack.com"})
    ) == "https://real.substack.com"
```

(If the existing suite already pins uppercase `TODO`/empty, keep those tests; this strengthens coverage of lower/mixed case and whitespace-only.)

- [ ] **Step 2: Run — verify fail (lowercase case)**

```bash
uv run pytest tests/test_render.py::test_substack_url_rejects_placeholder_any_case -q
```
Expected: FAIL on the `todo`/`ToDo` and whitespace-only params.

- [ ] **Step 3: Modify `substack_url` in `src/henry_castillo/render.py`**

Replace the guard line:

```python
    url = profile.links.get("substack", "")
    if not url.strip() or "TODO" in url.upper():
        return None
    return url
```

- [ ] **Step 4: Run & verify**

```bash
uv run pytest tests/test_render.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; 100%.

- [ ] **Step 5: Commit**

```bash
git add src/henry_castillo/render.py tests/test_render.py
git commit -m "fix: reject substack placeholder case-insensitively and when blank

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Kill surviving mutations + fix the tautology (TDD-by-mutation)

**Files:** Modify `tests/test_render.py`, `tests/test_tui.py`, `tests/test_cli.py`, `tests/test_integration.py`. No `src/` change (the implementation is already correct; these tests lock it).

- [ ] **Step 1: Replace the tautological test in `tests/test_cli.py`**

Find `test_subcommand_resume_open` (asserts `opened == [] or opened`). Replace the whole function with:

```python
def test_subcommand_resume_open_draft_no_pdf(monkeypatch):
    """The committed DRAFT résumé has an empty pdf -> --open must NOT open
    a browser and must print the no-link message."""
    opened: list[str] = []
    monkeypatch.setattr("henry_castillo.__main__._open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0
    assert opened == []
    assert "no résumé" in out.lower()
```

- [ ] **Step 2: Add negative-assertion render tests — append to `tests/test_render.py`**

```python
def test_contact_excludes_substack_url():
    out = _text(render.contact(PROFILE))  # PROFILE has a substack link
    assert "substack" not in out.lower()
    assert "x.substack.com" not in out


def test_resume_pdf_line_absent_when_empty():
    p = Profile(resume=Resume(
        pdf="",
        experience=[{"org": "Corp", "role": "Dev", "period": "2023"}],
        education=[],
        highlights=["h1"],
    ))
    assert "PDF:" not in _text(render.resume(p))


def test_resume_entry_without_summary_has_no_blank_line():
    p = Profile(resume=Resume(
        experience=[{"org": "Corp", "role": "Dev", "period": "2023"}],
        education=[], highlights=[],
    ))
    out = _text(render.resume(p))
    assert "Corp" in out
    inner = [
        ln.strip("│ ")
        for ln in out.splitlines()
        if ln.startswith("│") and ln.endswith("│")
    ]
    assert all(seg for seg in inner), f"blank interior line present: {inner!r}"


def test_contact_labels_are_capitalized():
    p = Profile(email="e@x.y",
                links={"github": "https://g.io/u", "twitter": "https://t.co/u"})
    out = _text(render.contact(p))
    assert "Github:" in out and "Twitter:" in out
    assert "github:" not in out
```

- [ ] **Step 3: Add tui path tests — append to `tests/test_tui.py`**

```python
def test_quit_string_choice_exits_loop():
    console, buf = _console()
    seq = iter(["Quit"])
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=lambda _u: None)
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "Bio." not in out


def test_resume_selection_renders():
    console, buf = _console()
    seq = iter(["Résumé", None])
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=lambda _u: None)
    assert "Résumé" in buf.getvalue()


def test_contact_selection_renders():
    console, buf = _console()
    seq = iter(["Contact", None])
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=lambda _u: None)
    assert "e@x.y" in buf.getvalue()
```

- [ ] **Step 4: Harden the KI/EOF select tests in `tests/test_tui.py`**

Replace `test_default_select_returns_none_on_keyboardinterrupt` and `test_default_select_returns_none_on_eoferror` with:

```python
def test_default_select_returns_none_on_keyboardinterrupt(monkeypatch):
    def fake_select(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    try:
        result = tui._default_select("Pick", ["About"])
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped _default_select (catch removed)")
    assert result is None


def test_default_select_returns_none_on_eoferror(monkeypatch):
    def fake_select(*_a, **_k):
        raise EOFError

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    try:
        result = tui._default_select("Pick", ["About"])
    except EOFError:
        pytest.fail("EOFError escaped _default_select (catch removed)")
    assert result is None
```

Ensure `import pytest` is present at the top of `tests/test_tui.py` (add it if missing).

- [ ] **Step 5: Add CLI tag-match + all-alias byte-identity**

Append to `tests/test_cli.py`:

```python
def test_subcommand_projects_tag_match(monkeypatch):
    from henry_castillo.content import Project

    monkeypatch.setattr(
        _m.content,
        "load_projects",
        lambda: [
            Project("p-alpha", "d", "https://a.io", ["ml", "python"]),
            Project("p-beta", "d", "https://b.io", ["web"]),
        ],
    )
    rc, out = _run(["projects", "--tag", "ml"], monkeypatch)
    assert rc == 0
    assert "p-alpha" in out
    assert "p-beta" not in out
```

Append to `tests/test_integration.py` (match the file's existing `_resolve`/`ALIASES` helpers — read them first; if the alias list constant is named differently, adapt):

```python
def test_all_aliases_byte_identical():
    import subprocess

    aliases = ["henry-castillo", "d0rbu", "d0rb", "hc", "henry", "secret-string-lol"]
    ref_exe = _resolve(aliases[0])
    ref = subprocess.run([ref_exe], capture_output=True, text=True,
                         check=False, stdin=subprocess.DEVNULL)
    for alias in aliases[1:]:
        exe = _resolve(alias)
        r = subprocess.run([exe], capture_output=True, text=True,
                           check=False, stdin=subprocess.DEVNULL)
        assert r.stdout == ref.stdout, f"{alias} stdout differs"
        assert r.returncode == ref.returncode
        assert r.stderr == ref.stderr
```

(If `_resolve` `pytest.skip`s when a console script is absent, this test inherits that skip behavior — acceptable, unchanged.)

- [ ] **Step 6: Run & verify (mutation intent)**

```bash
uv run pytest tests/test_render.py tests/test_tui.py tests/test_cli.py tests/test_integration.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; full suite 0 failures at 100%. Sanity-mutation (manual, on a /tmp copy only — do NOT commit): removing `if label == "substack": continue` in render.py must now fail `test_contact_excludes_substack_url`; flipping `== _QUIT` must fail `test_quit_string_choice_exits_loop`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_render.py tests/test_tui.py tests/test_cli.py tests/test_integration.py
git commit -m "test: kill surviving mutations; replace tautological resume-open assertion

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: DRY — section-name coherence test + conftest `stub_tui_run` fixture

**Files:** Modify `conftest.py`, `tests/test_cli.py`.

- [ ] **Step 1: Read the seams**

```bash
cat conftest.py
grep -n 'monkeypatch.setattr(_m.tui, "run"\|monkeypatch.setattr(.*tui.*run' tests/test_cli.py
grep -n 'COLUMNS\|env_hygiene\|autouse' conftest.py
```

- [ ] **Step 2: Add the fixture + COLUMNS hygiene to `conftest.py`**

Add (top-level, after existing imports/fixtures):

```python
import pytest


@pytest.fixture
def stub_tui_run(monkeypatch):
    """Replace the interactive loop with a silent no-op so a tty-default
    main([]) does not enter questionary under pytest."""
    import henry_castillo.__main__ as _m

    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    return _m
```

Locate the existing autouse env-hygiene/offline fixture (from `grep`); add inside it (or, if none exists, create an `autouse=True` fixture):

```python
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)
```

(If the existing hygiene fixture is not `monkeypatch`-based, use `os.environ.pop("COLUMNS", None)` with restore in a yield-fixture instead — match the file's existing pattern exactly.)

- [ ] **Step 3: Refactor the 9 inline stubs in `tests/test_cli.py`**

For every test that currently does `monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)` (the env-contract / `_maybe_notice` tty-path tests), remove that inline line and add `stub_tui_run` to the test's parameter list. Example transform:

```python
def test_env_contract_drives_check_for_update(monkeypatch, stub_tui_run):
    # (was: monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None))
    ...
```

Do this for all 9 sites. `test_default_tty_runs_interactive_loop` keeps its OWN `fake_run` (it asserts the sentinel) — do NOT convert that one.

- [ ] **Step 4: Add the section-name coherence test — append to `tests/test_cli.py`**

```python
def test_section_names_single_source_of_truth():
    """render.SECTIONS (display titles) and __main__._SEC_* (subcommand
    names) must describe the same five logical sections; the only mapping
    is Résumé<->resume (+ the résumé accent alias)."""
    from henry_castillo import render
    import henry_castillo.__main__ as m

    display = {name for name, _ in render.SECTIONS}
    assert display == {"About", "Projects", "Résumé", "Contact", "Substack"}
    canonical = {
        m._SEC_ABOUT, m._SEC_PROJECTS, m._SEC_RESUME,
        m._SEC_CONTACT, m._SEC_SUBSTACK,
    }
    assert canonical == {"about", "projects", "resume", "contact", "substack"}
    mapped = {("resume" if d == "Résumé" else d).lower() for d in display}
    assert mapped == canonical
    assert m._SEC_RESUME_ACCENT == "résumé"
```

- [ ] **Step 5: Run & verify**

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```
Expected: all pass; 100%; the 9 refactored tests still pass via the fixture.

- [ ] **Step 6: Commit**

```bash
git add conftest.py tests/test_cli.py
git commit -m "test: extract stub_tui_run fixture, COLUMNS hygiene, section coherence

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Hypothesis property tests (+ pinned dev dependency)

**Files:** Modify `pyproject.toml`, `uv.lock`, `.gitignore`, `conftest.py`; create `tests/test_property.py`.

- [ ] **Step 1: Choose a ≥7-day-old `hypothesis` and add it to the dev group**

```bash
cat pyproject.toml   # find how dev deps are declared (dependency-groups / tool.uv)
python3 -c "import json,urllib.request; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/hypothesis/json')); rel=[(v, r[0]['upload_time_iso_8601']) for v,r in d['releases'].items() if r]; rel=[x for x in rel if x[1] <= '2026-05-11']; rel.sort(key=lambda x: x[1]); print(rel[-1])"
```
This prints the newest `hypothesis` whose upload is on/before 2026-05-11. Pin EXACTLY that version. Add it to the SAME dev/test dependency group M1.5 uses for `pytest`/`ruff` (mirror that block's syntax), e.g. for PEP-735 `[dependency-groups]`:

```toml
[dependency-groups]
dev = [
  # ...existing entries unchanged...
  "hypothesis==<CHOSEN_VERSION>",
]
```
Then:
```bash
uv lock
uv run python scripts/check_min_dependency_age.py --skip-npm
```
The dependency-age guard MUST exit 0 (delta vs origin/main: `hypothesis` + any NEW transitive — `attrs`, `sortedcontainers` — must all be ≥7d; they are long-stable, but if the guard flags a transitive, pin that transitive likewise to a ≥7-day-old version in the dev group). If it fails, iterate version choice until rc 0. Do NOT proceed until the guard is green.

- [ ] **Step 2: `.gitignore` + Hypothesis CI settings**

Append to `.gitignore`:
```
.hypothesis/
```
Append to `conftest.py`:
```python
from hypothesis import settings as _hyp_settings

_hyp_settings.register_profile("ci", derandomize=True, deadline=None,
                               print_blob=False)
_hyp_settings.load_profile("ci")
```
(`derandomize=True` makes examples deterministic → stable CI and stable coverage.)

- [ ] **Step 3: Create `tests/test_property.py`**

```python
"""Property-based invariants (Hypothesis). The loaders must never raise and
must always return correctly-typed, control-char-free content for ANY JSON;
the renderers must never raise and never emit raw escape sequences."""

import io
import json

from hypothesis import given
from hypothesis import strategies as st
from rich.console import Console

from henry_castillo import content, render
from henry_castillo.content import Profile, Resume

_json = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(max_size=8), children, max_size=5),
    max_leaves=25,
)


def _install(monkeypatch, tmp_path, name, value):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / name).write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda n: (cdir / n) if (cdir / n).is_file() else None,
    )


def _has_control(s: str) -> bool:
    import unicodedata

    return any(
        c not in "\n\t" and unicodedata.category(c) == "Cc" for c in s
    )


@given(_json)
def test_load_profile_never_raises_and_is_typed(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", value)
    p = content.load_profile()
    assert isinstance(p, Profile)
    assert isinstance(p.resume, Resume)


@given(_json)
def test_load_projects_never_raises_and_is_typed(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "projects.json", value)
    out = content.load_projects()
    assert isinstance(out, list)
    assert all(isinstance(x, content.Project) for x in out)


@given(_json)
def test_loaded_profile_has_no_control_chars(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", value)
    p = content.load_profile()
    for s in (p.name, p.handle, p.tagline, p.about, p.email, p.resume.pdf):
        assert not _has_control(s)
    for k, v in p.links.items():
        assert not _has_control(k) and not _has_control(v)
    for h in p.resume.highlights:
        assert not _has_control(h)
    assert not _has_control(repr(p.resume.experience + p.resume.education))


@given(_json)
def test_render_never_raises_and_no_ansi(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", value)
    _install(monkeypatch, tmp_path, "projects.json", value)
    profile = content.load_profile()
    projects = content.load_projects()
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), profile, projects)
    out = buf.getvalue()
    assert "\x1b" not in out and "\x9b" not in out and "\x07" not in out


@given(st.dictionaries(st.text(max_size=8), st.text(max_size=40), max_size=5))
def test_substack_url_invariant(links):
    result = render.substack_url(Profile(links=links))
    if result is not None:
        assert isinstance(result, str)
        assert result.strip()
        assert "TODO" not in result.upper()


@given(
    st.none()
    | st.integers()
    | st.floats(allow_nan=False)
    | st.text()
    | st.lists(st.text(), max_size=4)
)
def test_str_helper_always_returns_clean_str(value):
    out = content._str(value)
    assert isinstance(out, str)
    assert not _has_control(out)
```

- [ ] **Step 4: Run & verify**

```bash
uv run pytest tests/test_property.py -q
uv run pytest -q
uv run pytest --cov=henry_castillo --cov-report=term-missing -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run pre-commit run --all-files
```
Expected: all pass; full suite **0 failures at exactly 100% line+branch** (property tests are additive and deterministic via the `ci` profile; they must not drop coverage or flake). Zero pragmas. `uv.lock` consistent (`uv lock --locked` rc 0).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .gitignore conftest.py tests/test_property.py
git commit -m "test: add Hypothesis property tests (pinned >=7d-old dev dependency)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full local gate, push, CI green, final review (NOT merged)

**Files:** none (verification + PR state) unless a coverage gap requires a focused test.

- [ ] **Step 1: Coverage + full local gate**

```bash
uv run pytest --cov=henry_castillo --cov-report=term-missing -q
grep -rn "pragma: no cover\|coverage: ignore\|no cover" src/
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run pre-commit run --all-files
uv lock --locked
uvx zizmor --persona=pedantic --config .github/zizmor.yml .github/workflows
uv run python scripts/check_min_dependency_age.py --skip-npm
make check
```
Expected: 0 failures, genuine 100% line+branch, `grep` empty, all rc 0. The dependency-age guard MUST be green WITH `hypothesis` now in the lock (delta-vs-origin/main: pinned ≥7-day-old). If `uv lock --locked` shows drift, STOP and report. If coverage <100%, add a focused real test (no pragma) and re-run.

- [ ] **Step 2: Confirm coherent diff**

```bash
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD -- pyproject.toml
git status --porcelain
```
Confirm: linear conventional series; the ONLY `pyproject.toml` changes vs origin/main are the M2 force-include lines + the dev-group `hypothesis` pin (no `[project.dependencies]` runtime change); `git status --porcelain` shows ONLY the two untracked plan docs.

- [ ] **Step 3: Push and watch CI**

```bash
git push
sleep 25
gh pr checks --watch --interval 20
```
Expected: ALL 13 checks SUCCESS. Fix-forward at root cause on any red (test-only or the pinned-version choice for the dependency-age guard); never weaken; never merge. Re-watch until all green.

- [ ] **Step 4: Confirm PR state (NOT merged)**

```bash
gh pr view 3 --json isDraft,state -q '{draft:.isDraft,state:.state}'
git rev-parse origin/main
```
Expected: `draft:false, state:OPEN`; `origin/main` still `f8bfa22…`. Do NOT merge.

- [ ] **Step 5: Report**

PR URL; the 13/13 green summary; the new commit list; confirmation 100% line+branch genuine zero pragmas; the dependency-age guard green with the pinned `hypothesis` (state the chosen version + its upload date); `git status` shows only the untracked plan docs; PR Ready+OPEN, not merged; `main`/`origin/main` untouched.

---

## Self-Review

**1. Spec coverage (the chosen "Full hardening + Hypothesis" scope):**
- A1 encoding crash → Task 3 (`_harden_stream` + functional ascii test). ✓
- A2 control-char sanitization → Task 2 (`_sanitize`/`_sanitize_json` across all fields incl. nested). ✓
- A3 RecursionError → Task 1 (`except (OSError, ValueError, RecursionError)` + test). ✓
- A4 NFD résumé → Task 3 (NFC-normalize argv + test). ✓
- A5/I3/I6/M4 robust resolver → Task 1 (Traversable, guarded `files()`, per-file packaged-vs-dev). ✓
- A6 case-insensitive TODO → Task 4. ✓
- C17 utf-8 → Task 1 (kept `encoding="utf-8"` + non-ascii test). ✓
- Tautology fix + surviving mutations (R8/R14/R15/R_cap), Quit/Résumé/Contact tui, projects --tag match, all-6-alias byte-identity, KI/EOF hardening, COLUMNS hygiene → Tasks 5, 6. ✓
- DRY: section coherence + conftest fixture → Task 6. ✓
- Hypothesis property tests + pinned dep → Task 7. ✓
- Final gate/CI/PR-state → Task 8. ✓
Not in scope (deliberately, per the user): update-notice `print()` (contract-pinned), dataclass hashability (design — flagged, not changed), inherited version-test duplication. No task — intentional.

**2. Placeholder scan:** every code step has complete code; commands have expected outcomes; the only "choose a value" step (hypothesis version) is a concrete registry query with an explicit cutoff date and an iterate-until-green criterion (data sourced from PyPI, not a code placeholder).

**3. Type/identifier consistency:** `_packaged_resource(name)->Traversable|None`, `_repo_content_file(name)->Path`, `_read_json(name)->object`, `_sanitize(str)->str`, `_sanitize_json(object)->object`, `_harden_stream(object)->None` are defined once (Tasks 1–3) and referenced consistently in later tasks/tests. `Profile/Project/Resume`, `render.SECTIONS`, `_SEC_*`, `stub_tui_run`, `_run`, `_console`, `_text`, `_resolve` match the existing codebase. No mismatches.

No issues found.
