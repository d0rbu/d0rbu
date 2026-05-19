"""Pure ``rich`` renderers for each CLI section. No I/O, no network, no print.

Every function takes already-loaded content and returns a ``rich`` renderable
so it is trivially testable via ``rich.console.Console`` capture.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from henry_castillo.content import Card, CardProfile, CardProject


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


def render_all(console: Console, card: Card) -> None:
    """Render all sections to *console*."""
    console.print(banner(card.profile))
    for _name, fn in SECTIONS:
        console.print(fn(card))
