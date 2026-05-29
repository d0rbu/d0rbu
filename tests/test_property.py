"""Property-based invariants (Hypothesis). Strict Card API only.

parse_card must either return a valid Card or raise CardError for any input;
for schema-valid documents it must always return a clean Card; render_all must
never raise and never emit raw ANSI sequences; blog_url must always return
None or a non-empty string.
"""

import io
import json
import unicodedata

from hypothesis import given
from hypothesis import strategies as st
from rich.console import Console

from henry_castillo import content, render
from henry_castillo.content import Card, CardError, Links, Profile

_text = st.text(max_size=40)

# Required-field strings: non-empty AND non-blank (parse_card uses _req which
# rejects "" but also _sanitize strips nothing here — however a string
# of only whitespace is still non-empty so _req accepts it; no extra filter
# needed for non-empty check).  We filter out "" only to satisfy _req.
_req_str = _text.filter(lambda s: s != "")

# PEP 440-valid version strings for demo min_version.
_version_str = st.builds(
    lambda a, b, c: f"{a}.{b}.{c}",
    st.integers(0, 9),
    st.integers(0, 9),
    st.integers(0, 9),
)


_FORBIDDEN_CATEGORIES = {"Cc", "Cf", "Cs", "Co"}


def _has_cc(s: str) -> bool:
    """Return True if any forbidden-category char (Cc/Cf/Cs/Co) survives in s.

    \n and \t are explicitly allow-listed (they are Cc but must be kept).
    """
    return any(
        c not in "\n\t" and unicodedata.category(c) in _FORBIDDEN_CATEGORIES for c in s
    )


# A strategy that builds a SCHEMA-VALID card document (all required keys
# present, values drawn from arbitrary text including control chars) so the
# sanitize/validate path is genuinely exercised — not theater.
_valid_doc = st.fixed_dictionaries(
    {
        "schema_version": st.just(content.SCHEMA_VERSION),
        "profile": st.fixed_dictionaries(
            {
                "name": _req_str,
                "handle": _req_str,
                "tagline": _req_str,
                "about": _req_str,
                "email": _req_str,
                "links": st.fixed_dictionaries({"github": _req_str, "blog": _text}),
            }
        ),
        "projects": st.lists(
            st.fixed_dictionaries(
                {
                    "name": _req_str,
                    "blurb": _text,
                    "url": _req_str,
                    "tags": st.lists(_text, max_size=4),
                }
            ),
            min_size=1,
            max_size=4,
        ),
        "resume": st.fixed_dictionaries(
            {
                "pdf": _text,
                "experience": st.lists(
                    st.dictionaries(st.text(max_size=8), _text, max_size=4),
                    max_size=3,
                ),
                "education": st.lists(
                    st.dictionaries(st.text(max_size=8), _text, max_size=4),
                    max_size=3,
                ),
                "highlights": st.lists(_text, max_size=4),
            }
        ),
        "demos": st.lists(
            st.fixed_dictionaries(
                {
                    "name": _req_str,
                    "summary": _req_str,
                    "min_version": _version_str,
                }
            ),
            max_size=3,
        ),
    }
)

# Arbitrary JSON-ish for the "never anything but CardError" property.
_json = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda c: (
        st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=6), c, max_size=4)
    ),
    max_leaves=20,
)


@given(_json)
def test_parse_card_only_raises_carderror(value):
    try:
        result = content.parse_card(value)
    except CardError:
        return
    assert isinstance(result, Card)


@given(_valid_doc)
def test_parse_valid_doc_yields_clean_card(doc):
    card = content.parse_card(doc)
    assert isinstance(card, Card)
    p = card.profile
    link_strs = (p.links.github, p.links.blog)
    for s in (p.name, p.handle, p.tagline, p.about, p.email, *link_strs):
        assert not _has_cc(s)
    for proj in card.projects:
        for s in (proj.name, proj.blurb, proj.url, *proj.tags):
            assert not _has_cc(s)
    assert not _has_cc(json.dumps(card.resume.experience + card.resume.education))
    for h in card.resume.highlights:
        assert not _has_cc(h)
    for demo in card.demos:
        for s in (demo.name, demo.summary):
            assert not _has_cc(s)


@given(_valid_doc)
def test_render_all_never_raises_and_no_ansi(doc):
    card = content.parse_card(doc)
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), card)
    out = buf.getvalue()
    assert "\x1b" not in out and "\x9b" not in out and "\x07" not in out


@given(st.text(max_size=60))
def test_blog_url_invariant(blog):
    profile = Profile(
        name="n",
        handle="h",
        tagline="t",
        about="a",
        email="e",
        links=Links(github="g", blog=blog),
    )
    result = render.blog_url(profile)
    assert result is None or (isinstance(result, str) and result.strip() != "")


# ---------------------------------------------------------------------------
# DRIFT property: schema ⟺ parser agreement on generated card-shaped docs
# ---------------------------------------------------------------------------

# A shallow object for experience/education entries (no deep nesting).
_shallow_obj = st.dictionaries(
    st.text(max_size=8),
    st.text(max_size=20),
    max_size=4,
)

# A full valid profile.links object (required by schema).
_links_doc = st.fixed_dictionaries(
    {
        "github": _req_str,
        "blog": _text,
    }
)

