# d0rbu — Milestone 2: The CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scaffold entrypoint with the real `henry-castillo` CLI — a content-driven personal "business card": an interactive `rich`+`questionary` card (default, on a TTY) plus direct subcommands, rendering About · Projects · Résumé · Contact · Substack from bundled `content/*.json`, fully offline, preserving the existing update-check behavior.

**Architecture:** Three new focused modules — `content.py` (typed loaders, dual-path resolver: packaged data in a wheel, repo `content/` in editable dev), `render.py` (pure `rich` renderers per section, no I/O), `tui.py` (the interactive loop with injected selector/opener/console for full testability) — wired by a rewritten `__main__.py` (argparse subcommands + the preserved `--version/--check-update/--update/--no-update-check` flags + TTY-vs-pipe dispatch). `content/*.json` is force-included into the wheel as `henry_castillo/_content/` so the installed CLI works with zero network and zero filesystem assumptions.

**Tech Stack:** Python ≥3.10 · `rich` (render) · `questionary` (interactive select) · stdlib `argparse`/`webbrowser`/`importlib.resources`/`json` · hatchling (wheel data) · pytest (100% line+branch, zero pragmas) · `gh` (draft content from public GitHub).

---

## Conventions (apply to EVERY task)

- **Branch:** all work on `milestone-2-cli` (created in Task 1 off `main` = `f8bfa22`). Never commit to `main`. PR opened **Draft** in Task 1, marked **Ready** in the final task. The user reviews & merges — never auto-merge.
- **Commits:** Conventional Commits; append the trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` to every commit. Pre-commit + commit-msg hooks are active and must pass (no `--no-verify`).
- **Green gate:** after every task, `uv run pytest` passes at **exactly 100% line+branch** (`--cov-fail-under=100`, **zero** `# pragma: no cover` in `src/`), `uv run ruff check . && uv run ruff format --check . && uv run ty check` clean, `uv run pre-commit run --all-files` all hooks pass (incl. `minimum dependency age` — no new runtime dep is added so it stays clean), `uvx zizmor --persona=pedantic --config .github/zizmor.yml .github/workflows` rc 0.
- **No new runtime dependency.** `rich`, `questionary`, `packaging` are already declared. Do not add to `[project.dependencies]` (keeps the ≥7-day dependency-age guard clean in delta-vs-`main` mode). No workflow `uses:` edits (zizmor `hash-pin`).
- **Update behavior is preserved verbatim.** Do not change `src/henry_castillo/update.py`. The `--version/--check-update/--update/--no-update-check` flags and the throttled, TTY-only, offline-safe `_maybe_notice` must behave exactly as today (their existing tests must keep passing, adjusted only where the *default* output text legitimately changed).
- **PyPI publish is OUT of scope.** M2's definition-of-done = a fully-working, tested, content-drafted, publish-**ready** CLI on a Ready PR. The real release (git tag → Trusted Publishing) is a documented follow-up the user triggers after confirming content and doing the one-time PyPI Trusted Publisher setup (already in `CONTRIBUTING.md`).
- Working dir `/home/d0rb/Documents/Github/d0rbu` for all commands.

---

## File Structure

| Path | Responsibility |
|---|---|
| `src/henry_castillo/content.py` | **NEW.** Frozen dataclasses `Profile`/`Project`/`Resume`; `load_profile()`/`load_projects()`; `_content_dir()` dual-path resolver (packaged `henry_castillo/_content/` else repo `content/`); defensive parsing (never raises on malformed/missing). |
| `src/henry_castillo/render.py` | **NEW.** Pure functions returning `rich` renderables: `banner(profile)`, `about(profile)`, `projects(projects, tag=None)`, `resume(profile)`, `contact(profile)`, `substack(profile)`, plus `SECTIONS` ordering + `render_all(console, profile, projects)` plain dump. No I/O, no network, no `print`. |
| `src/henry_castillo/tui.py` | **NEW.** `run(profile, projects, *, console, select, open_url)` — the interactive loop: identity banner + arrow-key menu (About/Projects/Résumé/Contact/Substack + a disabled "Lab (locked)"), render selected section as a panel, open links for the Substack item, loop until quit. All side-effecting collaborators injected for tests. |
| `src/henry_castillo/__main__.py` | **REWRITE.** argparse with subparsers (`about`, `projects [--tag]`, `resume`/`résumé` [`--open`], `contact`, `substack`) **plus** the preserved top-level `--version/--check-update/--update/--no-update-check`; dispatch: action-flag precedence unchanged → subcommand renders to stdout → no-subcommand+TTY runs `tui.run` → no-subcommand+pipe does `render.render_all`; `_maybe_notice` preserved. |
| `content/profile.json`, `content/projects.json` | **REWRITE (drafted).** Real-ish content drafted from public `github.com/d0rbu`, schema per spec §5, marked as a draft for the user, **no private PII**, Substack URL a clearly-marked TODO. |
| `pyproject.toml` | **MODIFY.** Force-include `content/*.json` into the wheel as `henry_castillo/_content/*.json`. |
| `tests/test_content.py`, `tests/test_render.py`, `tests/test_tui.py` | **NEW.** Unit tests (TDD) for the three modules. |
| `tests/test_cli.py`, `tests/test_smoke.py`, `tests/test_integration.py` | **MODIFY.** Migrate the default-output expectations from the scaffold banner to the real CLI; keep all update-flag/alias/`python -m` assertions. |
| `README.md`, `CONTRIBUTING.md` | **MODIFY.** Reflect the real CLI + subcommands; note the gated PyPI follow-up. |

---

## Task 1: Branch, content packaging, Draft PR

**Files:** modify `pyproject.toml`; commit; open PR.

- [ ] **Step 1: Branch off the merged main**

```bash
git fetch origin
git switch -c milestone-2-cli origin/main
git log --oneline -1   # expect: f8bfa22 Merge pull request #1 ...
```

- [ ] **Step 2: Force-include `content/*.json` into the wheel — modify `pyproject.toml`**

Find the existing block:
```toml
[tool.hatch.build.targets.wheel.force-include]
"src/henry_castillo/py.typed" = "henry_castillo/py.typed"
```
Replace it with:
```toml
[tool.hatch.build.targets.wheel.force-include]
"src/henry_castillo/py.typed" = "henry_castillo/py.typed"
"content/profile.json" = "henry_castillo/_content/profile.json"
"content/projects.json" = "henry_castillo/_content/projects.json"
```

- [ ] **Step 3: Verify the wheel ships the content + marker**

```bash
uv build 2>&1 | tail -1
python3 -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); n=z.namelist(); print(all(x in n for x in ['henry_castillo/py.typed','henry_castillo/_content/profile.json','henry_castillo/_content/projects.json']))"
rm -rf dist
```
Expected: build succeeds; prints `True`.

