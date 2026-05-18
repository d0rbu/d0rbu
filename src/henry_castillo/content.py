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
from typing import cast


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
    packaged = _packaged_content()
    base = packaged if packaged.is_dir() else _content_dir()
    try:
        return json.loads((base / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
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
