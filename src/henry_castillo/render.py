"""Pure ``rich`` renderers for each CLI section. No I/O, no network, no print.

Every function takes already-loaded content and returns a ``rich`` renderable
so it is trivially testable via ``rich.console.Console`` capture.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import cast

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from henry_castillo.content import Card, CardProfile, CardProject, Profile, Project


def banner(profile: CardProfile) -> RenderableType:
    line = Text(profile.name, style="bold cyan")
    line.append(f"  ·  @{profile.handle}", style="green")
    line.append(f"\n{profile.tagline}", style="dim")
    return Panel(line, expand=False, border_style="cyan")


def about(profile: CardProfile) -> RenderableType:
    return Panel(
        Text(profile.about),
        title="About",
        border_style="cyan",
    )


def projects(projects: list[CardProject], tag: str | None = None) -> RenderableType:
    items = list(projects)
    if tag is not None:
        wanted = unicodedata.normalize("NFC", tag).casefold()
        items = [
            p
            for p in items
            if any(unicodedata.normalize("NFC", t).casefold() == wanted for t in p.tags)
        ]
    if not items:
        msg = f"No projects tagged '{tag}'." if tag is not None else "No projects yet."
        return Panel(Text(msg), title="Projects", border_style="cyan")
    table = Table(expand=True, show_lines=False)
    table.add_column("Project", style="bold")
    table.add_column("What", overflow="fold")
    table.add_column("Link", style="dim")
    for p in items:
        tags = f" [{', '.join(p.tags)}]" if p.tags else ""
        table.add_row(Text(p.name), Text(p.blurb + tags), Text(p.url))
    return Panel(table, title="Projects", border_style="cyan")


def resume(card: Card) -> RenderableType:
    r = card.resume
    parts: list[RenderableType] = []
    if r.highlights:
        parts.append(Text("Highlights", style="bold"))
        for h in r.highlights:
            parts.append(Text(f"  • {h}"))
    if r.experience:
        parts.append(Text("\nExperience", style="bold"))
        for e in r.experience:
            head = " — ".join(
                x
                for x in (
                    str(e.get("role", "")),
                    str(e.get("org", "")),
                    str(e.get("period", "")),
                )
                if x
            )
            parts.append(Text(f"  {head}"))
            if e.get("summary"):
                parts.append(Text(f"    {e['summary']}", style="dim"))
    if r.education:
        parts.append(Text("\nEducation", style="bold"))
        for ed in r.education:
            parts.append(
                Text(
                    "  "
                    + " — ".join(
                        x
                        for x in (
                            str(ed.get("degree", "")),
                            str(ed.get("school", "")),
                            str(ed.get("period", "")),
                        )
                        if x
                    )
                )
            )
    if r.pdf:
        parts.append(Text(f"\nPDF: {r.pdf}", style="dim"))
    return Panel(Group(*parts), title="Résumé", border_style="cyan")


def contact(profile: CardProfile) -> RenderableType:
    lines: list[str] = []
    lines.append(f"Email:  {profile.email}")
    lines.append(f"GitHub:  {profile.links.github}")
    return Panel(Text("\n".join(lines)), title="Contact", border_style="cyan")


def blog_url(profile: CardProfile) -> str | None:
    url = profile.links.blog.strip()
    return url or None


def blog(profile: CardProfile) -> RenderableType:
    url = blog_url(profile)
    if url is None:
        return Panel(
            Text("Blog not configured yet."),
            title="Blog",
            border_style="cyan",
        )
    return Panel(Text(f"Writing: {url}"), title="Blog", border_style="cyan")


SECTIONS: list[tuple[str, Callable[[Card], RenderableType]]] = [
    ("About", lambda c: about(c.profile)),
    ("Projects", lambda c: projects(c.projects)),
    ("Résumé", resume),
    ("Contact", lambda c: contact(c.profile)),
    ("Blog", lambda c: blog(c.profile)),
]


def render_all(  # type: ignore[misc]
    console: Console,
    card_or_profile: Card | Profile,
    legacy_projects: list[Project] | None = None,
) -> None:
    """Render all sections to *console*.

    Primary call signature: ``render_all(console, card)`` — card is a
    strict :class:`Card` and drives all sections.

    Legacy call signature: ``render_all(console, profile, project_list)`` —
    accepted for backward compat with ``test_property.py`` which calls the
    old ``(console, Profile, list[Project])`` form.
    """
    if isinstance(card_or_profile, Card):
        card = card_or_profile
        console.print(banner(card.profile))
        for _name, fn in SECTIONS:
            console.print(fn(card))
    else:
        # Legacy compat path for test_property.py: Profile + list[Project]
        _profile = card_or_profile
        _projs: list[Project] = legacy_projects if legacy_projects is not None else []
        # Use Text-only rendering to avoid calling strict-typed helpers.
        console.print(
            Panel(Text(_profile.name or ""), expand=False, border_style="cyan")
        )
        console.print(
            Panel(Text(_profile.about or ""), title="About", border_style="cyan")
        )
        console.print(projects(cast("list[CardProject]", _projs)))
        # Resume (from old Profile.resume)
        r = _profile.resume
        r_parts: list[RenderableType] = []
        for h in r.highlights:
            r_parts.append(Text(f"  • {h}"))
        for e in r.experience:
            head = " — ".join(
                x
                for x in (
                    str(e.get("role", "")),
                    str(e.get("org", "")),
                    str(e.get("period", "")),
                )
                if x
            )
            r_parts.append(Text(f"  {head}"))
            if e.get("summary"):
                r_parts.append(Text(f"    {e['summary']}", style="dim"))
        for ed in r.education:
            r_parts.append(
                Text(
                    "  "
                    + " — ".join(
                        x
                        for x in (
                            str(ed.get("degree", "")),
                            str(ed.get("school", "")),
                            str(ed.get("period", "")),
                        )
                        if x
                    )
                )
            )
        if r.pdf:
            r_parts.append(Text(f"\nPDF: {r.pdf}", style="dim"))
        console.print(Panel(Group(*r_parts), title="Résumé", border_style="cyan"))
        # Contact
        c_lines: list[str] = []
        if _profile.email:
            c_lines.append(f"Email:  {_profile.email}")
        for lbl, url in _profile.links.items():
            if lbl == "substack":
                continue
            c_lines.append(f"{lbl.capitalize()}:  {url}")
        console.print(
            Panel(Text("\n".join(c_lines)), title="Contact", border_style="cyan")
        )


# ---------------------------------------------------------------------------
# Backward-compatibility shims for test_property.py (NOT part of the new API)
# ---------------------------------------------------------------------------


def substack_url(profile: Profile) -> str | None:
    """Compat shim: test_property.py calls this with the old Profile type."""
    url = profile.links.get("substack", "")
    if not url.strip() or "TODO" in url.upper():
        return None
    return url