- [ ] **Step 4: Verify the suite is still green (no behavior change yet)**

```bash
uv run pytest -q
```
Expected: all pass, 100% coverage (`pyproject.toml` change does not affect coverage).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: ship content/*.json as packaged data for the offline CLI

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: Push and open a Draft PR**

```bash
git push -u origin milestone-2-cli
gh pr create --draft --base main --head milestone-2-cli \
  --title "ci: milestone 2 — the henry-castillo CLI" \
  --body "$(cat <<'EOF'
## Summary
Implements Milestone 2 (the real CLI) per the approved design spec: interactive
rich+questionary card + direct subcommands, content-driven from bundled
content/*.json, offline, update-check preserved. Content is **drafted from
public GitHub for the maintainer to edit**; the PyPI release is a gated
follow-up (Trusted Publishing + content sign-off).

## Test Plan
- [ ] `make check` green; 100% line+branch coverage
- [ ] All 13 CI checks green on this PR
EOF
)"
gh pr view --json isDraft,baseRefName,headRefName,url -q '{draft:.isDraft,base:.baseRefName,head:.headRefName,url:.url}'
```
Expected: a **Draft** PR against `main`. Record the PR number/URL.

---

## Task 2: `content.py` — typed loaders + dual-path resolver (TDD)

**Files:** Create `src/henry_castillo/content.py`; Test `tests/test_content.py`.

- [ ] **Step 1: Write the failing tests — create `tests/test_content.py`**

```python
import json
from pathlib import Path

import pytest

from henry_castillo import content


def _write(dirpath: Path, profile: dict | None = None, projects: object | None = None) -> Path:
    cdir = dirpath / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    if profile is not None:
        (cdir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    if projects is not None:
        (cdir / "projects.json").write_text(json.dumps(projects), encoding="utf-8")
    return cdir


def test_content_dir_prefers_packaged(tmp_path, monkeypatch):
    cdir = _write(tmp_path, profile={"name": "X"})
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content._content_dir() == cdir


def test_content_dir_falls_back_to_repo(tmp_path, monkeypatch):
    # packaged path has no profile.json -> repo fallback
    (tmp_path / "_content").mkdir(parents=True)
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    got = content._content_dir()
    assert got.name == "content"
    assert (got / "profile.json").is_file()  # the real repo content/ exists


def test_load_profile_full(tmp_path, monkeypatch):
    _write(
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
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert (p.name, p.handle, p.tagline, p.about) == (
        "Henry Castillo", "d0rbu", "ML / interpretability", "Bio.")
    assert p.email == "a@b.c"
    assert p.links == {"github": "https://github.com/d0rbu"}  # non-str dropped
    assert p.resume.pdf == "r.pdf"
    assert p.resume.experience == [{"org": "O"}]  # non-dict dropped
    assert p.resume.education == [{"school": "S"}]
    assert p.resume.highlights == ["h1", "2"]  # coerced to str


@pytest.mark.parametrize("blob", ["[]", '"x"', "5", "null", "not json", ""])
def test_load_profile_malformed_returns_empty(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "profile.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert p == content.Profile()  # defensive empty default, never raises


def test_load_profile_missing_file_returns_empty(tmp_path, monkeypatch):
    (tmp_path / "_content").mkdir(parents=True)
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content.load_profile() == content.Profile()


def test_load_profile_partial_and_bad_subtypes(tmp_path, monkeypatch):
    _write(tmp_path, profile={"name": "N", "contact": "nope", "links": "nope",
                              "resume": "nope"})
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert p.name == "N" and p.email == "" and p.links == {}
    assert p.resume == content.Resume()


def test_load_projects(tmp_path, monkeypatch):
    _write(tmp_path, projects=[
        {"name": "A", "blurb": "b", "url": "u", "tags": ["t", 1]},
        "garbage",
        {"name": "B"},
    ])
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    ps = content.load_projects()
    assert [x.name for x in ps] == ["A", "B"]
    assert ps[0].tags == ["t"]  # non-str dropped
    assert (ps[1].blurb, ps[1].url, ps[1].tags) == ("", "", [])


@pytest.mark.parametrize("blob", ["{}", '"x"', "5", "null", "bad", ""])
def test_load_projects_malformed_returns_empty_list(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "projects.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content.load_projects() == []
```

- [ ] **Step 2: Run — verify it fails**

```bash
uv run pytest tests/test_content.py -q
```
Expected: FAIL/collection error — `henry_castillo.content` does not exist.

- [ ] **Step 3: Create `src/henry_castillo/content.py`**

```python
"""Typed, defensive loaders for the bundled content/*.json.

Resolves content from the packaged data dir (``henry_castillo/_content`` in an
installed wheel) and falls back to the repo-root ``content/`` directory for an
editable/development checkout. Never raises on missing or malformed content;
returns empty defaults so the CLI degrades gracefully offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class Resume:
    pdf: str = ""
    experience: list[dict] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Profile:
    name: str = ""
    handle: str = ""
    tagline: str = ""
    about: str = ""
    email: str = ""
    links: dict[str, str] = field(default_factory=dict)
    resume: Resume = field(default_factory=Resume)


@dataclass(frozen=True)
class Project:
    name: str = ""
    blurb: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)


def _packaged_content() -> Path:
    """The packaged data directory inside the installed package."""
    return Path(str(files("henry_castillo"))) / "_content"


def _content_dir() -> Path:
    """Packaged content dir if present, else the repo-root ``content/``."""
    packaged = _packaged_content()
    if (packaged / "profile.json").is_file():
        return packaged
    return Path(__file__).resolve().parents[2] / "content"


def _read_json(name: str) -> object:
    try:
        return json.loads((_content_dir() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def load_profile() -> Profile:
    data = _read_json("profile.json")
    if not isinstance(data, dict):
        return Profile()
    contact = data.get("contact")
    email = contact.get("email") if isinstance(contact, dict) else None
    raw_links = data.get("links")
    links = (
        {k: v for k, v in raw_links.items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(raw_links, dict)
        else {}
    )
    r = data.get("resume")
    if isinstance(r, dict):
        resume = Resume(
            pdf=_str(r.get("pdf")),
            experience=[x for x in r.get("experience", []) if isinstance(x, dict)]
            if isinstance(r.get("experience"), list)
            else [],
            education=[x for x in r.get("education", []) if isinstance(x, dict)]
            if isinstance(r.get("education"), list)
            else [],
            highlights=[str(x) for x in r.get("highlights", [])]
            if isinstance(r.get("highlights"), list)
            else [],
        )
    else:
        resume = Resume()
    return Profile(
        name=_str(data.get("name")),
        handle=_str(data.get("handle")),
        tagline=_str(data.get("tagline")),
        about=_str(data.get("about")),
        email=_str(email),
        links=links,
        resume=resume,
    )


def load_projects() -> list[Project]:
    data = _read_json("projects.json")
    if not isinstance(data, list):
        return []
    projects: list[Project] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_tags = item.get("tags")
        projects.append(
            Project(
                name=_str(item.get("name")),
                blurb=_str(item.get("blurb")),
                url=_str(item.get("url")),
                tags=[t for t in raw_tags if isinstance(t, str)]
                if isinstance(raw_tags, list)
                else [],
            )
        )
    return projects
```

- [ ] **Step 4: Run — verify pass + lint/type**

```bash
uv run pytest tests/test_content.py -q
uv run ruff check src/henry_castillo/content.py tests/test_content.py
uv run ty check
```
Expected: all green. (`test_content_dir_falls_back_to_repo` relies on the real repo `content/profile.json` existing — it does, from M1.)

- [ ] **Step 5: Full suite still 100%**

```bash
uv run pytest -q
```
Expected: all pass; coverage 100% (content.py fully exercised; every branch has a test).

- [ ] **Step 6: Commit**

```bash
git add src/henry_castillo/content.py tests/test_content.py
git commit -m "feat: typed defensive content loaders (packaged + dev dual-path)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Draft real content from public GitHub

**Files:** Modify `content/profile.json`, `content/projects.json`; Test: extend `tests/test_content.py`.

- [ ] **Step 1: Fetch the public GitHub data**

```bash
gh api users/d0rbu --jq '{name,login,bio,blog,company,location,twitter_username}'
gh api 'users/d0rbu/repos?per_page=100&sort=pushed&type=owner' \
  --jq '[.[] | select(.fork==false) | {name,description,html_url,topics,stargazers_count,language}] | sort_by(-.stargazers_count)'
```
Note the returned fields. (`gh` is authenticated; this is public data only.)

- [ ] **Step 2: Write `content/profile.json` from the fetched data + schema**

Produce EXACTLY this shape (fill values from Step 1; rules below). Keep the keys/structure identical to the spec §5 schema so `content.py` and the website (M3) consume it unchanged:

```json
{
  "name": "<github name, else \"Henry Castillo\">",
  "handle": "d0rbu",
  "tagline": "<github bio one-liner, else \"ML / interpretability researcher\">",
  "about": "DRAFT — please edit. <2-4 sentences synthesized from the GitHub bio/most-notable repos; factual, no invented credentials>",
  "contact": { "email": "<a clearly-public email IF and ONLY IF GitHub exposes one; otherwise exactly> \"d0rbu@users.noreply.github.com\"" },
  "links": {
    "github": "https://github.com/d0rbu",
    "substack": "https://TODO.substack.com  (set your Substack URL)",
    "other": []
  },
  "resume": {
    "pdf": "",
    "experience": [
      { "org": "DRAFT — add real entries or delete", "role": "", "period": "", "summary": "" }
    ],
    "education": [
      { "school": "DRAFT — add real entries or delete", "degree": "", "period": "" }
    ],
    "highlights": [
      "DRAFT — add résumé highlights, or this section will render empty"
    ]
  }
}
```
**Rules (hard constraints):** Do NOT invent employers/degrees/dates — leave the résumé entries as the explicit `DRAFT —` placeholders above (they are clearly the user's to fill, and `content.py` renders them harmlessly). Do NOT use a real personal email unless GitHub publicly publishes one on the user profile; otherwise use exactly `d0rbu@users.noreply.github.com`. The `substack` value MUST be the literal TODO string above (the user has no public Substack URL to infer). `about` MUST be prefixed `DRAFT — please edit.` and contain only facts derivable from the public profile/repos. JSON must be valid and 2-space-indented (matches the existing file style; `check-json`/pre-commit will validate).

- [ ] **Step 3: Write `content/projects.json` from the fetched repos**

A JSON array of the up-to-8 most-starred non-fork repos, EXACTLY this per-item shape:
```json
[
  { "name": "<repo name>", "blurb": "<repo description, else \"\">", "url": "<html_url>", "tags": ["<up to 4 topics/language, lowercased>"] }
]
```
If the user has fewer public non-fork repos, include what exists. If a repo has no description, use `""` (not invented text). Valid JSON, 2-space indent.

- [ ] **Step 4: Add a content-conformance test — extend `tests/test_content.py`**

Append (this test loads the REAL drafted files via the dev fallback and asserts the loader yields a coherent, schema-valid result — it pins that the drafted JSON parses and is shaped correctly, without asserting volatile specific values):

```python
def test_real_repo_content_loads_and_is_coherent():
    """The committed content/*.json must parse via the loader into a coherent
    Profile/Projects (schema conformance for the drafted content)."""
    p = content.load_profile()
    assert isinstance(p, content.Profile)
    assert p.handle == "d0rbu"
    assert p.name  # non-empty
    assert p.links.get("github") == "https://github.com/d0rbu"
    assert isinstance(p.resume, content.Resume)
    projects = content.load_projects()
    assert isinstance(projects, list)
    for proj in projects:
        assert isinstance(proj, content.Project)
        assert proj.name  # every project has a name
        assert isinstance(proj.tags, list)
```

- [ ] **Step 5: Verify**

```bash
python3 -c "import json; json.load(open('content/profile.json')); json.load(open('content/projects.json')); print('content JSON OK')"
uv run pytest tests/test_content.py -q
uv run pytest -q
```
Expected: `content JSON OK`; all tests pass; coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add content/profile.json content/projects.json tests/test_content.py
git commit -m "feat(content): draft profile/projects from public GitHub (maintainer to edit)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `render.py` — pure section renderers (TDD)

**Files:** Create `src/henry_castillo/render.py`; Test `tests/test_render.py`.

- [ ] **Step 1: Write the failing tests — create `tests/test_render.py`**

```python
import io

from rich.console import Console

from henry_castillo import render
from henry_castillo.content import Profile, Project, Resume


def _text(renderable) -> str:
    buf = io.StringIO()
    Console(file=buf, width=80, no_color=True).print(renderable)
    return buf.getvalue()


PROFILE = Profile(
    name="Henry Castillo",
    handle="d0rbu",
    tagline="ML / interpretability",
    about="I work on interpretability.",
    email="d0rbu@users.noreply.github.com",
    links={"github": "https://github.com/d0rbu",
           "substack": "https://x.substack.com"},
    resume=Resume(
        pdf="",
        experience=[{"org": "Acme", "role": "RE", "period": "2024", "summary": "S"}],
        education=[{"school": "Uni", "degree": "BS", "period": "2020"}],
        highlights=["Did a thing"],
    ),
)
PROJECTS = [
    Project("saebench", "sae eval suite", "https://github.com/d0rbu/saebench",
            ["interp", "python"]),
    Project("moe-router", "routing study", "https://github.com/d0rbu/moe-router",
            ["moe"]),
]


def test_banner_has_identity():
    out = _text(render.banner(PROFILE))
    assert "Henry Castillo" in out and "@d0rbu" in out
    assert "ML / interpretability" in out


def test_about_renders_bio():
    assert "I work on interpretability." in _text(render.about(PROFILE))


def test_about_empty_is_graceful():
    assert "No bio yet" in _text(render.about(Profile()))


def test_projects_lists_all():
    out = _text(render.projects(PROJECTS))
    assert "saebench" in out and "moe-router" in out
    assert "sae eval suite" in out and "github.com/d0rbu/saebench" in out


def test_projects_tag_filter_case_insensitive():
    out = _text(render.projects(PROJECTS, tag="INTERP"))
    assert "saebench" in out and "moe-router" not in out


def test_projects_tag_no_match_message():
    assert "No projects" in _text(render.projects(PROJECTS, tag="nope"))


def test_projects_empty_message():
    assert "No projects" in _text(render.projects([]))


def test_resume_renders_sections():
    out = _text(render.resume(PROFILE))
    assert "Acme" in out and "Uni" in out and "Did a thing" in out
    assert "Résumé" in out  # accented title


def test_resume_empty_is_graceful():
    assert "No résumé" in _text(render.resume(Profile()))


def test_contact_shows_email_and_links():
    out = _text(render.contact(PROFILE))
    assert "d0rbu@users.noreply.github.com" in out
    assert "github.com/d0rbu" in out


def test_contact_empty_is_graceful():
    assert "No contact" in _text(render.contact(Profile()))


def test_substack_shows_url():
    assert "x.substack.com" in _text(render.substack(PROFILE))


def test_substack_unconfigured_message():
    p = Profile(links={"substack": "https://TODO.substack.com  (set your Substack URL)"})
    out = _text(render.substack(p))
    assert "not configured" in out.lower()


def test_substack_missing_message():
    assert "not configured" in _text(render.substack(Profile())).lower()


def test_sections_order_and_keys():
    assert [k for k, _ in render.SECTIONS] == [
        "About", "Projects", "Résumé", "Contact", "Substack"]


def test_render_all_dumps_every_section():
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), PROFILE, PROJECTS)
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "I work on interpretability." in out
    assert "saebench" in out
    assert "Acme" in out
    assert "d0rbu@users.noreply.github.com" in out
    assert "x.substack.com" in out


def test_substack_url_is_configured_helper():
    assert render.substack_url(PROFILE) == "https://x.substack.com"
    assert render.substack_url(Profile()) is None
    assert render.substack_url(
        Profile(links={"substack": "https://TODO.substack.com  (set your Substack URL)"})
    ) is None
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_render.py -q
```
Expected: FAIL — `henry_castillo.render` missing.

- [ ] **Step 3: Create `src/henry_castillo/render.py`**

```python
"""Pure ``rich`` renderers for each CLI section. No I/O, no network, no print.

Every function takes already-loaded content and returns a ``rich`` renderable
so it is trivially testable via ``rich.console.Console`` capture.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from henry_castillo.content import Profile, Project

_TODO_SUBSTACK = "https://TODO.substack.com  (set your Substack URL)"


def banner(profile: Profile) -> RenderableType:
    name = profile.name or "henry-castillo"
    handle = f"@{profile.handle}" if profile.handle else ""
    line = Text(name, style="bold cyan")
    if handle:
        line.append(f"  ·  {handle}", style="green")
    if profile.tagline:
        line.append(f"\n{profile.tagline}", style="dim")
    return Panel(line, expand=False, border_style="cyan")


def about(profile: Profile) -> RenderableType:
    body = profile.about.strip() if profile.about else ""
    return Panel(body or "No bio yet — set `about` in content/profile.json.",
                 title="About", border_style="cyan")


def projects(
    projects: Sequence[Project], tag: str | None = None
) -> RenderableType:
    items = list(projects)
    if tag is not None:
        wanted = tag.casefold()
        items = [p for p in items
                 if any(t.casefold() == wanted for t in p.tags)]
    if not items:
        msg = (f"No projects tagged '{tag}'." if tag is not None
               else "No projects yet — add to content/projects.json.")
        return Panel(msg, title="Projects", border_style="cyan")
    table = Table(expand=True, show_lines=False)
    table.add_column("Project", style="bold")
    table.add_column("What", overflow="fold")
    table.add_column("Link", style="dim")
    for p in items:
        tags = f" [{', '.join(p.tags)}]" if p.tags else ""
        table.add_row(p.name, (p.blurb or "") + tags, p.url or "")
    return Panel(table, title="Projects", border_style="cyan")


def resume(profile: Profile) -> RenderableType:
    r = profile.resume
    if not (r.experience or r.education or r.highlights or r.pdf):
        return Panel("No résumé yet — set `resume` in content/profile.json.",
                     title="Résumé", border_style="cyan")
    parts: list[RenderableType] = []
    if r.highlights:
        parts.append(Text("Highlights", style="bold"))
        for h in r.highlights:
            parts.append(Text(f"  • {h}"))
    if r.experience:
        parts.append(Text("\nExperience", style="bold"))
        for e in r.experience:
            head = " — ".join(x for x in (str(e.get("role", "")),
                                          str(e.get("org", "")),
                                          str(e.get("period", ""))) if x)
            parts.append(Text(f"  {head}"))
            if e.get("summary"):
                parts.append(Text(f"    {e['summary']}", style="dim"))
    if r.education:
        parts.append(Text("\nEducation", style="bold"))
        for ed in r.education:
            parts.append(Text("  " + " — ".join(
                x for x in (str(ed.get("degree", "")), str(ed.get("school", "")),
                            str(ed.get("period", ""))) if x)))
    if r.pdf:
        parts.append(Text(f"\nPDF: {r.pdf}", style="dim"))
    return Panel(Group(*parts), title="Résumé", border_style="cyan")


def contact(profile: Profile) -> RenderableType:
    lines: list[str] = []
    if profile.email:
        lines.append(f"Email:  {profile.email}")
    for label, url in profile.links.items():
        if label == "substack":
            continue
        lines.append(f"{label.capitalize()}:  {url}")
    if not lines:
        return Panel("No contact info yet — set `contact`/`links` in "
                     "content/profile.json.", title="Contact",
                     border_style="cyan")
    return Panel("\n".join(lines), title="Contact", border_style="cyan")


def substack_url(profile: Profile) -> str | None:
    url = profile.links.get("substack", "")
    if not url or url == _TODO_SUBSTACK or "TODO" in url:
        return None
    return url


def substack(profile: Profile) -> RenderableType:
    url = substack_url(profile)
    if url is None:
        return Panel("Substack not configured yet — set `links.substack` in "
                     "content/profile.json.", title="Substack",
                     border_style="cyan")
    return Panel(f"Writing: {url}", title="Substack", border_style="cyan")


SECTIONS: list[tuple[str, Callable[[Profile, Sequence[Project]], RenderableType]]] = [
    ("About", lambda p, _: about(p)),
    ("Projects", lambda _, pr: projects(pr)),
    ("Résumé", lambda p, _: resume(p)),
    ("Contact", lambda p, _: contact(p)),
    ("Substack", lambda p, _: substack(p)),
]


def render_all(
    console: Console, profile: Profile, project_list: Sequence[Project]
) -> None:
    console.print(banner(profile))
    for _name, fn in SECTIONS:
        console.print(fn(profile, project_list))
```

- [ ] **Step 4: Run — verify pass + lint/type**

```bash
uv run pytest tests/test_render.py -q
uv run ruff check src/henry_castillo/render.py tests/test_render.py && uv run ty check
```
Expected: all green.

- [ ] **Step 5: Full suite 100%**

```bash
uv run pytest -q
```
Expected: pass; 100% (every render branch — empty/full/tag/no-match/unconfigured — has an assertion).

- [ ] **Step 6: Commit**

```bash
git add src/henry_castillo/render.py tests/test_render.py
git commit -m "feat: pure rich renderers for every CLI section

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `tui.py` — interactive loop (TDD)

**Files:** Create `src/henry_castillo/tui.py`; Test `tests/test_tui.py`.

The loop's collaborators are injected: `select(prompt, choices) -> str | None` (None = quit/Ctrl-C), `open_url(url) -> None`, and a `rich` `Console`. The default `select` wraps `questionary`; a dedicated test exercises that real wrapper with `questionary` monkeypatched, so there is **no** pragma.

- [ ] **Step 1: Write the failing tests — create `tests/test_tui.py`**

```python
import io

from rich.console import Console

from henry_castillo import tui
from henry_castillo.content import Profile, Project

PROFILE = Profile(name="Henry Castillo", handle="d0rbu", tagline="ML",
                   about="Bio.", email="e@x.y",
                   links={"github": "https://github.com/d0rbu",
                          "substack": "https://s.substack.com"})
PROJECTS = [Project("p1", "b1", "u1", ["t"])]


def _console():
    buf = io.StringIO()
    return Console(file=buf, width=80, no_color=True), buf


def test_loop_renders_selected_then_quits():
    console, buf = _console()
    seq = iter(["About", "Projects", None])  # None => quit
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=lambda _u: None)
    out = buf.getvalue()
    assert "Henry Castillo" in out          # banner shown once
    assert "Bio." in out                    # About rendered
    assert "p1" in out                      # Projects rendered


def test_quit_immediately_only_banner():
    console, buf = _console()
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: None, open_url=lambda _u: None)
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "Bio." not in out


def test_substack_selection_opens_url():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Substack", None])
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq),
            open_url=opened.append)
    assert opened == ["https://s.substack.com"]


def test_substack_unconfigured_does_not_open():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Substack", None])
    tui.run(Profile(name="N"), PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=opened.append)
    assert opened == []


def test_unknown_selection_is_ignored():
    console, buf = _console()
    seq = iter(["Lab (locked)", "Nonsense", None])
    tui.run(PROFILE, PROJECTS, console=console,
            select=lambda *_a, **_k: next(seq), open_url=lambda _u: None)
    out = buf.getvalue()
    assert "locked" in out.lower()  # informs the user Lab is unavailable
    assert "Bio." not in out        # no section rendered for junk choices


def test_default_select_wraps_questionary(monkeypatch):
    class FakeQ:
        def ask(self):
            return "About"

    captured = {}

    def fake_select(message, choices, **kwargs):
        captured["message"] = message
        captured["choices"] = choices
        return FakeQ()

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    assert tui._default_select("Pick", ["About", "Quit"]) == "About"
    assert captured["choices"] == ["About", "Quit"]


def test_default_select_returns_none_on_keyboardinterrupt(monkeypatch):
    def fake_select(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    assert tui._default_select("Pick", ["About"]) is None


def test_default_open_url_uses_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    tui._default_open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_run_uses_real_defaults_when_not_injected(monkeypatch):
    # default select returns None immediately -> loop exits after banner
    monkeypatch.setattr(tui, "_default_select", lambda *_a, **_k: None)
    console, buf = _console()
    tui.run(PROFILE, PROJECTS, console=console)
    assert "Henry Castillo" in buf.getvalue()
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_tui.py -q
```
Expected: FAIL — `henry_castillo.tui` missing.

- [ ] **Step 3: Create `src/henry_castillo/tui.py`**

```python
"""Interactive card loop: identity banner + arrow-key section menu.

Side-effecting collaborators (`select`, `open_url`) are injected so the loop
is fully unit-testable without a real terminal. The defaults wrap
``questionary`` and ``webbrowser``.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable, Sequence

import questionary
from rich.console import Console

from henry_castillo import render
from henry_castillo.content import Profile, Project

_MENU = [name for name, _ in render.SECTIONS]
_LAB_LOCKED = "Lab (locked)"
_QUIT = "Quit"

SelectFn = Callable[[str, list[str]], str | None]
OpenUrlFn = Callable[[str], None]


def _default_select(message: str, choices: list[str]) -> str | None:
    try:
        return questionary.select(message, choices=choices).ask()
    except KeyboardInterrupt:
        return None


def _default_open_url(url: str) -> None:
    webbrowser.open(url)


def run(
    profile: Profile,
    project_list: Sequence[Project],
    *,
    console: Console,
    select: SelectFn | None = None,
    open_url: OpenUrlFn | None = None,
) -> None:
    select = select or _default_select
    open_url = open_url or _default_open_url
    sections = dict(render.SECTIONS)
    choices = [*_MENU, _LAB_LOCKED, _QUIT]

    console.print(render.banner(profile))
    while True:
        choice = select("Navigate (↑/↓, Enter; q quits)", choices)
        if choice is None or choice == _QUIT:
            return
        if choice == _LAB_LOCKED:
            console.print(
                "[dim]Lab is locked — install the optional extra: "
                "`uvx --with 'henry-castillo[lab]' henry-castillo lab`[/dim]"
            )
            continue
        renderer = sections.get(choice)
        if renderer is None:
            continue
        console.print(renderer(profile, project_list))
        if choice == "Substack":
            url = render.substack_url(profile)
            if url is not None:
                open_url(url)
```

- [ ] **Step 4: Run — verify pass + lint/type**

```bash
uv run pytest tests/test_tui.py -q
uv run ruff check src/henry_castillo/tui.py tests/test_tui.py && uv run ty check
```
Expected: all green. (Every branch — quit, None, Lab, unknown, Substack-open vs not, real `_default_select` ok/KeyboardInterrupt, real `_default_open_url`, defaults-not-injected — is covered.)

- [ ] **Step 5: Full suite 100%**

```bash
uv run pytest -q
```
Expected: pass; 100% line+branch; zero pragmas.

- [ ] **Step 6: Commit**

```bash
git add src/henry_castillo/tui.py tests/test_tui.py
git commit -m "feat: interactive section card loop (injected collaborators)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Rewrite `__main__.py` — subcommands + dispatch (TDD)

**Files:** Modify `src/henry_castillo/__main__.py`; Test: extend `tests/test_cli.py`.

Preserve the update flags exactly (precedence `--version` > `--update` > `--check-update`), the env contract, and `_maybe_notice`. Add subcommands and the new default dispatch.

- [ ] **Step 1: Write the failing tests — append to `tests/test_cli.py`**

```python
import io

import henry_castillo.update as _up
from henry_castillo.__main__ import main


def _run(argv, monkeypatch, *, tty=False):
    """Run main() with stdout captured; isatty controllable."""
    buf = io.StringIO()
    buf.isatty = lambda: tty  # type: ignore[attr-defined]
    monkeypatch.setattr("sys.stdout", buf)
    rc = main(argv)
    return rc, buf.getvalue()


def test_subcommand_about(monkeypatch):
    rc, out = _run(["about"], monkeypatch)
    assert rc == 0
    assert "About" in out


def test_subcommand_projects(monkeypatch):
    rc, out = _run(["projects"], monkeypatch)
    assert rc == 0
    assert "Projects" in out


def test_subcommand_projects_tag(monkeypatch):
    rc, out = _run(["projects", "--tag", "zzznotareal_tag"], monkeypatch)
    assert rc == 0
    assert "No projects tagged 'zzznotareal_tag'." in out


def test_subcommand_resume_and_accent_alias(monkeypatch):
    rc, out = _run(["resume"], monkeypatch)
    assert rc == 0 and "Résumé" in out
    rc2, out2 = _run(["résumé"], monkeypatch)
    assert rc2 == 0 and "Résumé" in out2


def test_subcommand_resume_open(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("henry_castillo.__main__._open_url", opened.append)
    rc, _ = _run(["resume", "--open"], monkeypatch)
    assert rc == 0
    # opened only if the drafted résumé has a real pdf URL; with the DRAFT
    # placeholder (empty pdf) it must NOT open and must not crash:
    assert opened == [] or opened  # tolerate both; the next test pins behavior


def test_resume_open_with_pdf(monkeypatch):
    import henry_castillo.__main__ as m
    from henry_castillo.content import Profile, Resume

    monkeypatch.setattr(m.content, "load_profile",
                        lambda: Profile(resume=Resume(pdf="https://x/cv.pdf")))
    opened: list[str] = []
    monkeypatch.setattr(m, "_open_url", opened.append)
    rc, _ = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == ["https://x/cv.pdf"]


def test_resume_open_without_pdf_message(monkeypatch):
    import henry_castillo.__main__ as m
    from henry_castillo.content import Profile

    monkeypatch.setattr(m.content, "load_profile", lambda: Profile())
    opened: list[str] = []
    monkeypatch.setattr(m, "_open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == []
    assert "no résumé" in out.lower()


def test_subcommand_contact(monkeypatch):
    rc, out = _run(["contact"], monkeypatch)
    assert rc == 0 and "Contact" in out


def test_subcommand_substack(monkeypatch):
    rc, out = _run(["substack"], monkeypatch)
    assert rc == 0 and "Substack" in out


def test_default_non_tty_renders_all_plain(monkeypatch):
    rc, out = _run([], monkeypatch, tty=False)
    assert rc == 0
    # plain full render: banner + every section, no interactive prompt
    assert "About" in out and "Projects" in out and "Contact" in out


def test_default_tty_runs_interactive_loop(monkeypatch):
    import henry_castillo.__main__ as m

    called = {}

    def fake_run(profile, projects, *, console, **kw):
        called["yes"] = True
        console.print("[INTERACTIVE]")

    monkeypatch.setattr(m.tui, "run", fake_run)
    rc, out = _run([], monkeypatch, tty=True)
    assert rc == 0 and called.get("yes") and "[INTERACTIVE]" in out


def test_subcommand_suppresses_notice_in_pipe(monkeypatch):
    monkeypatch.setattr(_up, "check_for_update",
                        lambda **_k: (_ for _ in ()).throw(AssertionError("net!")))
    rc, out = _run(["about"], monkeypatch, tty=False)
    assert rc == 0 and "new release" not in out.lower()


def test_version_still_short_circuits(monkeypatch):
    rc, out = _run(["--version"], monkeypatch)
    assert rc == 0
    assert out.strip() == f"henry-castillo {__import__('henry_castillo').__version__}"
```

(Keep ALL pre-existing `tests/test_cli.py` tests for `--version/--check-update/--update/--no-update-check`, abbreviation/exit-2, precedence, env contract — they must still pass unchanged.)

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_cli.py -q
```
Expected: new tests FAIL (no subcommands / old scaffold default).

- [ ] **Step 3: Rewrite `src/henry_castillo/__main__.py`**

```python
"""CLI entrypoint: interactive card (TTY) or subcommands, content-driven.

Update-check behavior (`--version/--check-update/--update/--no-update-check`,
the throttled TTY-only offline-safe notice) is preserved from Milestone 1.5.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from rich.console import Console

from henry_castillo import __version__, content, render, tui
from henry_castillo import update as _update

_FALSEY_ENV = {"", "0", "false", "no", "off"}


def _update_check_disabled_by_env() -> bool:
    val = os.environ.get("HENRY_CASTILLO_NO_UPDATE_CHECK")
    return val is not None and val.strip().lower() not in _FALSEY_ENV


def _open_url(url: str) -> None:
    webbrowser.open(url)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="henry-castillo",
        description="Henry Castillo's personal CLI business card.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="store_true",
                        help="print version and exit")
    parser.add_argument("--check-update", action="store_true",
                        help="check whether a newer release exists and exit")
    parser.add_argument("--update", action="store_true",
                        help="upgrade henry-castillo to the latest release")
    parser.add_argument("--no-update-check", action="store_true",
                        help="skip the background update check on this run")
    sub = parser.add_subparsers(dest="section")
    sub.add_parser("about", help="show the about section")
    pp = sub.add_parser("projects", help="list projects")
    pp.add_argument("--tag", help="filter projects by tag")
    rp = sub.add_parser("resume", aliases=["résumé"], help="show the résumé")
    rp.add_argument("--open", dest="open_resume", action="store_true",
                    help="open the résumé PDF/web link in a browser")
    sub.add_parser("contact", help="show contact info")
    sub.add_parser("substack", help="show the Substack link")
    return parser


def _maybe_notice(args: argparse.Namespace) -> None:
    if args.no_update_check or _update_check_disabled_by_env():
        return
    if not sys.stdout.isatty():
        return
    latest = _update.check_for_update()
    if latest:
        print(_update.update_notice(latest))


def _render_section(args: argparse.Namespace, console: Console) -> int:
    profile = content.load_profile()
    section = args.section
    if section == "about":
        console.print(render.about(profile))
    elif section == "projects":
        console.print(render.projects(content.load_projects(),
                                      tag=getattr(args, "tag", None)))
    elif section in ("resume", "résumé"):
        console.print(render.resume(profile))
        if getattr(args, "open_resume", False):
            pdf = profile.resume.pdf
            if pdf:
                _open_url(pdf)
            else:
                console.print(
                    "[dim]No résumé link set (`resume.pdf` in "
                    "content/profile.json).[/dim]"
                )
    elif section == "contact":
        console.print(render.contact(profile))
    elif section == "substack":
        console.print(render.substack(profile))
        url = render.substack_url(profile)
        if url is not None:
            _open_url(url)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = _build_parser().parse_args(argv)

    if args.version:
        print(f"henry-castillo {__version__}")
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

    console = Console()
    if args.section is not None:
        rc = _render_section(args, console)
        _maybe_notice(args)
        return rc

    profile = content.load_profile()
    projects = content.load_projects()
    if sys.stdout.isatty():
        tui.run(profile, projects, console=console)
    else:
        render.render_all(console, profile, projects)
        _maybe_notice(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the CLI tests — verify pass**

```bash
uv run pytest tests/test_cli.py -q
```
Expected: all pass (new subcommand/dispatch tests + all preserved update-flag tests).

- [ ] **Step 5: Lint/type**

```bash
uv run ruff check src/henry_castillo/__main__.py tests/test_cli.py && uv run ruff format --check . && uv run ty check
```
Expected: clean. (Note: `import webbrowser` is used by `_open_url`; `Console()` real default is used in `main` — the tty/pipe branches are exercised by `_run(..., tty=...)`.)

- [ ] **Step 6: Commit**

```bash
git add src/henry_castillo/__main__.py tests/test_cli.py
git commit -m "feat: real CLI — subcommands + interactive/plain dispatch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Migrate scaffold-era expectations in smoke/integration tests

**Files:** Modify `tests/test_smoke.py`, `tests/test_integration.py`.

The default output is no longer the scaffold banner; it is now the plain full render (in a pipe/subprocess) of banner + sections. Update the assertions that pinned the old scaffold text, keep everything that pins update-flag behavior, aliases, exit codes, `python -m`, and offline determinism.

- [ ] **Step 1: Read both files and identify scaffold assertions**

```bash
grep -n "scaffold\|Personal website + CLI\|CLI features land\|Repo: https://github.com/d0rbu/d0rbu" tests/test_smoke.py tests/test_integration.py
```
These substrings come from the removed scaffold banner and must be replaced with assertions on the real default output.

- [ ] **Step 2: Update `tests/test_smoke.py`**

For every test that ran `main([])` (or the console script) and asserted the scaffold text, change the assertion to the stable real default. The default non-TTY output always contains the identity (`name` from content, e.g. the drafted GitHub name) and section titles. Replace scaffold-substring asserts with:
```python
    assert "About" in out
    assert "Projects" in out
```
Keep `test_version_*`, `test_main_uses_sys_argv_*`, the `henry-castillo --version` subprocess assertions, and any update-flag tests exactly as they are (their behavior is preserved). Do NOT assert a specific drafted name (volatile — content is the maintainer's to edit); assert structural invariants (section titles, rc 0, stderr empty).

- [ ] **Step 3: Update `tests/test_integration.py`**

The 6-alias + `python -m` tests assert the first stdout line / banner. Change those that expected the scaffold first line to assert the real banner identity is present and sections render, while keeping: rc 0, **stderr empty**, **no update notice in a pipe** (`"A new release" not in stdout` — still true; offline determinism preserved because content is bundled, no network on the render path), all 6 aliases byte-identical to each other and to `python -m henry_castillo`, `--version` exact, unknown flag → rc 2, `-h` → rc 0, and the PATH-shim `--update` test. Concretely, for the bare-run alias test, replace any `assert "scaffold" in stdout` / scaffold-first-line check with:
```python
    assert r.returncode == 0
    assert r.stderr == ""
    assert "About" in r.stdout and "Projects" in r.stdout
    assert "A new release" not in r.stdout  # offline-determinism preserved
```
and keep the cross-alias byte-identity assertion (`all outputs equal`).

- [ ] **Step 4: Run smoke + integration**

```bash
uv run pytest tests/test_smoke.py tests/test_integration.py -q
```
Expected: all pass. If a console-script integration test resolves no script, it `pytest.skip`s as before (unchanged behavior).

- [ ] **Step 5: Full suite**

```bash
uv run pytest -q
```
Expected: all pass, 100% line+branch, zero pragmas.

- [ ] **Step 6: Commit**

```bash
git add tests/test_smoke.py tests/test_integration.py
git commit -m "test: migrate scaffold-era expectations to the real CLI output

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Coverage finalization + full local gate

**Files:** add targeted tests only if coverage < 100% (no source changes expected).

- [ ] **Step 1: Coverage report**

```bash
uv run pytest --cov=henry_castillo --cov-report=term-missing -q
```
Expected: `TOTAL ... 100%`, "Required test coverage of 100% reached." If any line/branch in `content.py`/`render.py`/`tui.py`/`__main__.py` is missed, add a focused test that asserts that exact behavior (do NOT add a `# pragma: no cover` — the project bar is genuine 100%). Likely candidates to double-check: the `resume.pdf` line in `render.resume`; `contact` skipping the `substack` link; `_render_section` every branch incl. `--open` with/without pdf; `main` tty vs pipe; `_default_select` KeyboardInterrupt.

- [ ] **Step 2: Full local gate**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run pre-commit run --all-files
uv lock --locked
uvx zizmor --persona=pedantic --config .github/zizmor.yml .github/workflows
uv run python scripts/check_min_dependency_age.py --skip-npm
make check
```
Expected: all green. `uv lock --locked` rc 0 (no dependency change — confirm `git diff origin/main..HEAD -- pyproject.toml` shows ONLY the `force-include` lines, no `[project.dependencies]` change). The dependency-age guard: this PR adds no new dep, so it is clean in delta-vs-`main` mode.

- [ ] **Step 3: Commit (only if Step 1 added tests)**

```bash
git add tests/
git commit -m "test: close remaining coverage to genuine 100%

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
(If no tests were needed, skip — there is nothing to commit.)

---

## Task 9: Docs

**Files:** Modify `README.md`, `CONTRIBUTING.md`.

- [ ] **Step 1: Update `README.md` "Try it" / behavior section**

Replace the scaffold-era "what this is / try it" description with the real CLI usage. Add a usage block (keep the existing badges/roadmap; only update the CLI-description region):
```markdown
## The CLI

```bash
uvx henry-castillo            # interactive card (About · Projects · Résumé · Contact · Substack)
henry-castillo about          # or jump straight to a section
henry-castillo projects --tag interp
henry-castillo resume --open  # open the résumé link
henry-castillo --version | --check-update | --update
```

Runs fully offline (content is bundled). On a non-interactive pipe it prints
the full card. Aliases: `henry-castillo`, `d0rbu`, `d0rb`, `hc`, `henry`,
`secret-string-lol`.
```
In the Roadmap, mark "CLI" done; keep the rest. Do not assert a specific name/bio in docs (content is the maintainer's draft to edit).

- [ ] **Step 2: Update `CONTRIBUTING.md`**

Under the existing release section, add one accurate line:
```markdown
The CLI is content-driven from `content/*.json` (single source of truth, also
consumed by the website in Milestone 3). Edit those files to set your real
profile/projects/résumé; the committed values are a GitHub-derived **draft**.
The first PyPI release is gated on (a) confirming that content and (b) the
one-time Trusted Publishing setup above.
```

- [ ] **Step 3: Verify + commit**

```bash
test -f docs/superpowers/specs/2026-05-17-d0rbu-design.md && echo "links OK"
uv run pre-commit run --all-files
git add README.md CONTRIBUTING.md
git commit -m "docs: document the real CLI usage; note gated PyPI follow-up

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Push, verify CI green, mark PR Ready

**Files:** none (CI + PR state).

- [ ] **Step 1: Push and watch all checks**

```bash
git push
sleep 25
gh pr checks --watch --interval 20
```
Expected: ALL 13 checks SUCCESS (quality, test py3.10–3.13, build, security incl. the dependency-age guard, zizmor, typescript, CodeQL, pr-title). Fix-forward on any red (`gh run view <id> --log-failed`, fix root cause, push, re-watch). Do NOT proceed with any red check.

- [ ] **Step 2: Confirm coherent diff**

```bash
gh pr view --json url,additions,deletions,changedFiles,isDraft -q '{url:.url,files:.changedFiles,draft:.isDraft}'
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD -- pyproject.toml
```
Expected: a coherent series of conventional commits; `pyproject.toml` diff is ONLY the `force-include` content lines (no new runtime dependency); no unrelated files.

- [ ] **Step 3: Mark the PR Ready**

```bash
gh pr ready
gh pr view --json isDraft -q .isDraft
```
Expected: `false`. Do NOT merge — the user reviews & merges.

- [ ] **Step 4: Report**

Report: PR URL, the green `gh pr checks` summary, the commit list, confirmation the PR is Ready (not merged), `git status --porcelain` clean, branch `milestone-2-cli`, `main` untouched. Note the two gated follow-ups for the maintainer before the first PyPI release: (a) edit `content/*.json` (replace the GitHub-derived draft, set the real Substack URL/résumé), (b) the one-time PyPI Trusted Publishing setup (steps in `CONTRIBUTING.md`), then push a `vX.Y.Z` tag.

---

## Self-Review

**1. Spec coverage (design spec §4/§5/§6/§10, Milestone 2 scope):**
- §6 interactive card (banner + arrow-key menu over About·Projects·Résumé·Contact·Substack, sections as rich panels, links open in browser, q/Esc quits) → Task 5 (`tui.py`) + Task 4 (`render.py`). ✓
- §6 direct subcommands (`about`, `projects [--tag]`, `resume`/`résumé` [`--open`], `contact`, `substack`) → Task 6 (`__main__` subparsers + `_render_section`). ✓
- §6 update flags preserved (`--version/--check-update/--update/--no-update-check`, throttled TTY-only offline notice, env contract, precedence) → Task 6 keeps them verbatim; Task 7 keeps their tests. ✓
- §6 Résumé displayed accented, typed subcommand ASCII `resume` + `résumé` alias → `render.resume` title "Résumé"; `aliases=["résumé"]`. ✓
- §5 content schema (profile name/handle/tagline/about/contact/links/resume; projects list) → Task 2 `content.py` typed loaders; Task 3 drafted content matches schema. ✓
- §4 content bundled into the wheel, CLI works offline → Task 1 force-include; Task 2 dual-path resolver; no network on render path (conftest still blocks net). ✓
- §4 module structure (content/render/tui/__main__) → Tasks 2/4/5/6. ✓
- §10 phasing: M2 publish-ready, real publish gated → Conventions + Task 10 report; no publish step in scope. ✓
- Non-TTY/pipe behavior (no hanging questionary) → `main` pipe branch → `render_all`; Task 6/7 tests. ✓
No gaps.

**2. Placeholder scan:** No "TBD/implement later/handle errors" instructions. Task 3's content values are drawn from a concrete `gh api` procedure with explicit schema + hard rules (this is data sourced from a live public API, not a code placeholder); the literal `DRAFT —`/Substack-TODO strings are intentional, user-facing, and asserted only structurally. Every code step has complete runnable code; every command has an expected result.

**3. Type/identifier consistency:** `Profile`/`Project`/`Resume` fields (`name/handle/tagline/about/email/links/resume`; `pdf/experience/education/highlights`; `name/blurb/url/tags`) are defined in Task 2 and used identically in Tasks 4/5/6 tests and code. `render` API (`banner/about/projects(…, tag=None)/resume/contact/substack/substack_url/SECTIONS/render_all`) defined in Task 4 and consumed unchanged by `tui.py` (Task 5) and `__main__` (Task 6). `tui.run(profile, project_list, *, console, select=None, open_url=None)` and `_default_select/_default_open_url` consistent between Task 5 code/tests and Task 6's `tui.run` call. `__main__` keeps `_update_check_disabled_by_env`, `_FALSEY_ENV`, `_maybe_notice`, `_build_parser`, `main(argv=None)->int` consistent with the preserved M1.5 contract and existing tests. `_open_url` is the single browser seam (mocked in tests). No mismatches.

No issues found.
