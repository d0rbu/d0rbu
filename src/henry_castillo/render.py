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
    return Panel(
        body or "No bio yet — set `about` in content/profile.json.",
        title="About",
        border_style="cyan",
    )


def projects(projects: Sequence[Project], tag: str | None = None) -> RenderableType:
    items = list(projects)
    if tag is not None:
        wanted = tag.casefold()
        items = [p for p in items if any(t.casefold() == wanted for t in p.tags)]
    if not items:
        msg = (
            f"No projects tagged '{tag}'."
            if tag is not None
            else "No projects yet — add to content/projects.json."
        )
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
        return Panel(
            "No résumé yet — set `resume` in content/profile.json.",
            title="Résumé",
            border_style="cyan",
        )
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


def contact(profile: Profile) -> RenderableType:
    lines: list[str] = []
    if profile.email:
        lines.append(f"Email:  {profile.email}")
    for label, url in profile.links.items():
        if label == "substack":
            continue
        lines.append(f"{label.capitalize()}:  {url}")
    if not lines:
        return Panel(
            "No contact info yet — set `contact`/`links` in content/profile.json.",
            title="Contact",
            border_style="cyan",
        )
    return Panel("\n".join(lines), title="Contact", border_style="cyan")


def substack_url(profile: Profile) -> str | None:
    url = profile.links.get("substack", "")
    if not url or url == _TODO_SUBSTACK or "TODO" in url:
        return None
    return url


def substack(profile: Profile) -> RenderableType:
    url = substack_url(profile)
    if url is None:
        return Panel(
            "Substack not configured yet — set `links.substack` in "
            "content/profile.json.",
            title="Substack",
            border_style="cyan",
        )
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
