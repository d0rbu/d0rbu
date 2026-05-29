"""Tests for render.py — strict Card/Profile/Project types."""

import copy
import io
import unicodedata

from rich.console import Console

from henry_castillo import content as _content_mod
from henry_castillo import render
from henry_castillo.content import (
    Card,
    Links,
    Profile,
    Project,
    parse_card,
)


def _text(renderable) -> str:
    buf = io.StringIO()
    Console(file=buf, width=80, no_color=True).print(renderable)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Shared fixtures built via parse_card so they are always schema-valid.
# ---------------------------------------------------------------------------

_PROFILE_DOC: dict[str, object] = {
    "name": "Henry Castillo",
    "handle": "d0rbu",
    "tagline": "ML / interpretability",
    "about": "I work on interpretability.",
    "email": "d0rbu@users.noreply.github.com",
    "links": {
        "github": "https://github.com/d0rbu",
        "blog": "https://x.substack.com",
    },
}
_RESUME_DOC: dict[str, object] = {
    "pdf": "",
    "experience": [{"org": "Acme", "role": "RE", "period": "2024", "summary": "S"}],
    "education": [{"school": "Uni", "degree": "BS", "period": "2020"}],
    "highlights": ["Did a thing"],
}
_VALID_DOC: dict[str, object] = {
    "schema_version": 2,
    "profile": _PROFILE_DOC,
    "projects": [
        {
            "name": "saebench",
            "blurb": "sae eval suite",
            "url": "https://github.com/d0rbu/saebench",
            "tags": ["interp", "python"],
        },
        {
            "name": "moe-router",
            "blurb": "routing study",
            "url": "https://github.com/d0rbu/moe-router",
            "tags": ["moe"],
        },
    ],
    "resume": _RESUME_DOC,
    "demos": [],
}

CARD: Card = parse_card(_VALID_DOC)
PROFILE = CARD.profile
PROJECTS = CARD.projects


# ---------------------------------------------------------------------------
# banner
# ---------------------------------------------------------------------------


def test_banner_has_identity():
    out = _text(render.banner(PROFILE))
    assert "Henry Castillo" in out and "@d0rbu" in out
    assert "ML / interpretability" in out


def test_banner_name_direct_no_fallback():
    """banner() uses profile.name directly — no 'henry-castillo' fallback."""
    card = parse_card({**_VALID_DOC, "profile": {**_PROFILE_DOC, "name": "Alice"}})
    out = _text(render.banner(card.profile))
    assert "Alice" in out
    assert "henry-castillo" not in out


def test_banner_handle_prefixed():
    out = _text(render.banner(PROFILE))
    assert "@d0rbu" in out


def test_banner_tagline_present():
    out = _text(render.banner(PROFILE))
    assert "ML / interpretability" in out


# ---------------------------------------------------------------------------
# about
# ---------------------------------------------------------------------------


def test_about_renders_bio():
    assert "I work on interpretability." in _text(render.about(PROFILE))


def test_about_no_empty_fallback():
    """about() renders profile.about directly, no 'No bio' fallback."""
    card = parse_card(
        {**_VALID_DOC, "profile": {**_PROFILE_DOC, "about": "Short bio."}}
    )
    out = _text(render.about(card.profile))
    assert "Short bio." in out
    assert "No bio" not in out


# ---------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------


def test_projects_lists_all():
    out = _text(render.projects(PROJECTS))
    assert "saebench" in out and "moe-router" in out
    assert "sae eval suite" in out and "github.com/d0rbu" in out
    assert "interp" in out and "python" in out


def test_projects_tag_filter_case_insensitive():
    out = _text(render.projects(PROJECTS, tag="INTERP"))
    assert "saebench" in out and "moe-router" not in out


def test_projects_tag_no_match_message():
    out = _text(render.projects(PROJECTS, tag="nope"))
    assert "No projects tagged 'nope'." in out


def test_projects_empty_message():
    assert "No projects yet." in _text(render.projects([]))


def test_projects_tag_filter_nfc_nfd_insensitive():
    nfd = unicodedata.normalize("NFD", "café")
    nfc = unicodedata.normalize("NFC", "café")
    assert nfd != nfc
    # Build Project objects directly (tags can be NFD-stored in raw JSON,
    # but parse_card sanitizes to NFC via _sanitize).  We use
    # Project directly here to exercise the filter logic with NFD tags.
    projs = [
        Project("p-accent", "blurb", "https://x", [nfd]),
        Project("p-other", "b", "https://y", ["web"]),
    ]
    for query in (nfc, nfd):
        out = _text(render.projects(projs, tag=query))
        assert "p-accent" in out
        assert "p-other" not in out
    assert "p-accent" not in _text(render.projects(projs, tag="zzz"))


def test_projects_item_with_no_tags():
    """Covers the p.tags false branch in the table row loop."""
    notag = Project("notag-proj", "blurb", "https://example.com", [])
    out = _text(render.projects([notag]))
    assert "notag-proj" in out


