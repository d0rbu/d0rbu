# d0rbu — M2 Content Re-Architecture Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Replace bundled `content/*.json` with a remote, cached, strictly-validated
`card.json`; no-default dataclasses; guided no-data UX; loguru; Blog/Demos renames;
sanitization without regex. Spec: `docs/superpowers/specs/2026-05-19-d0rbu-content-rearchitecture-design.md`.

**Branch:** continue `milestone-2-cli` (PR #3, NOT merged). HEAD at start `37c9ba8`.

## Conventions (EVERY task)
- TDD. `uv run` everything. Green gate after each task: `uv run pytest -q` 0-fail at **exactly 100% line+branch**; ZERO `# pragma: no cover`/`no cover`/`coverage: ignore` in `src/`; `uv run ruff check . && uv run ruff format --check . && uv run ty check` clean; `uv run pre-commit run --all-files` 14 hooks; `uv run --python 3.10 python -c "import henry_castillo.__main__;print('OK310')"` → OK310.
- Conventional Commits + trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. One commit/task (stage only that task's files).
- NEVER `git add` the plan docs `docs/superpowers/plans/2026-05-1{8,9}-*.md` (untracked forever; never `git add .`/`git add docs/superpowers/plans`). After commit `git status --porcelain` shows ONLY those 3 untracked plan docs.
- Never push until R13. Never merge. Never modify `main`. `src/henry_castillo/update.py` update-check contract is preserved verbatim (do not change it; it is consumed read-only for the Demos badge).
- Module naming: logging module is `src/henry_castillo/_log.py` (NOT `logging.py`; never shadow stdlib).

## File map
- `src/henry_castillo/content.py` — REWRITE (model + parse + fetch + cache + load_card; remove old resolver/defaults/_CSI_RE).
- `src/henry_castillo/_log.py` — NEW (loguru config).
- `src/henry_castillo/failure_ui.py` — NEW (#6 no-data screen + countdown + keypress).
- `src/henry_castillo/render.py` — MODIFY (Blog rename, required-field model, no `name or`).
- `src/henry_castillo/tui.py` — MODIFY (Demos rename + update badge, Blog open).
- `src/henry_castillo/__main__.py` — MODIFY (blog subcommand, --debug+loguru, load_card+CardError dispatch, badge).
- `pyproject.toml` — MODIFY (drop content force-include; add pinned `loguru`). `uv.lock` regen.
- `web/{data/card.json,index.html,package.json,package-lock.json,build.mjs}` — NEW.
- Remove `content/profile.json`, `content/projects.json`, `content/`.
- `tests/test_content.py` REWRITE; `tests/test_log.py`,`tests/test_failure_ui.py`,`tests/test_web.py` NEW; `tests/test_render.py`,`tests/test_tui.py`,`tests/test_cli.py`,`tests/test_integration.py`,`tests/test_smoke.py`,`tests/test_property.py`,`tests/conftest.py` MODIFY.
- `README.md`,`CONTRIBUTING.md` MODIFY.

---

## R1: content.py — strict model + sanitize + parse_card (TDD)

**Files:** rewrite `src/henry_castillo/content.py` (model+parse only; fetch/cache in R2); rewrite `tests/test_content.py` (parse+sanitize only; fetch tests in R2).

- [ ] Step 1 — `tests/test_content.py` (full validation matrix + sanitize). Write tests first; key cases (use exact asserts):

```python
import unicodedata

import pytest

from henry_castillo import content
from henry_castillo.content import Card, CardError, Links, Profile, Project, Resume

_VALID = {
    "schema_version": 1,
    "profile": {
        "name": "Henry Castillo", "handle": "d0rbu",
        "tagline": "Interpretability and safety researcher",
        "about": "DRAFT — about.", "email": "henryandrecastillo@gmail.com",
        "links": {"github": "https://github.com/d0rbu", "blog": ""},
    },
    "projects": [
        {"name": "mc-dreamer", "blurb": "b", "url": "https://github.com/d0rbu/mc-dreamer", "tags": ["x"]},
    ],
    "resume": {"pdf": "", "experience": [{"org": "DRAFT —"}], "education": [{"school": "DRAFT —"}], "highlights": ["DRAFT —"]},
}


def test_parse_valid_minimal():
    c = content.parse_card(_VALID)
    assert isinstance(c, Card)
    assert c.schema_version == 1
    assert c.profile == Profile(
        name="Henry Castillo", handle="d0rbu",
        tagline="Interpretability and safety researcher",
        about="DRAFT — about.", email="henryandrecastillo@gmail.com",
        links=Links(github="https://github.com/d0rbu", blog=""),
    )
    assert c.projects == [Project(name="mc-dreamer", blurb="b",
                                  url="https://github.com/d0rbu/mc-dreamer", tags=["x"])]
    assert c.resume == Resume(pdf="", experience=[{"org": "DRAFT —"}],
                              education=[{"school": "DRAFT —"}], highlights=["DRAFT —"])


@pytest.mark.parametrize("mutate,msg_contains", [
    (lambda d: d.__setitem__("schema_version", 2), "schema_version"),
    (lambda d: d.pop("schema_version"), "schema_version"),
    (lambda d: d.__setitem__("schema_version", "1"), "schema_version"),
    (lambda d: d.__setitem__("profile", {}), "profile.name"),
    (lambda d: d["profile"].__setitem__("name", ""), "profile.name"),
    (lambda d: d["profile"].__setitem__("name", 5), "profile.name"),
    (lambda d: d["profile"].pop("handle"), "profile.handle"),
    (lambda d: d["profile"].pop("tagline"), "profile.tagline"),
    (lambda d: d["profile"].pop("about"), "profile.about"),
    (lambda d: d["profile"].pop("email"), "profile.email"),
    (lambda d: d["profile"].__setitem__("links", {}), "links.github"),
    (lambda d: d["profile"]["links"].__setitem__("github", ""), "links.github"),
    (lambda d: d["profile"]["links"].pop("blog"), "links.blog"),
    (lambda d: d["profile"]["links"].__setitem__("blog", 7), "links.blog"),
    (lambda d: d.__setitem__("projects", []), "projects"),
    (lambda d: d.__setitem__("projects", "x"), "projects"),
    (lambda d: d["projects"].__setitem__(0, {"name": "n"}), "projects[0].blurb"),
    (lambda d: d["projects"][0].__setitem__("tags", "x"), "projects[0].tags"),
    (lambda d: d["projects"][0]["tags"].__setitem__(0, 1), "projects[0].tags"),
    (lambda d: d.__setitem__("resume", {}), "resume.pdf"),
    (lambda d: d["resume"].__setitem__("experience", "x"), "resume.experience"),
    (lambda d: d["resume"].__setitem__("highlights", [1]), "resume.highlights"),
    (lambda d: d.clear(), "card"),
])
def test_parse_invalid_raises_carderror_with_path(mutate, msg_contains):
    import copy
    d = copy.deepcopy(_VALID)
    mutate(d)
    with pytest.raises(CardError) as ei:
        content.parse_card(d)
    assert msg_contains in str(ei.value)


@pytest.mark.parametrize("bad", [None, [], "x", 5, 1.0, True])
def test_parse_non_dict_root(bad):
    with pytest.raises(CardError):
        content.parse_card(bad)


def test_sanitize_strips_cc_except_nl_tab():
    assert content._sanitize("a\x1b[31mX\x1b[0m\x07b\x00\x9bc\nd\te") == "a[31mX[0mbc\nd\te"
    # NOTE: ESC removed (Cc); residual "[31m" text remains (acceptable per spec §5).
    assert content._sanitize("plain") == "plain"


@pytest.mark.parametrize("cp", list(range(0x00, 0x100)))
def test_sanitize_exhaustive_latin1(cp):
    ch = chr(cp)
    out = content._sanitize(ch)
    if ch in "\n\t":
        assert out == ch
    elif unicodedata.category(ch) == "Cc":
        assert out == ""
    else:
        assert out == ch


def test_parse_sanitizes_all_strings():
    import copy
    d = copy.deepcopy(_VALID)
    d["profile"]["name"] = "Henry\x1bCastillo"
    d["projects"][0]["blurb"] = "b\x07x"
    d["resume"]["highlights"] = ["h\x9bi"]
    d["resume"]["experience"] = [{"role": "r\x00x"}]
    c = content.parse_card(d)
    assert c.profile.name == "HenryCastillo"
    assert c.projects[0].blurb == "bx"
    assert c.resume.highlights == ["hi"]
    assert c.resume.experience == [{"role": "rx"}]


def test_dataclasses_have_no_defaults():
    import dataclasses
    for dc in (Resume, Links, Profile, Project, Card):
        for f in dataclasses.fields(dc):
            assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING, f
```

- [ ] Step 2 — run, expect fail (no `parse_card`/new model).
- [ ] Step 3 — rewrite `src/henry_castillo/content.py` model+parse region:

```python
"""Strict, fail-fast card model + parser. No defaults, no fallbacks."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


class CardError(Exception):
    """Raised when card data is missing/malformed. Message names the path."""


@dataclass(frozen=True)
class Resume:
    pdf: str
    experience: list[dict]
    education: list[dict]
    highlights: list[str]


@dataclass(frozen=True)
class Links:
    github: str
    blog: str


@dataclass(frozen=True)
class Profile:
    name: str
    handle: str
    tagline: str
    about: str
    email: str
    links: Links


@dataclass(frozen=True)
class Project:
    name: str
    blurb: str
    url: str
    tags: list[str]


@dataclass(frozen=True)
class Card:
    schema_version: int
    profile: Profile
    projects: list[Project]
    resume: Resume


SCHEMA_VERSION = 1


def _sanitize(value: str) -> str:
    return "".join(
        c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc"
    )


def _sanitize_json(obj: object) -> object:
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {_sanitize_json(k): _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    return obj


def _req_str(d: object, path: str) -> str:
    if not isinstance(d, dict):
        raise CardError(f"{path}: parent is not an object")
    key = path.rsplit(".", 1)[-1]
    v = d.get(key)
    if not isinstance(v, str) or not _sanitize(v).strip() == "" and not isinstance(v, str):
        raise CardError(f"{path}: expected non-empty string")
    if not isinstance(v, str) or v == "":
        raise CardError(f"{path}: expected non-empty string")
    return _sanitize(v)


def _opt_str(d: dict, key: str, path: str) -> str:
    if key not in d or not isinstance(d[key], str):
        raise CardError(f"{path}: expected string (use \"\" if none)")
    return _sanitize(d[key])


def parse_card(data: object) -> Card:
    if not isinstance(data, dict):
        raise CardError("card: root is not an object")
    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise CardError(
            f"schema_version: expected {SCHEMA_VERSION}, got {sv!r}"
            " — update henry-castillo"
        )
    p = data.get("profile")
    if not isinstance(p, dict):
        raise CardError("profile: missing or not an object (profile.name)")
    lk = p.get("links")
    if not isinstance(lk, dict):
        raise CardError("links.github: profile.links missing or not an object")
    links = Links(github=_req_str(lk, "links.github"),
                  blog=_opt_str(lk, "blog", "links.blog"))
    profile = Profile(
        name=_req_str(p, "profile.name"),
        handle=_req_str(p, "profile.handle"),
        tagline=_req_str(p, "profile.tagline"),
        about=_req_str(p, "profile.about"),
        email=_req_str(p, "profile.email"),
        links=links,
    )
    raw_projects = data.get("projects")
    if not isinstance(raw_projects, list) or not raw_projects:
        raise CardError("projects: expected a non-empty list")
    projects: list[Project] = []
    for i, it in enumerate(raw_projects):
        if not isinstance(it, dict):
            raise CardError(f"projects[{i}]: not an object")
        tags = it.get("tags")
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise CardError(f"projects[{i}].tags: expected list[str]")
        projects.append(Project(
            name=_req_str(it, f"projects[{i}].name"),
            blurb=_opt_str(it, "blurb", f"projects[{i}].blurb"),
            url=_req_str(it, f"projects[{i}].url"),
            tags=[_sanitize(t) for t in tags],
        ))
    r = data.get("resume")
    if not isinstance(r, dict):
        raise CardError("resume.pdf: resume missing or not an object")
    exp = r.get("experience")
    edu = r.get("education")
    hi = r.get("highlights")
    if not isinstance(exp, list) or not all(isinstance(x, dict) for x in exp):
        raise CardError("resume.experience: expected list[object]")
    if not isinstance(edu, list) or not all(isinstance(x, dict) for x in edu):
        raise CardError("resume.education: expected list[object]")
    if not isinstance(hi, list) or not all(isinstance(x, str) for x in hi):
        raise CardError("resume.highlights: expected list[str]")
    resume = Resume(
        pdf=_opt_str(r, "pdf", "resume.pdf"),
        experience=[_sanitize_json_dict(x) for x in exp],
        education=[_sanitize_json_dict(x) for x in edu],
        highlights=[_sanitize(x) for x in hi],
    )
    return Card(schema_version=sv, profile=profile, projects=projects, resume=resume)


def _sanitize_json_dict(x: dict) -> dict:
    return {_sanitize_json(k): _sanitize_json(v) for k, v in x.items()}
```

NOTE for implementer: clean up `_req_str` — the intended logic is simply: value must be a `str` and, after `_sanitize`, non-empty (`.strip()` non-empty? No — must be non-empty exactly; spec: required strings non-empty). Implement `_req_str` as: `if not isinstance(v, str) or v == "": raise CardError(...)` then `return _sanitize(v)`. (The draft above has a deliberately-broken redundant condition for you to simplify to exactly that. Required = non-empty string; `links.blog`/`resume.pdf`/`projects[].blurb` use `_opt_str` allowing `""`.) Ensure ty-clean and ruff-clean; `cast` only if mirroring an existing idiom.

- [ ] Step 4 — run `uv run pytest tests/test_content.py -q`; iterate to green; full gate. Commit:
```
git add src/henry_castillo/content.py tests/test_content.py
git commit -m "feat: strict no-default card model + parser + regex-free sanitize"
```

---

## R2: content.py — fetch + cache + load_card (TDD)

**Files:** extend `src/henry_castillo/content.py`; extend `tests/test_content.py`.

- [ ] Step 1 — tests (injected fetcher + tmp cache + real localhost for `_default_fetch`):

```python
import json as _json

import henry_castillo.content as C


def _doc_bytes(d=None):
    return _json.dumps(d if d is not None else _VALID).encode()


def test_load_card_fetch_success_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_cache_path", lambda: tmp_path / "card.json")
    got = C.load_card(fetch=lambda url: _doc_bytes())
    assert isinstance(got, C.Card)
    assert (tmp_path / "card.json").read_bytes() == _doc_bytes()


def test_load_card_fetch_fail_uses_cache(tmp_path, monkeypatch):
    cp = tmp_path / "card.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(C, "_cache_path", lambda: cp)

    def boom(url):
        raise OSError("offline")

    assert isinstance(C.load_card(fetch=boom), C.Card)


def test_load_card_invalid_fetch_valid_cache(tmp_path, monkeypatch):
    cp = tmp_path / "card.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(C, "_cache_path", lambda: cp)
    got = C.load_card(fetch=lambda u: b"{not json")
    assert isinstance(got, C.Card)
    assert cp.read_bytes() == _doc_bytes()  # bad fetch did NOT overwrite cache


def test_load_card_fetch_fail_no_cache_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_cache_path", lambda: tmp_path / "nope.json")
    with pytest.raises(C.CardError):
        C.load_card(fetch=lambda u: (_ for _ in ()).throw(OSError()))


def test_load_card_invalid_fetch_invalid_cache_raises(tmp_path, monkeypatch):
    cp = tmp_path / "card.json"
    cp.write_bytes(b"garbage")
    monkeypatch.setattr(C, "_cache_path", lambda: cp)
    with pytest.raises(C.CardError):
        C.load_card(fetch=lambda u: b"also garbage")


def test_card_url_env_override(monkeypatch):
    monkeypatch.setenv("HENRY_CASTILLO_CARD_URL", "https://example.invalid/x.json")
    assert C._card_url() == "https://example.invalid/x.json"
    monkeypatch.delenv("HENRY_CASTILLO_CARD_URL", raising=False)
    assert C._card_url() == "https://d0rbu.github.io/d0rbu/data/card.json"


def test_default_fetch_real_localhost(tmp_path):
    import http.server, socketserver, threading, functools
    body = _doc_bytes()
    d = tmp_path / "srv"
    d.mkdir()
    (d / "card.json").write_bytes(body)
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as srv:
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            assert C._default_fetch(f"http://127.0.0.1:{port}/card.json") == body
        finally:
            srv.shutdown()
            t.join()


def test_default_fetch_rejects_non_http(monkeypatch):
    with pytest.raises(OSError):
        C._default_fetch("file:///etc/passwd")
```

- [ ] Step 2 — run, expect fail.
- [ ] Step 3 — add to `content.py`:

```python
import json
import os
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

_CARD_URL = "https://d0rbu.github.io/d0rbu/data/card.json"
_TIMEOUT = 3.0
_MAX_BYTES = 256 * 1024


def _card_url() -> str:
    return os.environ.get("HENRY_CASTILLO_CARD_URL") or _CARD_URL


def _cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base and os.path.isabs(base) else Path.home() / ".cache"
    return root / "henry-castillo" / "card.json"


def _default_fetch(url: str) -> bytes:
    if not url.lower().startswith(("http://", "https://")):
        raise OSError(f"refusing non-HTTP(S) URL: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": "henry-castillo"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 - scheme checked above
        return resp.read(_MAX_BYTES + 1)[:_MAX_BYTES]


def _write_cache(raw: bytes) -> None:
    cp = _cache_path()
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(cp.parent))
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        os.replace(tmp, cp)
    except OSError:
        pass  # cache is best-effort; not fatal


def _parse_bytes(raw: bytes) -> Card:
    return parse_card(json.loads(raw.decode("utf-8")))


def load_card(*, fetch: Callable[[str], bytes] | None = None) -> Card:
    fetch = fetch or _default_fetch
    fetched: bytes | None = None
    try:
        fetched = fetch(_card_url())
        card = _parse_bytes(fetched)
    except (OSError, ValueError, CardError):
        card = None
    else:
        _write_cache(fetched)
        return card
    cp = _cache_path()
    try:
        return _parse_bytes(cp.read_bytes())
    except (OSError, ValueError, CardError) as e:
        raise CardError(
            "no usable profile data (fetch failed and no valid cache)"
        ) from e
```

Implementer: ensure `urlopen` is acceptable to zizmor/ruff (scheme is validated; add the minimal `# noqa`/nosec only if the repo's existing `update.py` does — MATCH `update.py`'s exact urllib pattern/lint-suppression idiom; do not introduce a new suppression style). `RecursionError` from `json.loads` deep nesting: include `RecursionError` in the `except` of `_parse_bytes` callers (mirror M2 hardening) — i.e. catch `(OSError, ValueError, CardError, RecursionError)` in `load_card`. Keep `_cache_path` mirroring `update.py`'s XDG logic exactly (reuse/extract if `update.py` already has identical logic — DRY, but do NOT modify `update.py`).

- [ ] Step 4 — green + full gate. Commit `src/henry_castillo/content.py tests/test_content.py`: `feat: remote fetch + atomic cache + fail-fast load_card`.

---

## R3: `_log.py` — loguru (pinned runtime dep) (TDD)

**Files:** `pyproject.toml`, `uv.lock`, NEW `src/henry_castillo/_log.py`, NEW `tests/test_log.py`.

- [ ] Step 1 — pick pinned loguru: `python3 -c "import json,urllib.request;d=json.load(urllib.request.urlopen('https://pypi.org/pypi/loguru/json'));import datetime;r=[(v,x[0]['upload_time_iso_8601']) for v,x in d['releases'].items() if x and not x[0].get('yanked') and '-' not in v];r=[a for a in r if a[1]<='2026-05-12T23:59:59'];r.sort(key=lambda a:a[1]);print(r[-1])"`. Pin EXACT `loguru==<V>` in `[project.dependencies]` (NOT a dev group — it is runtime). `uv lock`; `uv run python scripts/check_min_dependency_age.py --skip-npm` MUST rc 0 (loguru is a NEW runtime dep, delta-vs-origin/main, must be ≥7d; iterate to an older version if flagged). Confirm `uv lock --locked` rc 0.
- [ ] Step 2 — `tests/test_log.py`:

```python
import importlib

from henry_castillo import _log


def test_logger_silent_by_default(capsys):
    _log.configure(debug=False)
    _log.logger.error("should-not-appear")
    out = capsys.readouterr()
    assert "should-not-appear" not in out.err and "should-not-appear" not in out.out


def test_logger_emits_on_debug(capsys):
    _log.configure(debug=True)
    _log.logger.error("diag-msg")
    err = capsys.readouterr().err
    assert "diag-msg" in err
    _log.configure(debug=False)  # restore


def test_debug_enabled_via_env(monkeypatch):
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "1")
    assert _log.debug_enabled(cli_flag=False) is True
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "0")
    assert _log.debug_enabled(cli_flag=False) is False
    monkeypatch.delenv("HENRY_CASTILLO_DEBUG", raising=False)
    assert _log.debug_enabled(cli_flag=False) is False
    assert _log.debug_enabled(cli_flag=True) is True


def test_module_import_is_silent(capsys):
    importlib.reload(_log)
    _log.logger.info("x")
    assert capsys.readouterr().err == ""
```

- [ ] Step 3 — `src/henry_castillo/_log.py`:

```python
"""loguru wiring: silent by default; stderr only in debug."""

from __future__ import annotations

import os
import sys

from loguru import logger

logger.remove()  # silence loguru's default stderr sink at import

_FALSEY = {"", "0", "false", "no", "off"}
_sink_id: int | None = None


def debug_enabled(*, cli_flag: bool) -> bool:
    if cli_flag:
        return True
    val = os.environ.get("HENRY_CASTILLO_DEBUG")
    return val is not None and val.strip().lower() not in _FALSEY


def configure(*, debug: bool) -> None:
    global _sink_id
    if _sink_id is not None:
        logger.remove(_sink_id)
        _sink_id = None
    if debug:
        _sink_id = logger.add(sys.stderr, level="DEBUG")


__all__ = ["configure", "debug_enabled", "logger"]
```

- [ ] Step 4 — green + full gate (dependency-age guard MUST be green with pinned loguru). Commit `pyproject.toml uv.lock src/henry_castillo/_log.py tests/test_log.py`: `feat: loguru logging, silent unless --debug (pinned runtime dep)`.

---

## R4: render.py — Blog rename + required-field model (TDD)

**Files:** `src/henry_castillo/render.py`, `tests/test_render.py`.

- [ ] Tests then code. Changes: helpers/sections operate on the new required-field dataclasses (`Card`/`Profile`/`Project`/`Resume`/`Links`); `substack`→`blog` (panel title "Blog"; `blog_url(profile)` returns `profile.links.blog or None`; if `""` → None → "Blog not configured yet" panel); `SECTIONS` titles `["About","Projects","Résumé","Contact","Blog"]`; `banner` uses `profile.name` directly (no `or "henry-castillo"`); keep all content wrapped in `rich.text.Text`. The empty-`about`/empty-`resume` graceful branches are GONE (validation guarantees non-empty about; résumé fields may be DRAFT strings but present → render them; the "No résumé yet" path is removed since resume is always present — but DRAFT placeholder text renders fine). Provide full test code asserting: blog set→panel shows url; blog ""→"not configured"; banner shows name; sections order; render_all dumps all five; markup-literal regression retained. Commit: `feat: Blog section (was Substack); render the strict card model`.

---

## R5: failure_ui.py — #6 no-data screen + countdown (TDD)

**Files:** NEW `src/henry_castillo/failure_ui.py`, NEW `tests/test_failure_ui.py`.

- [ ] Step 1 — tests (inject `wait_for_keypress`, `open_url`, `console`, `sleep`):

```python
import io

from rich.console import Console

from henry_castillo import failure_ui as F


def _con():
    b = io.StringIO()
    return Console(file=b, width=80, no_color=True), b


def test_non_tty_prints_stderr_and_returns_1(monkeypatch, capsys):
    rc = F.show_no_data(
        "boom", url="https://d0rbu.github.io/d0rbu/", is_tty=False,
        console=_con()[0], wait_for_keypress=lambda _t: True,
        open_url=lambda _u: None, sleep=lambda _s: None,
    )
    assert rc == 1
    assert "boom" in capsys.readouterr().err


def test_tty_keypress_exits_without_opening():
    console, buf = _con()
    opened = []
    rc = F.show_no_data(
        "boom", url="U", is_tty=True, console=console,
        wait_for_keypress=lambda _t: True, open_url=opened.append,
        sleep=lambda _s: None,
    )
    assert rc == 0 and opened == [] and "boom" in buf.getvalue()


def test_tty_timeout_opens_url():
    console, buf = _con()
    opened = []
    seq = iter([False, False, False, False, False])
    rc = F.show_no_data(
        "boom", url="U", is_tty=True, console=console,
        wait_for_keypress=lambda _t: next(seq), open_url=opened.append,
        sleep=lambda _s: None,
    )
    assert rc == 0 and opened == ["U"]
    assert "5" in buf.getvalue() and "1" in buf.getvalue()  # countdown shown


def test_default_wait_for_keypress_via_pty():
    import os, time
    m, s = os.openpty()
    try:
        # no input within timeout -> False
        assert F._default_wait_for_keypress(0.05, stream_fd=s) is False
        os.write(m, b"x")
        time.sleep(0.01)
        assert F._default_wait_for_keypress(1.0, stream_fd=s) is True
    finally:
        os.close(m)
        os.close(s)
```

- [ ] Step 3 — `failure_ui.py`:

```python
"""Friendly 'no usable data' screen with a press-any-key / countdown."""

from __future__ import annotations

import select
import sys
import termios
import tty
from collections.abc import Callable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

_COUNTDOWN = 5


def _default_wait_for_keypress(timeout: float, *, stream_fd: int | None = None) -> bool:
    fd = sys.stdin.fileno() if stream_fd is None else stream_fd
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        r, _, _ = select.select([fd], [], [], timeout)
        return bool(r)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _default_open_url(url: str) -> None:
    import webbrowser

    webbrowser.open(url)


def show_no_data(
    message: str,
    *,
    url: str,
    is_tty: bool,
    console: Console,
    wait_for_keypress: Callable[[float], bool] | None = None,
    open_url: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> int:
    body = Text(
        f"{message}\n\nTry: uvx --refresh henry-castillo  (or update the "
        "package).\nIf this persists, contact henryandrecastillo@gmail.com.",
    )
    if not is_tty:
        print(body.plain, file=sys.stderr)
        return 1
    wait_for_keypress = wait_for_keypress or _default_wait_for_keypress
    open_url = open_url or _default_open_url
    sleep = sleep or __import__("time").sleep
    console.print(Panel(body, title="henry-castillo", border_style="red"))
    for n in range(_COUNTDOWN, 0, -1):
        console.print(Text(f"Opening {url} in {n}…  (press any key to exit)",
                            style="dim"))
        if wait_for_keypress(1.0):
            return 0
        sleep(0)
    open_url(url)
    return 0
```

Implementer: ensure 100% — every branch (non-tty; tty keypress at each iteration; tty timeout→open) is covered by the provided tests; `_default_wait_for_keypress` covered for real via the pty test (both timeout-False and key-True). `sleep(0)` exists only so the seam is injectable/covered; if ruff/ty objects, replace with a no-op `sleep` parameter usage that is still covered. Keep `Text`-wrapped. Commit: `feat: guided no-data screen with countdown / press-any-key`.

---

## R6: tui.py — Demos (under construction) + Blog open + update badge (TDD)

**Files:** `src/henry_castillo/tui.py`, `tests/test_tui.py`.

- [ ] `_LAB_LOCKED`→`_DEMOS = "Demos (under construction)"`; menu entry renders that; when an injected `update_available: bool` (derived in __main__ from the preserved `update.check_for_update`) is True, the Demos line/panel shows a badge Text "● newer henry-castillo available — run `henry-castillo --update`". `_SUBSTACK`→`_BLOG="Blog"`; selecting Blog → `render.blog_url(profile)`; open only if not None. `run(...)` signature gains `update_available: bool = False` (keyword) injected by __main__; default False keeps existing call sites/tests minimal. `SECTIONS` consumed from `render`. Provide full tests: Demos shows the message + badge when update_available, no badge when False; Blog opens `links.blog` when set, not when ""; Quit/None/unknown/EOF/KeyboardInterrupt paths retained. Commit: `feat: Demos (under construction) + update badge; Blog open`.

---

## R7: __main__.py — blog subcommand, --debug, load_card→failure dispatch (TDD)

**Files:** `src/henry_castillo/__main__.py`, `tests/test_cli.py`.

- [ ] Changes (preserve the update-flag contract verbatim):
  - imports: `from henry_castillo import _log, content, failure_ui, render, tui`.
  - argparse: add `--debug` (store_true). `substack` subparser → `blog`. Keep `about|projects --tag|resume/résumé --open|contact|blog` + the 4 update flags + `allow_abbrev=False` + NFC argv + `_harden_stream(sys.stdout)`.
  - very early in `main`: `_log.configure(debug=_log.debug_enabled(cli_flag=args.debug))`.
  - replace content loading: a single `try: card = content.load_card() except content.CardError as e: return failure_ui.show_no_data(str(e), url="https://d0rbu.github.io/d0rbu/", is_tty=sys.stdout.isatty(), console=console)` placed AFTER the version/update-flag short-circuits (so `--version`/`--update`/`--check-update` still work with no network — they must NOT call load_card), BEFORE section/tui dispatch. Use `card.profile`/`card.projects`/`card.resume` throughout (drop the separate load_profile/load_projects).
  - Demos badge: `update_available = bool(_update.check_for_update())` ONLY on the interactive (tty, no-subcommand) path, gated by the same throttle/env as `_maybe_notice` (reuse `_maybe_notice`'s decision; do not double-fetch — compute once); pass to `tui.run(..., update_available=...)`. Subcommand/pipe path unchanged re: notice.
  - `_render_section`: `blog` branch → `render.blog(card.profile)` then open `render.blog_url` if not None; `resume --open` uses `card.resume.pdf`; etc.
  - `_open_url` seam retained.
  - Full `tests/test_cli.py` updates: blog subcommand; `--debug` enables loguru (assert a `logger.error` is visible only with `--debug`); `CardError`→failure screen on tty (countdown seam injected) and non-tty (stderr, rc 1); `--version`/update flags STILL work with `content.load_card` monkeypatched to raise (proving they don't depend on data); all preserved flag/precedence/env/abbrev/alias/`python -m` tests still pass (adjust only data-dependent ones to inject a valid card via `monkeypatch.setattr(content,"load_card",lambda **k: _VALID_CARD)`). Commit: `feat: blog subcommand, --debug, load_card with guided failure`.

---

## R8: web/ site bootstrap + real card content (TDD)

**Files:** NEW `web/data/card.json`, `web/index.html`, `web/package.json`, `web/package-lock.json`, `web/build.mjs`; NEW `tests/test_web.py`.

- [ ] `web/data/card.json` = the real content: schema_version 1; profile name "Henry Castillo", handle "d0rbu", tagline "Interpretability and safety researcher", about "DRAFT — please edit." (+ a sentence of factual draft), email "henryandrecastillo@gmail.com", links.github "https://github.com/d0rbu", links.blog "" ; projects = exactly TWO: `{name:"mc-dreamer", blurb:"" or short factual, url:"https://github.com/d0rbu/mc-dreamer", tags:[…]}` and `{name:"nano-gpt-pretrain-steer", blurb:"DRAFT —", url:"https://github.com/Algorithmic-Alignment-Lab/nano-gpt-pretrain-steer", tags:[…]}`; resume pdf "", experience/education/highlights = explicit "DRAFT —" entries (valid, non-empty where required). 2-space JSON, passes `check-json`/pre-commit.
- [ ] `web/index.html` minimal placeholder: title, one line "Henry Castillo — see the CLI: `uvx henry-castillo`", link to `data/card.json` and the GitHub repo. (M3 replaces this.)
- [ ] `web/package.json`: name private, `"scripts": {"build": "node build.mjs"}`, no deps; `web/package-lock.json` (lockfileVersion 3, empty packages — `npm ci` works). `.npmrc`? root `.npmrc ignore-scripts=true` applies; fine. `web/build.mjs`: Node ESM that `mkdir -p dist/data`, copies `index.html`→`dist/`, `data/card.json`→`dist/data/`. (pages.yml runs `cd web && npm ci && npm run build`, uploads `web/dist`.)
- [ ] `tests/test_web.py`: read `web/data/card.json`, assert `content.parse_card(json.loads(...))` returns a `Card` with profile.name "Henry Castillo", exactly the 2 project URLs, schema_version == content.SCHEMA_VERSION; assert `web/build.mjs` referenced files exist; (optionally, if node available) run the build into a tmp dir and assert `dist/data/card.json` == source. Skip the node-run portion if node absent (pytest.skip) — but the parse_card conformance test is unconditional.
- [ ] Commit `web/ tests/test_web.py`: `feat(web): host card.json via Pages bootstrap (shared CLI/site source)`.

---

## R9: remove bundled content + migrate smoke/integration (TDD)

**Files:** delete `content/profile.json`,`content/projects.json`,`content/` ; `pyproject.toml` (drop the 2 force-include content lines — keep `py.typed`); `tests/test_smoke.py`,`tests/test_integration.py`,`tests/conftest.py`.

- [ ] `git rm content/profile.json content/projects.json`. Edit `pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` → remove the 2 `content/...` mappings (leave the `py.typed` mapping). `uv build` sanity: wheel no longer ships `_content`.
- [ ] conftest: add a `card_server` fixture (localhost http.server serving a valid card.json from a tmp dir) and/or a `valid_card`/`stub_load_card` fixture that monkeypatches `content.load_card`→a fixed valid `Card`. Migrate smoke/integration: the default non-tty run now needs a card source — set `HENRY_CASTILLO_CARD_URL` to the localhost fixture OR pre-seed the XDG cache (set `XDG_CACHE_HOME` to a tmp dir with a valid card.json) so the subprocess CLI gets data WITHOUT real network (conftest network block stays; subprocesses use the local server / seeded cache). Preserve: `--version` exact, alias byte-identity, `python -m` parity, exit codes, no-notice-in-pipe, stderr-empty (on success paths). Add an integration test: with NO card source and a tmp empty `XDG_CACHE_HOME`, a piped run prints the friendly message to stderr and exits 1 (the #6 non-tty path) — real subprocess.
- [ ] Full gate; commit: `refactor: drop bundled content; smoke/integration use remote/cache model`.

---

## R10: property tests for the new model (TDD)

**Files:** `tests/test_property.py`.

- [ ] Replace the old loader properties with: `parse_card` never returns a `Card` containing a control char or wrong-typed field for ANY structured input (build a Hypothesis strategy that seeds the real schema keys with `st.text()` values incl. control chars, plus arbitrary `_json` for the "never accepts invalid / raises CardError not some other exception" property); `_sanitize` invariants (idempotent, returns str, no Cc except \n\t — already exhaustive in R1, keep a property too); `blog_url` invariant; `load_card` never raises anything other than `CardError` for an arbitrary (fetched-or-cached) byte blob. Reuse the H7 lessons: seed schema keys so values actually flow through sanitization (no theater); assert mutation-killing (the reviewer will verify teeth). Commit: `test: property tests for strict card model + sanitize`.

---

## R11: coverage finalization + full local gate

- [ ] `uv run pytest --cov=henry_castillo --cov-report=term-missing -q` genuine 100% line+branch; zero pragmas. `uv run ruff check . && uv run ruff format --check . && uv run ty check`; `uv run pre-commit run --all-files`; `uv lock --locked`; `uvx zizmor --persona=pedantic --config .github/zizmor.yml .github/workflows`; `uv run python scripts/check_min_dependency_age.py --skip-npm` (loguru pinned ≥7d → rc 0); `uv run --python 3.10 ...` OK310; `make check`. Add focused tests only if a branch is uncovered (no pragmas). Commit only if tests added: `test: close coverage to genuine 100%`.

---

## R12: docs

- [ ] `README.md`: replace the offline/bundled wording — the CLI fetches a hosted card and caches it; works offline after first run; `HENRY_CASTILLO_CARD_URL` override; `--debug`; `Blog`/`Demos` in the usage block; aliases unchanged. `CONTRIBUTING.md`: the data lives at `web/data/card.json` deployed to GitHub Pages (edit & push to update — no release); the **one-time maintainer action**: repo Settings → Pages → Source = "GitHub Actions"; the gated-release note updated (confirm hosted content + Pages enabled + Trusted Publishing). Commit: `docs: document remote card model, Pages setup, --debug`.

---

## R13: push, CI green, final review, smoke (NOT merged)

- [ ] Full local gate. `git push`. `gh pr checks 3 --watch`. ALL 13 SUCCESS — fix-forward at root cause (test-only / pinned-version) MINIMALLY; never weaken; never merge; never touch the workflow beyond necessity; if a red is ambiguous/supply-chain → report. `gh pr view 3` → draft:false, OPEN, NOT merged. `origin/main` unchanged.
- [ ] Final whole-implementation review (capstone, independent): net diff vs the M2/hardening baseline coherent + conventional+trailered; spec honored; no M2-update-contract regression; the composed packaged-wheel works offline-after-cache; #6 flow real; property tests have teeth; genuine 100%; 13/13 CI; plan docs never committed; main untouched; PR Ready not merged.
- [ ] **Real-data/API smoke** (the user explicitly asked): build wheel; clean /tmp venv install; serve the REAL `web/data/card.json` via a localhost http.server; `HENRY_CASTILLO_CARD_URL=http://127.0.0.1:PORT/card.json henry-castillo …` — every subcommand/alias/interactive card; kill the server + clear cache → confirm cache works after one good fetch; empty cache + no server → the #6 stderr (pipe) and the pty countdown (tty, key vs timeout→open) for real; hit the **real PyPI** JSON for the update badge path; `--debug` shows loguru, default silent. Symlink `web/data/` into the smoke workspace as needed. (No ML models — `lab` deferred; note N/A.) Capture evidence.
- [ ] Report: PR URL, 13/13, the smoke evidence, the private-repo flag, the maintainer Pages action, gating, what changed; PR Ready+OPEN, NOT merged.

## Self-Review
Spec coverage: §2 contract→R1/R8; §3 model→R1; §4 fetch/cache→R2; §5 sanitize→R1(+R10 property); §6 UX→R5/R7; §7 loguru→R3/R7; §8 CLI(Blog/Demos/badge)→R4/R6/R7; §9 hosting→R8(+R12 doc, R13 maintainer action); §10 removals→R9; §11 testing→every task + R10/R13; §12 scope→R13. No gaps. Placeholders: the only "fill from concrete source" is R8 card content (factual draft, explicit) and R3's pinned-version registry query (concrete cmd). Type consistency: `Card/Profile/Project/Resume/Links`, `CardError`, `parse_card`, `load_card(fetch=)`, `_sanitize`, `_card_url`, `_cache_path`, `_default_fetch`, `blog_url`, `failure_ui.show_no_data(...)`, `_log.configure/debug_enabled/logger`, `tui.run(...,update_available=)` consistent across tasks. Note the deliberately-broken `_req_str` in R1 Step 3 has an explicit instruction to simplify to the exact intended logic.
