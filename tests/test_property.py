"""Property-based invariants (Hypothesis). The loaders must never raise and
must always return correctly-typed, control-char-free content for ANY JSON;
the renderers must never raise and never emit raw escape sequences."""

import io
import json
import unicodedata

from hypothesis import given
from hypothesis import strategies as st
from rich.console import Console

from henry_castillo import content, render
from henry_castillo.content import Profile, Resume

_json = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(max_size=8), children, max_size=5)
    ),
    max_leaves=25,
)

# A bounded JSON-ish value used for nested resume entry fields.
_nested = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda c: (
        st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=6), c, max_size=3)
    ),
    max_leaves=8,
)

# A profile dict that ACTUALLY uses the schema keys, so string values
# (which st.text() populates with control chars) flow through _sanitize.
_profile_doc = st.fixed_dictionaries(
    {
        "name": st.text(),
        "handle": st.text(),
        "tagline": st.text(),
        "about": st.text(),
        "contact": st.fixed_dictionaries({"email": st.text()}),
        "links": st.dictionaries(st.text(max_size=12), st.text(), max_size=5),
        "resume": st.fixed_dictionaries(
            {
                "pdf": st.text(),
                "highlights": st.lists(st.text(), max_size=4),
                "experience": st.lists(
                    st.dictionaries(st.text(max_size=8), _nested, max_size=4),
                    max_size=3,
                ),
                "education": st.lists(
                    st.dictionaries(st.text(max_size=8), _nested, max_size=4),
                    max_size=3,
                ),
            }
        ),
    }
)

_projects_doc = st.lists(
    st.fixed_dictionaries(
        {
            "name": st.text(),
            "blurb": st.text(),
            "url": st.text(),
            "tags": st.lists(st.text(), max_size=4),
        }
    ),
    max_size=4,
)


def _install(monkeypatch, tmp_path, name, value):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / name).write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda n: (cdir / n) if (cdir / n).is_file() else None,
    )


def _has_control(s: str) -> bool:
    return any(c not in "\n\t" and unicodedata.category(c) == "Cc" for c in s)


# NOTE: positional @given with pytest fixtures does not work (fixture 'value'
# not found); use keyword argument form so Hypothesis can distinguish its
# generated args from pytest fixtures. The contract being tested is identical.
@given(value=_json)
def test_load_profile_never_raises_and_is_typed(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", value)
    p = content.load_profile()
    assert isinstance(p, Profile)
    assert isinstance(p.resume, Resume)


@given(value=_json)
def test_load_projects_never_raises_and_is_typed(value, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "projects.json", value)
    out = content.load_projects()
    assert isinstance(out, list)
    assert all(isinstance(x, content.Project) for x in out)


@given(doc=_profile_doc)
def test_loaded_profile_has_no_control_chars(doc, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", doc)
    p = content.load_profile()
    for s in (p.name, p.handle, p.tagline, p.about, p.email, p.resume.pdf):
        assert not _has_control(s)
    for k, v in p.links.items():
        assert not _has_control(k) and not _has_control(v)
    for h in p.resume.highlights:
        assert not _has_control(h)
    assert not _has_control(repr(p.resume.experience + p.resume.education))


@given(pdoc=_profile_doc, jdoc=_projects_doc)
def test_render_never_raises_and_no_ansi(pdoc, jdoc, tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, "profile.json", pdoc)
    _install(monkeypatch, tmp_path, "projects.json", jdoc)
    profile = content.load_profile()
    projects = content.load_projects()
    buf = io.StringIO()
    render.render_all(Console(file=buf, width=80, no_color=True), profile, projects)
    out = buf.getvalue()
    assert "\x1b" not in out and "\x9b" not in out and "\x07" not in out


_todo_like = st.sampled_from(["TODO", "todo", "Todo", "TodoApp", "My TODO substack"])
_substack_val = st.one_of(st.text(max_size=60), _todo_like)


@given(
    substack_val=_substack_val,
    extra=st.dictionaries(st.text(max_size=12), st.text(max_size=60), max_size=4),
)
def test_substack_url_invariant(substack_val, extra):
    links = {**extra, "substack": substack_val}
    result = render.substack_url(Profile(links=links))
    if result is not None:
        assert isinstance(result, str)
        assert result.strip()
        assert "TODO" not in result.upper()


@given(
    st.none()
    | st.integers()
    | st.floats(allow_nan=False)
    | st.text()
    | st.lists(st.text(), max_size=4)
)
def test_str_helper_always_returns_clean_str(value):
    out = content._str(value)
    assert isinstance(out, str)
    assert not _has_control(out)