# A valid profile object (all required keys present).
_profile_doc = st.fixed_dictionaries(
    {
        "name": _req_str,
        "handle": _req_str,
        "tagline": _req_str,
        "about": _req_str,
        "email": _req_str,
        "links": _links_doc,
    }
)

# A valid project item.
_project_item = st.fixed_dictionaries(
    {
        "name": _req_str,
        "blurb": _text,
        "url": _req_str,
        "tags": st.lists(_text, max_size=4),
    }
)

# A valid resume object.
_resume_doc = st.fixed_dictionaries(
    {
        "pdf": _text,
        "experience": st.lists(_shallow_obj, max_size=3),
        "education": st.lists(_shallow_obj, max_size=3),
        "highlights": st.lists(_text, max_size=4),
    }
)

# A valid demo item.
_demo_item = st.fixed_dictionaries(
    {
        "name": _req_str,
        "summary": _req_str,
        "min_version": _version_str,
    }
)

# A fully valid card document (baseline for mutation strategies below).
_base_card = st.fixed_dictionaries(
    {
        "schema_version": st.just(content.SCHEMA_VERSION),
        "profile": _profile_doc,
        "projects": st.lists(_project_item, min_size=1, max_size=3),
        "resume": _resume_doc,
        "demos": st.lists(_demo_item, min_size=1, max_size=2),
    }
)

# ---- Mutation strategies (each makes the document schema-invalid) ----

# Drop one required top-level key.
_top_level_required = ["schema_version", "profile", "projects", "resume", "demos"]


@st.composite
def _drop_top_key(draw):
    doc = draw(_base_card)
    key = draw(st.sampled_from(_top_level_required))
    doc = dict(doc)
    doc.pop(key, None)
    return doc


# Insert an unexpected extra key at some level.
@st.composite
def _add_extra_key(draw):
    doc = draw(_base_card)
    doc = dict(doc)
    level = draw(st.sampled_from(["root", "profile", "project", "resume", "demo"]))
    extra_key = draw(st.text(min_size=1, max_size=8).filter(lambda s: s.isalpha()))
    extra_val = draw(_text)
    if level == "root":
        doc[extra_key] = extra_val
    elif level == "profile":
        doc["profile"] = dict(doc["profile"])
        doc["profile"][extra_key] = extra_val
    elif level == "project" and doc.get("projects"):
        projects = list(doc["projects"])
        projects[0] = dict(projects[0])
        projects[0][extra_key] = extra_val
        doc["projects"] = projects
    elif level == "resume":
        doc["resume"] = dict(doc["resume"])
        doc["resume"][extra_key] = extra_val
    elif level == "demo" and doc.get("demos"):
        demos = list(doc["demos"])
        demos[0] = dict(demos[0])
        demos[0][extra_key] = extra_val
        doc["demos"] = demos
    return doc


# Make a required string field empty (violates minLength: 1).
_required_string_mutations = [
    ("profile", "name"),
    ("profile", "handle"),
    ("profile", "tagline"),
    ("profile", "about"),
    ("profile", "email"),
]


@st.composite
def _empty_required_string(draw):
    doc = draw(_base_card)
    doc = dict(doc)
    parent_key, field = draw(st.sampled_from(_required_string_mutations))
    doc[parent_key] = dict(doc[parent_key])
    doc[parent_key][field] = ""
    return doc


# Make a required string field a non-string (wrong type).
@st.composite
def _wrong_type_required_string(draw):
    doc = draw(_base_card)
    doc = dict(doc)
    parent_key, field = draw(st.sampled_from(_required_string_mutations))
    doc[parent_key] = dict(doc[parent_key])
    doc[parent_key][field] = draw(st.integers() | st.none() | st.booleans())
    return doc


# Make projects an empty list (violates minItems: 1).
@st.composite
def _empty_projects(draw):
    doc = draw(_base_card)
    doc = dict(doc)
    doc["projects"] = []
    return doc


# Make demos not a list (wrong type — demos itself).
@st.composite
def _demos_wrong_type(draw):
    doc = draw(_base_card)
    doc = dict(doc)
    doc["demos"] = draw(st.text() | st.integers() | st.none())
    return doc


# Combined: either a valid doc or one of the invalid mutations.
_card_shaped_doc = st.one_of(
    _base_card,
    _drop_top_key(),
    _add_extra_key(),
    _empty_required_string(),
    _wrong_type_required_string(),
    _empty_projects(),
    _demos_wrong_type(),
)


@given(_card_shaped_doc)
def test_schema_parser_drift(doc):
    """Schema and parser must agree: schema_ok ⟺ parser_ok on all generated docs.

    This is the canonical drift test — if schema or parser is changed without
    updating the other, this property will find a counterexample.

    Note: min_version-semantic invalidity (non-PEP-440 strings) is outside
    this property by design — the schema has no pattern constraint for
    min_version (it's the parser's job), so schema_ok can be True while
    parser_ok is False for those inputs. The _version_str strategy used here
    always generates valid PEP 440 strings, so this edge case is excluded.
    """
    schema_ok = not list(content._validator().iter_errors(doc))
    try:
        content.parse_card(doc)
        parser_ok = True
    except CardError:
        parser_ok = False
    assert schema_ok == parser_ok, (
        f"schema and parser disagree on doc={doc!r}: "
        f"schema_ok={schema_ok}, parser_ok={parser_ok}"
    )