# ---------------------------------------------------------------------------
# resume
# ---------------------------------------------------------------------------


def test_resume_renders_sections():
    out = _text(render.resume(CARD))
    assert "Acme" in out and "Uni" in out and "Did a thing" in out
    assert "Résumé" in out


def test_resume_omits_empty_experience():
    """resume() omits the Experience block when experience list is empty."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [],
            "education": [{"degree": "BS", "school": "MIT", "period": "2020"}],
            "highlights": ["h1"],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "Experience" not in out
    assert "MIT" in out


def test_resume_omits_empty_education():
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [{"role": "R", "org": "O", "period": "P"}],
            "education": [],
            "highlights": [],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "Education" not in out
    assert "O" in out


def test_resume_omits_empty_pdf():
    """PDF line absent when resume.pdf == ''."""
    out = _text(render.resume(CARD))
    assert "PDF:" not in out


def test_resume_pdf_shown_when_set():
    doc = {**_VALID_DOC, "resume": {**_RESUME_DOC, "pdf": "https://example.com/cv.pdf"}}
    card = parse_card(doc)
    out = _text(render.resume(card))
    lines = [ln.strip("│ \n") for ln in out.splitlines() if "PDF:" in ln]
    assert lines == ["PDF: https://example.com/cv.pdf"]


def test_resume_no_missing_data_fallback():
    """resume() renders whatever is present; no 'No résumé' fallback exists."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [{"role": "R", "org": "O", "period": "P"}],
            "education": [],
            "highlights": [],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "No résumé" not in out


def test_resume_no_summary_entry():
    """Covers the if e.get('summary') false branch."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [{"org": "Corp", "role": "Dev", "period": "2023"}],
            "education": [],
            "highlights": [],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "Corp" in out
    assert "None" not in out


def test_resume_only_highlights():
    """Covers highlights-only path (no experience, education, or pdf)."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [],
            "education": [],
            "highlights": ["A highlight"],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "A highlight" in out


# ---------------------------------------------------------------------------
# contact
# ---------------------------------------------------------------------------


def test_contact_shows_email_and_github():
    out = _text(render.contact(PROFILE))
    assert "d0rbu@users.noreply.github.com" in out
    assert "github.com/d0rbu" in out


def test_contact_does_not_show_blog():
    """contact() shows only Email and GitHub — blog is excluded."""
    out = _text(render.contact(PROFILE))
    assert "Blog" not in out
    assert "blog" not in out.lower()
    assert "substack" not in out.lower()


def test_contact_labels_capitalized():
    out = _text(render.contact(PROFILE))
    assert "Email:" in out
    assert "GitHub:" in out


# ---------------------------------------------------------------------------
# blog / blog_url
# ---------------------------------------------------------------------------


def test_blog_configured_shows_url():
    out = _text(render.blog(PROFILE))
    assert "Writing: https://x.substack.com" in out


def test_blog_unconfigured_shows_fallback():
    """When blog is '', the Blog panel says 'Blog not configured yet.'"""
    doc = {
        **_VALID_DOC,
        "profile": {
            **_PROFILE_DOC,
            "links": {"github": "https://github.com/d0rbu", "blog": ""},
        },
    }
    card = parse_card(doc)
    out = _text(render.blog(card.profile))
    assert "Blog not configured yet." in out


def test_blog_panel_title_is_blog():
    out = _text(render.blog(PROFILE))
    assert "Blog" in out


def test_blog_url_returns_url_when_set():
    assert render.blog_url(PROFILE) == "https://x.substack.com"


def test_blog_url_returns_none_when_empty():
    doc = {
        **_VALID_DOC,
        "profile": {
            **_PROFILE_DOC,
            "links": {"github": "https://github.com/d0rbu", "blog": ""},
        },
    }
    card = parse_card(doc)
    assert render.blog_url(card.profile) is None


def test_blog_url_returns_none_when_whitespace_only():
    profile = Profile(
        name="N",
        handle="h",
        tagline="t",
        about="a",
        email="e@x.y",
        links=Links(github="https://g", blog="   "),
    )
    assert render.blog_url(profile) is None


# ---------------------------------------------------------------------------
# SECTIONS order
# ---------------------------------------------------------------------------


def test_sections_order_and_keys():
    assert [k for k, _ in render.SECTIONS] == [
        "About",
        "Projects",
        "Résumé",
        "Contact",
        "Blog",
    ]


def test_sections_renderers_accept_card(valid_card):
    """Every section renderer must accept a Card (not Profile+projects)."""
    for _name, fn in render.SECTIONS:
        result = fn(valid_card)
        assert result is not None


# ---------------------------------------------------------------------------
# render_all
# ---------------------------------------------------------------------------


def test_render_all_dumps_every_section():
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), CARD)
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "I work on interpretability." in out
    assert "saebench" in out
    assert "Acme" in out
    assert "d0rbu@users.noreply.github.com" in out
    assert "Writing: https://x.substack.com" in out


def test_render_all_banner_only_once():
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), CARD)
    out = buf.getvalue()
    assert out.count("Henry Castillo") == 1


