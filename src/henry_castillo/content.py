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


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


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
            k: v
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
            experience=[x for x in cast("list[object]", raw_exp) if isinstance(x, dict)]
            if isinstance(raw_exp, list)
            else [],
            education=[x for x in cast("list[object]", raw_edu) if isinstance(x, dict)]
            if isinstance(raw_edu, list)
            else [],
            highlights=[str(x) for x in cast("list[object]", raw_hi)]
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
                tags=[t for t in raw_tags if isinstance(t, str)]
                if isinstance(raw_tags, list)
                else [],
            )
        )
    return projects
