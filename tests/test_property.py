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


def _has_cc(s: str) -> bool:
    return any(c not in "\n\t" and unicodedata.category(c) == "Cc" for c in s)


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