# ---------------------------------------------------------------------------
# Rich-markup literal regression: bracket substrings must not be consumed.
# ---------------------------------------------------------------------------


def test_content_with_bracket_markup_renders_literally():
    """Regression: bracket substrings in content render literally, not as markup."""
    profile = Profile(
        name="N",
        handle="h",
        tagline="t",
        about="bio [bold]x[/bold] [link]",
        email="e@x.y",
        links=Links(github="https://g/[u]", blog=""),
    )
    assert "[bold]x[/bold] [link]" in _text(render.about(profile))
    contact_text = _text(render.contact(profile))
    contact_lines = [
        ln.strip("│ \n") for ln in contact_text.splitlines() if "GitHub:" in ln
    ]
    assert contact_lines == ["GitHub:  https://g/[u]"]


def test_project_blurb_with_brackets_renders_literally():
    proj = [Project("p", "blurb [b]z[/b]", "https://u/[v]", ["t1", "t2"])]
    out = _text(render.projects(proj))
    assert "blurb [b]z[/b]" in out and "[t1, t2]" in out
    url_lines = [ln for ln in out.splitlines() if "u/[v]" in ln]
    assert url_lines
    cells = [c.strip() for c in url_lines[0].split("│") if c.strip()]
    assert cells == ["p", "blurb [b]z[/b] [t1, t2]", "https://u/[v]"]


# ---------------------------------------------------------------------------
# End-to-end sanitize → render: bidi/format chars must not reach output
# ---------------------------------------------------------------------------

_BIDI_VALID_DOC: dict[str, object] = {
    "schema_version": 2,
    "profile": {
        "name": "\u202eHenry",  # RLO U+202E in name
        "handle": "d0rbu",
        "tagline": "safe",
        "about": "bio\ud800",  # lone surrogate in about
        "email": "e@x.com",
        "links": {
            "github": "https://github.com/d0rbu",
            "blog": "https://blog.example.com",
        },
    },
    "projects": [
        {
            "name": "proj",
            "blurb": "blurb\ufeff",  # BOM U+FEFF in blurb
            "url": "https://example.com",
            "tags": ["t"],
        }
    ],
    "resume": {
        "pdf": "",
        "experience": [],
        "education": [],
        "highlights": ["hi\u200b"],  # ZWSP U+200B in highlight
    },
    "demos": [],
}

# Forbidden codepoints that must NEVER appear in render output
_FORBIDDEN_CPS = {
    "\u202e",  # RIGHT-TO-LEFT OVERRIDE (RLO) — Cf
    "\u200b",  # ZERO WIDTH SPACE (ZWSP) — Cf
    "\ufeff",  # BOM / ZERO WIDTH NO-BREAK SPACE — Cf
    "\ud800",  # lone surrogate — Cs
}


def test_render_all_strips_bidi_format_surrogates():
    """parse_card + render_all must strip all Cf/Cs/Co chars before output.

    Also uses a Console backed by an ascii-codec StringIO to prove that no
    lone surrogate reaches the stream (which would raise UnicodeEncodeError
    with a strict codec) and no display-spoofing char survives sanitization.
    """
    card = _content_mod.parse_card(copy.deepcopy(_BIDI_VALID_DOC))

    # Standard StringIO render path
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), card)
    out = buf.getvalue()

    for cp in _FORBIDDEN_CPS:
        assert cp not in out, (
            f"forbidden char U+{ord(cp):04X} survived in render output"
        )

    # Strict ascii-codec path: lone surrogate would crash here if it survived
    ascii_buf = io.StringIO()
    render.render_all(Console(file=ascii_buf, width=80, no_color=True), card)
    ascii_out = ascii_buf.getvalue()
    # encode/decode round-trip through utf-8 to prove no surrogate slipped through
    ascii_out.encode("utf-8")  # raises UnicodeEncodeError if a lone surrogate survived

    assert "Henry" in out  # ordinary text (minus the stripped RLO) is preserved


# ---------------------------------------------------------------------------
# Item 4: render em-dash empty-field drop
# ---------------------------------------------------------------------------


def test_resume_experience_empty_org_no_doubled_emdash():
    """experience row with empty org: output shows 'R — 2024', not 'R —  — 2024'."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [{"role": "R", "org": "", "period": "2024"}],
            "education": [],
            "highlights": [],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    # Empty org is filtered; exactly one em-dash joining role to period
    assert "R — 2024" in out
    assert "—  —" not in out


def test_resume_education_empty_degree_and_period_no_stray_emdash():
    """education row with empty degree/period: lone school, no em-dashes."""
    doc = {
        **_VALID_DOC,
        "resume": {
            "pdf": "",
            "experience": [],
            "education": [{"degree": "", "school": "MIT", "period": ""}],
            "highlights": [],
        },
    }
    card = parse_card(doc)
    out = _text(render.resume(card))
    assert "MIT" in out
    # No em-dash at all (only non-empty field is school)
    assert "—" not in out
