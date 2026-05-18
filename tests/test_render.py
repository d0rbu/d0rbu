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
    links={"github": "https://github.com/d0rbu", "substack": "https://x.substack.com"},
    resume=Resume(
        pdf="",
        experience=[{"org": "Acme", "role": "RE", "period": "2024", "summary": "S"}],
        education=[{"school": "Uni", "degree": "BS", "period": "2020"}],
        highlights=["Did a thing"],
    ),
)
PROJECTS = [
    Project(
        "saebench",
        "sae eval suite",
        "https://github.com/d0rbu/saebench",
        ["interp", "python"],
    ),
    Project(
        "moe-router", "routing study", "https://github.com/d0rbu/moe-router", ["moe"]
    ),
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
    assert "Résumé" in out


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
    todo_url = "https://TODO.substack.com  (set your Substack URL)"
    p = Profile(links={"substack": todo_url})
    out = _text(render.substack(p))
    assert "not configured" in out.lower()


def test_substack_missing_message():
    assert "not configured" in _text(render.substack(Profile())).lower()


def test_sections_order_and_keys():
    assert [k for k, _ in render.SECTIONS] == [
        "About",
        "Projects",
        "Résumé",
        "Contact",
        "Substack",
    ]


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
    todo_url = "https://TODO.substack.com  (set your Substack URL)"
    assert render.substack_url(Profile(links={"substack": todo_url})) is None


# --- Branch-coverage completers (no pragma) ---


def test_banner_no_handle_no_tagline():
    """Covers banner: handle='' (skips append) and tagline='' (skips append)."""
    out = _text(render.banner(Profile()))
    assert "henry-castillo" in out


def test_banner_handle_no_tagline():
    """Covers banner branch: handle set but tagline empty."""
    out = _text(render.banner(Profile(name="Alice", handle="alice")))
    assert "@alice" in out and "alice" in out


def test_resume_pdf_branch():
    """Covers the `if r.pdf` branch inside resume()."""
    p = Profile(
        resume=Resume(
            pdf="https://example.com/cv.pdf",
            experience=[],
            education=[],
            highlights=["Highlight"],
        )
    )
    out = _text(render.resume(p))
    assert "https://example.com/cv.pdf" in out


def test_resume_no_summary_entry():
    """Covers the `if e.get('summary')` false branch (entry without summary)."""
    p = Profile(
        resume=Resume(
            experience=[{"org": "Corp", "role": "Dev", "period": "2023"}],
            education=[],
            highlights=[],
        )
    )
    out = _text(render.resume(p))
    assert "Corp" in out


def test_resume_only_experience_no_highlights():
    """Covers `if r.highlights` false branch when experience exists."""
    p = Profile(
        resume=Resume(
            experience=[{"org": "Org", "role": "R", "period": "P", "summary": "S"}],
            education=[],
            highlights=[],
        )
    )
    out = _text(render.resume(p))
    assert "Org" in out


def test_resume_only_education_no_experience():
    """Covers `if r.experience` false branch when education exists."""
    p = Profile(
        resume=Resume(
            experience=[],
            education=[{"school": "MIT", "degree": "BS", "period": "2022"}],
            highlights=[],
        )
    )
    out = _text(render.resume(p))
    assert "MIT" in out


def test_projects_item_with_no_tags():
    """Covers the `p.tags` false branch in the table row loop."""
    notag = Project("notag-proj", "blurb", "https://example.com", [])
    out = _text(render.projects([notag]))
    assert "notag-proj" in out
