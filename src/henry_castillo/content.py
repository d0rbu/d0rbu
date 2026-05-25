"""Strict remote-card model: fetch/cache, parse, and typed dataclasses.

The CLI fetches card.json from GitHub Pages and caches it locally under the
XDG cache directory.  ``load_card`` is the sole public entry point: it tries
the remote URL first, falls back to the on-disk cache, and raises
``CardError`` only when both are unavailable or malformed.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import tempfile
import unicodedata
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from packaging.version import InvalidVersion, Version


class CardError(Exception):
    """Card data missing/malformed; message names the offending path."""


@dataclass(frozen=True)
class Resume:
    pdf: str
    experience: list[dict]  # type: ignore[type-arg]
    education: list[dict]  # type: ignore[type-arg]
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
class Demo:
    name: str
    summary: str
    min_version: str


@dataclass(frozen=True)
class Card:
    schema_version: int
    profile: Profile
    projects: list[Project]
    resume: Resume
    demos: list[Demo]


SCHEMA_VERSION = 2
_MAX_JSON_DEPTH = 64


def _sanitize(value: str) -> str:
    return "".join(c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc")


def _sanitize_json(obj: object, _depth: int = 0) -> object:
    if _depth > _MAX_JSON_DEPTH:
        raise CardError("resume: nested data too deeply nested")
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {
            _sanitize_json(k, _depth + 1): _sanitize_json(v, _depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize_json(v, _depth + 1) for v in obj]
    return obj


def _sanitize_json_dict(x: dict) -> dict:
    return cast("dict[str, object]", _sanitize_json(x, 0))


def _req(d: dict[str, object], parent_path: str, key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or v == "":
        raise CardError(f"{parent_path}.{key}: expected a non-empty string")
    return _sanitize(v)


def _opt(d: dict[str, object], key: str, path: str) -> str:
    v = d.get(key)
    if not isinstance(v, str):
        raise CardError(f'{path}: expected a string (use "" if none)')
    return _sanitize(v)


_CARD_REQUIRED_KEYS = {"schema_version", "profile", "projects", "resume", "demos"}
_CARD_ALLOWED_KEYS = _CARD_REQUIRED_KEYS | {"$schema"}


def _reject_unknown(d: dict[str, object], allowed: set[str], path: str) -> None:
    extra = set(d.keys()) - allowed
    if extra:
        raise CardError(f"{path}: unexpected key(s): {sorted(extra)}")


def _parse_profile(p: object) -> Profile:
    if not isinstance(p, dict):
        raise CardError("profile.name: profile is missing or not an object")
    pd: dict[str, object] = cast("dict[str, object]", p)
    _reject_unknown(
        pd, {"name", "handle", "tagline", "about", "email", "links"}, "profile"
    )
    name = _req(pd, "profile", "name")
    handle = _req(pd, "profile", "handle")
    tagline = _req(pd, "profile", "tagline")
    about = _req(pd, "profile", "about")
    email = _req(pd, "profile", "email")
    lk = pd.get("links")
    if not isinstance(lk, dict):
        raise CardError("links.github: profile.links missing or not an object")
    ld: dict[str, object] = cast("dict[str, object]", lk)
    _reject_unknown(ld, {"github", "blog"}, "profile.links")
    links = Links(
        github=_req(ld, "links", "github"),
        blog=_opt(ld, "blog", "links.blog"),
    )
    return Profile(
        name=name,
        handle=handle,
        tagline=tagline,
        about=about,
        email=email,
        links=links,
    )


def _parse_project(it: object, i: int) -> Project:
    if not isinstance(it, dict):
        raise CardError(f"projects[{i}]: not an object")
    itd: dict[str, object] = cast("dict[str, object]", it)
    _reject_unknown(itd, {"name", "blurb", "url", "tags"}, f"projects[{i}]")
    tags = itd.get("tags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise CardError(f"projects[{i}].tags: expected list[str]")
    str_tags: list[str] = cast("list[str]", tags)
    return Project(
        name=_req(itd, f"projects[{i}]", "name"),
        blurb=_opt(itd, "blurb", f"projects[{i}].blurb"),
        url=_req(itd, f"projects[{i}]", "url"),
        tags=[_sanitize(t) for t in str_tags],
    )


def _parse_resume(r: object) -> Resume:
    if not isinstance(r, dict):
        raise CardError("resume: missing or not an object")
    rd: dict[str, object] = cast("dict[str, object]", r)
    _reject_unknown(rd, {"pdf", "experience", "education", "highlights"}, "resume")
    exp = rd.get("experience")
    edu = rd.get("education")
    hi = rd.get("highlights")
    if not isinstance(exp, list) or not all(isinstance(x, dict) for x in exp):
        raise CardError("resume.experience: expected list of objects")
    if not isinstance(edu, list) or not all(isinstance(x, dict) for x in edu):
        raise CardError("resume.education: expected list of objects")
    if not isinstance(hi, list) or not all(isinstance(x, str) for x in hi):
        raise CardError("resume.highlights: expected list of strings")
    exp_dicts: list[dict[str, object]] = cast("list[dict[str, object]]", exp)
    edu_dicts: list[dict[str, object]] = cast("list[dict[str, object]]", edu)
    hi_strs: list[str] = cast("list[str]", hi)
    return Resume(
        pdf=_opt(rd, "pdf", "resume.pdf"),
        experience=[_sanitize_json_dict(x) for x in exp_dicts],
        education=[_sanitize_json_dict(x) for x in edu_dicts],
        highlights=[_sanitize(x) for x in hi_strs],
    )


def _parse_demo(it: object, i: int) -> Demo:
    if not isinstance(it, dict):
        raise CardError(f"demos[{i}]: expected an object")
    itd: dict[str, object] = cast("dict[str, object]", it)
    _reject_unknown(itd, {"name", "summary", "min_version"}, f"demos[{i}]")
    name = _req(itd, f"demos[{i}]", "name")
    summary = _req(itd, f"demos[{i}]", "summary")
    mv = _req(itd, f"demos[{i}]", "min_version")
    try:
        Version(mv)
    except InvalidVersion:
        raise CardError(f"demos[{i}].min_version: not a valid version") from None
    return Demo(name=name, summary=summary, min_version=mv)


def parse_card(data: object) -> Card:
    if not isinstance(data, dict):
        raise CardError("card: root is not an object")
    dd: dict[str, object] = cast("dict[str, object]", data)
    if not _CARD_REQUIRED_KEYS.issubset(dd.keys()):
        raise CardError(
            f"card: missing required keys {_CARD_REQUIRED_KEYS - dd.keys()!r}"
        )
    _reject_unknown(dd, _CARD_ALLOWED_KEYS, "card")
    sv = dd.get("schema_version")
    if not isinstance(sv, int) or isinstance(sv, bool) or sv != SCHEMA_VERSION:
        raise CardError(
            f"schema_version: expected {SCHEMA_VERSION}, got {sv!r}"
            " — update henry-castillo"
        )
    # sv == SCHEMA_VERSION (int) after the guard above
    sv_int: int = cast("int", sv)
    raw_projects = dd.get("projects")
    if not isinstance(raw_projects, list) or not raw_projects:
        raise CardError("projects: expected a non-empty list")
    raw_demos = dd.get("demos")
    if not isinstance(raw_demos, list):
        raise CardError("demos: expected a list")
    return Card(
        schema_version=sv_int,
        profile=_parse_profile(dd.get("profile")),
        projects=[_parse_project(it, i) for i, it in enumerate(raw_projects)],
        resume=_parse_resume(dd.get("resume")),
        demos=[_parse_demo(it, i) for i, it in enumerate(raw_demos)],
    )


def new_demos(card: Card, *, current: str) -> list[Demo]:
    """Demos whose min_version is strictly greater than `current`.

    ``current`` must be a valid PEP 440 version string; raises ``CardError``
    otherwise.
    """
    try:
        cur = Version(current)
    except InvalidVersion:
        raise CardError(f"new_demos: invalid current version {current!r}") from None
    return [d for d in card.demos if Version(d.min_version) > cur]


# ---------------------------------------------------------------------------
# Remote fetch + atomic cache + load_card
# ---------------------------------------------------------------------------

_CARD_URL = "https://d0rbu.github.io/d0rbu/data/card.json"
_TIMEOUT = 3.0
_MAX_BYTES = 256 * 1024


def _card_url() -> str:
    return os.environ.get("HENRY_CASTILLO_CARD_URL") or _CARD_URL


def _cache_path() -> Path:
    """Per-user cache file for the fetched card, mirroring update.py XDG logic."""
    base = os.environ.get("XDG_CACHE_HOME")
    if not base or not Path(base).is_absolute():
        base = str(Path.home() / ".cache")
    return Path(base) / "henry-castillo" / "card.json"


# Scheme is restricted to http(s); urllib's redirect handler refuses non-http(s)
# redirects. The canonical URL is the author's HTTPS GitHub Pages constant; the env
# override is a deliberate user choice — so SSRF surface is acceptable-by-design.
def _default_fetch(url: str) -> bytes:
    if not url.lower().startswith(("http://", "https://")):
        raise OSError(f"refusing non-HTTP(S) URL: {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "henry-castillo"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as resp:  # noqa: S310
        return resp.read(_MAX_BYTES)


def _write_cache(raw: bytes) -> None:
    path = _cache_path()
    fd = -1
    tmp: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent))
        with os.fdopen(fd, "wb") as fh:
            fd = -1  # fdopen now owns the fd
            fh.write(raw)
        Path(tmp).replace(path)
        tmp = None  # promoted; do not unlink
    except (OSError, ValueError):
        return  # cache is best-effort; never fatal
    finally:
        if fd != -1:
            with contextlib.suppress(OSError):
                os.close(fd)
        if tmp is not None:
            with contextlib.suppress(OSError):
                Path(tmp).unlink()


def _parse_bytes(raw: bytes) -> Card:
    if not isinstance(raw, bytes):
        raise CardError("fetched body is not bytes")
    return parse_card(json.loads(raw.decode("utf-8")))


def load_card(*, fetch: Callable[[str], bytes] | None = None) -> Card:
    do_fetch = fetch or _default_fetch
    fetched: bytes | None = None
    try:
        fetched = do_fetch(_card_url())
        card = _parse_bytes(fetched)
    except (OSError, ValueError, CardError, RecursionError, http.client.HTTPException):
        card = None
    if card is not None and fetched is not None:
        _write_cache(fetched)
        return card
    try:
        return _parse_bytes(_cache_path().read_bytes())
    except (
        OSError,
        ValueError,
        CardError,
        RecursionError,
        http.client.HTTPException,
    ) as exc:
        raise CardError(
            "no usable profile data: fetch failed and no valid cache"
        ) from exc
