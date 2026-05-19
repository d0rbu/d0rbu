"""Typed, defensive loaders for the bundled content/*.json.

Resolves content from the packaged data dir (``henry_castillo/_content`` in an
installed wheel) and falls back to the repo-root ``content/`` directory for an
editable/development checkout. Never raises on missing or malformed content;
returns empty defaults so the CLI degrades gracefully offline.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import re
import tempfile
import unicodedata
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Protocol, cast


class _Resource(Protocol):
    """Structural type for a bundled-content handle (pathlib.Path or an
    importlib.resources Traversable both satisfy it)."""

    def is_file(self) -> bool: ...

    def read_text(self, encoding: str = ...) -> str: ...


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


def _packaged_resource(name: str) -> _Resource | None:
    """The bundled ``henry_castillo/_content/<name>`` as a resource handle, or
    ``None`` if it is not a readable packaged resource (dev checkout, or a
    loader without resource support). Zip-safe (works under zipimport)."""
    try:
        resource = files("henry_castillo") / "_content" / name
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


_CSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _sanitize(value: str) -> str:
    """Strip ANSI CSI sequences and C0/C1 control characters (Unicode
    category ``Cc``) except newline and tab, so terminal control/escape
    sequences embedded in content can never reach the terminal."""
    value = _CSI_RE.sub("", value)
    return "".join(c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc")


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


def _str(value: object) -> str:
    return _sanitize(value) if isinstance(value, str) else ""


def load_profile() -> Profile:
    data = _read_json("profile.json")
    if not isinstance(data, dict):
        return Profile()
    d: dict[str, object] = cast("dict[str, object]", data)
    contact = d.get("contact")
    if isinstance(contact, dict):
        cd: dict[str, object] = cast("dict[str, object]", contact)
        email: object = cd.get("email")
    else:
        email = None
    raw_links = d.get("links")
    links = (
        {
            _sanitize(k): _sanitize(v)
            for k, v in raw_links.items()
            if isinstance(k, str) and isinstance(v, str)
        }
        if isinstance(raw_links, dict)
        else {}
    )
    r = d.get("resume")
    if isinstance(r, dict):
        rd: dict[str, object] = cast("dict[str, object]", r)
        raw_exp = rd.get("experience")
        raw_edu = rd.get("education")
        raw_hi = rd.get("highlights")
        resume = Resume(
            pdf=_str(rd.get("pdf")),
            experience=cast(
                "list[dict]",
                [
                    _sanitize_json(x)
                    for x in cast("list[object]", raw_exp)
                    if isinstance(x, dict)
                ],
            )
            if isinstance(raw_exp, list)
            else [],
            education=cast(
                "list[dict]",
                [
                    _sanitize_json(x)
                    for x in cast("list[object]", raw_edu)
                    if isinstance(x, dict)
                ],
            )
            if isinstance(raw_edu, list)
            else [],
            highlights=[_sanitize(str(x)) for x in cast("list[object]", raw_hi)]
            if isinstance(raw_hi, list)
            else [],
        )
    else:
        resume = Resume()
    return Profile(
        name=_str(d.get("name")),
        handle=_str(d.get("handle")),
        tagline=_str(d.get("tagline")),
        about=_str(d.get("about")),
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
        it: dict[str, object] = cast("dict[str, object]", item)
        raw_tags = it.get("tags")
        projects.append(
            Project(
                name=_str(it.get("name")),
                blurb=_str(it.get("blurb")),
                url=_str(it.get("url")),
                tags=[_sanitize(t) for t in raw_tags if isinstance(t, str)]
                if isinstance(raw_tags, list)
                else [],
            )
        )
    return projects


# ---------------------------------------------------------------------------
# Strict remote-card model (additive — existing symbols above are unchanged)
# ---------------------------------------------------------------------------


class CardError(Exception):
    """Card data missing/malformed; message names the offending path."""


@dataclass(frozen=True)
class CardResume:
    pdf: str
    experience: list[dict]  # type: ignore[type-arg]
    education: list[dict]  # type: ignore[type-arg]
    highlights: list[str]


@dataclass(frozen=True)
class CardLinks:
    github: str
    blog: str


@dataclass(frozen=True)
class CardProfile:
    name: str
    handle: str
    tagline: str
    about: str
    email: str
    links: CardLinks


@dataclass(frozen=True)
class CardProject:
    name: str
    blurb: str
    url: str
    tags: list[str]


@dataclass(frozen=True)
class Card:
    schema_version: int
    profile: CardProfile
    projects: list[CardProject]
    resume: CardResume


SCHEMA_VERSION = 1
_MAX_JSON_DEPTH = 64


def _sanitize_strict(value: str) -> str:
    return "".join(c for c in value if c in "\n\t" or unicodedata.category(c) != "Cc")


def _sanitize_json_strict(obj: object, _depth: int = 0) -> object:
    if _depth > _MAX_JSON_DEPTH:
        raise CardError("resume: nested data too deeply nested")
    if isinstance(obj, str):
        return _sanitize_strict(obj)
    if isinstance(obj, dict):
        return {
            _sanitize_json_strict(k, _depth + 1): _sanitize_json_strict(v, _depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize_json_strict(v, _depth + 1) for v in obj]
    return obj


def _req(d: dict[str, object], parent_path: str, key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or v == "":
        raise CardError(f"{parent_path}.{key}: expected a non-empty string")
    return _sanitize_strict(v)


def _opt(d: dict[str, object], key: str, path: str) -> str:
    v = d.get(key)
    if not isinstance(v, str):
        raise CardError(f'{path}: expected a string (use "" if none)')
    return _sanitize_strict(v)


_CARD_REQUIRED_KEYS = {"schema_version", "profile", "projects", "resume"}


def _parse_profile(p: object) -> CardProfile:
    if not isinstance(p, dict):
        raise CardError("profile.name: profile is missing or not an object")
    pd: dict[str, object] = cast("dict[str, object]", p)
    name = _req(pd, "profile", "name")
    handle = _req(pd, "profile", "handle")
    tagline = _req(pd, "profile", "tagline")
    about = _req(pd, "profile", "about")
    email = _req(pd, "profile", "email")
    lk = pd.get("links")
    if not isinstance(lk, dict):
        raise CardError("links.github: profile.links missing or not an object")
    ld: dict[str, object] = cast("dict[str, object]", lk)
    links = CardLinks(
        github=_req(ld, "links", "github"),
        blog=_opt(ld, "blog", "links.blog"),
    )
    return CardProfile(
        name=name,
        handle=handle,
        tagline=tagline,
        about=about,
        email=email,
        links=links,
    )


def _parse_project(it: object, i: int) -> CardProject:
    if not isinstance(it, dict):
        raise CardError(f"projects[{i}]: not an object")
    itd: dict[str, object] = cast("dict[str, object]", it)
    tags = itd.get("tags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise CardError(f"projects[{i}].tags: expected list[str]")
    str_tags: list[str] = cast("list[str]", tags)
    return CardProject(
        name=_req(itd, f"projects[{i}]", "name"),
        blurb=_opt(itd, "blurb", f"projects[{i}].blurb"),
        url=_req(itd, f"projects[{i}]", "url"),
        tags=[_sanitize_strict(t) for t in str_tags],
    )


def _parse_resume(r: object) -> CardResume:
    if not isinstance(r, dict):
        raise CardError("resume: missing or not an object")
    rd: dict[str, object] = cast("dict[str, object]", r)
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
    return CardResume(
        pdf=_opt(rd, "pdf", "resume.pdf"),
        experience=[_sanitize_json_strict_dict(x) for x in exp_dicts],
        education=[_sanitize_json_strict_dict(x) for x in edu_dicts],
        highlights=[_sanitize_strict(x) for x in hi_strs],
    )


def parse_card(data: object) -> Card:
    if not isinstance(data, dict):
        raise CardError("card: root is not an object")
    dd: dict[str, object] = cast("dict[str, object]", data)
    if not _CARD_REQUIRED_KEYS.issubset(dd.keys()):
        raise CardError(
            f"card: missing required keys {_CARD_REQUIRED_KEYS - dd.keys()!r}"
        )
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
    return Card(
        schema_version=sv_int,
        profile=_parse_profile(dd.get("profile")),
        projects=[_parse_project(it, i) for i, it in enumerate(raw_projects)],
        resume=_parse_resume(dd.get("resume")),
    )


def _sanitize_json_strict_dict(x: dict) -> dict:
    return cast("dict[str, object]", _sanitize_json_strict(x, 0))


# ---------------------------------------------------------------------------
# Remote fetch + atomic cache + load_card (additive — all symbols above kept)
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
