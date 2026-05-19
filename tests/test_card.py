import copy
import dataclasses
import unicodedata
from typing import cast

import pytest

from henry_castillo import content
from henry_castillo.content import (
    Card,
    CardError,
    CardLinks,
    CardProfile,
    CardProject,
    CardResume,
)

_VALID: dict[str, object] = {
    "schema_version": 1,
    "profile": {
        "name": "Henry Castillo",
        "handle": "d0rbu",
        "tagline": "Interpretability and safety researcher",
        "about": "DRAFT — about.",
        "email": "henryandrecastillo@gmail.com",
        "links": {"github": "https://github.com/d0rbu", "blog": ""},
    },
    "projects": [
        {
            "name": "mc-dreamer",
            "blurb": "b",
            "url": "https://github.com/d0rbu/mc-dreamer",
            "tags": ["x"],
        }
    ],
    "resume": {
        "pdf": "",
        "experience": [{"org": "DRAFT —"}],
        "education": [{"school": "DRAFT —"}],
        "highlights": ["DRAFT —"],
    },
}


def test_parse_valid():
    c = content.parse_card(copy.deepcopy(_VALID))
    assert isinstance(c, Card)
    assert c.schema_version == content.SCHEMA_VERSION == 1
    assert c.profile == CardProfile(
        name="Henry Castillo",
        handle="d0rbu",
        tagline="Interpretability and safety researcher",
        about="DRAFT — about.",
        email="henryandrecastillo@gmail.com",
        links=CardLinks(github="https://github.com/d0rbu", blog=""),
    )
    assert c.projects == [
        CardProject(
            name="mc-dreamer",
            blurb="b",
            url="https://github.com/d0rbu/mc-dreamer",
            tags=["x"],
        )
    ]
    assert c.resume == CardResume(
        pdf="",
        experience=[{"org": "DRAFT —"}],
        education=[{"school": "DRAFT —"}],
        highlights=["DRAFT —"],
    )


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d.__setitem__("schema_version", 2), "schema_version"),
        (lambda d: d.pop("schema_version"), "schema_version"),
        (lambda d: d.__setitem__("schema_version", "1"), "schema_version"),
        (lambda d: d.__setitem__("schema_version", True), "schema_version"),
        (lambda d: d.__setitem__("schema_version", 1.0), "schema_version"),
        (lambda d: d.__setitem__("profile", {}), "profile.name"),
        (lambda d: d["profile"].__setitem__("name", ""), "profile.name"),
        (lambda d: d["profile"].__setitem__("name", 5), "profile.name"),
        (lambda d: d["profile"].pop("handle"), "profile.handle"),
        (lambda d: d["profile"].pop("tagline"), "profile.tagline"),
        (lambda d: d["profile"].pop("about"), "profile.about"),
        (lambda d: d["profile"].pop("email"), "profile.email"),
        (lambda d: d["profile"].__setitem__("links", {}), "links.github"),
        (lambda d: d["profile"]["links"].__setitem__("github", ""), "links.github"),
        (lambda d: d["profile"]["links"].pop("blog"), "links.blog"),
        (lambda d: d["profile"]["links"].__setitem__("blog", 7), "links.blog"),
        (lambda d: d.__setitem__("projects", []), "projects"),
        (lambda d: d.__setitem__("projects", "x"), "projects"),
        (
            lambda d: d["projects"].__setitem__(
                0, {"name": "n", "url": "u", "tags": []}
            ),
            "projects[0].blurb",
        ),
        (lambda d: d["projects"][0].__setitem__("tags", "x"), "projects[0].tags"),
        (lambda d: d["projects"][0]["tags"].__setitem__(0, 1), "projects[0].tags"),
        (lambda d: d["projects"].__setitem__(0, "nope"), "projects[0]"),
        (lambda d: d.__setitem__("resume", {}), "resume"),
        (lambda d: d["resume"].__setitem__("experience", "x"), "resume.experience"),
        (lambda d: d["resume"].__setitem__("education", [1]), "resume.education"),
        (lambda d: d["resume"].__setitem__("highlights", [1]), "resume.highlights"),
        (lambda d: d.clear(), "card"),
    ],
)
def test_parse_invalid(mutate, msg):
    d = copy.deepcopy(_VALID)
    mutate(d)
    with pytest.raises(CardError) as ei:
        content.parse_card(d)
    assert msg in str(ei.value)


@pytest.mark.parametrize("bad", [None, [], "x", 5, 1.0, True])
def test_parse_non_dict_root(bad):
    with pytest.raises(CardError):
        content.parse_card(bad)


def test_sanitize_strict_residue_note():
    # ESC (Cc) removed; the "[31m" residue text remains (acceptable per design).
    assert (
        content._sanitize_strict("a\x1b[31mX\x1b[0m\x07b\x00\x9bc\nd\te")
        == "a[31mX[0mbc\nd\te"
    )
    assert content._sanitize_strict("plain") == "plain"


@pytest.mark.parametrize("cp", list(range(0x00, 0x100)))
def test_sanitize_strict_exhaustive_latin1(cp):
    ch = chr(cp)
    out = content._sanitize_strict(ch)
    if ch in "\n\t":
        assert out == ch
    elif unicodedata.category(ch) == "Cc":
        assert out == ""
    else:
        assert out == ch


def test_parse_sanitizes_all_strings():
    d = copy.deepcopy(_VALID)
    profile = cast("dict[str, object]", d["profile"])
    profile["name"] = "Henry\x1bCastillo"
    links = cast("dict[str, object]", profile["links"])
    links["blog"] = "https://b\x07log"
    projects = cast("list[dict[str, object]]", d["projects"])
    projects[0]["blurb"] = "b\x07x"
    resume = cast("dict[str, object]", d["resume"])
    resume["highlights"] = ["h\x9bi"]
    resume["experience"] = [{"role": "r\x00x"}]
    c = content.parse_card(d)
    assert c.profile.name == "HenryCastillo"
    assert c.profile.links.blog == "https://blog"
    assert c.projects[0].blurb == "bx"
    assert c.resume.highlights == ["hi"]
    assert c.resume.experience == [{"role": "rx"}]


def test_strict_dataclasses_have_no_defaults():
    for dc in (CardResume, CardLinks, CardProfile, CardProject, Card):
        for f in dataclasses.fields(dc):
            assert (
                f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING
            ), f"{dc.__name__}.{f.name} has a default"


def test_resume_missing_pdf_key():
    """resume.pdf key absent → CardError with 'resume.pdf' in message."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["resume"]).pop("pdf")
    with pytest.raises(CardError, match=r"resume\.pdf"):
        content.parse_card(d)


def test_profile_missing_links_key():
    """profile.links key absent entirely → CardError with 'links.github'."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["profile"]).pop("links")
    with pytest.raises(CardError, match=r"links\.github"):
        content.parse_card(d)


def test_sanitize_json_strict_passthrough():
    """Non-str/dict/list values pass through unchanged."""
    assert content._sanitize_json_strict(42) == 42
    assert content._sanitize_json_strict(None) is None
    assert content._sanitize_json_strict(3.14) == 3.14


def test_sanitize_json_strict_nested():
    """Nested dict/list sanitization recurses correctly."""
    obj = {"k\x00": ["v\x01", {"inner\x07": "data\x1b"}]}
    result = content._sanitize_json_strict(obj)
    assert result == {"k": ["v", {"inner": "data"}]}


def test_profile_non_dict_value():
    """profile key present but value is not a dict → CardError with 'profile.name'."""
    d = copy.deepcopy(_VALID)
    d["profile"] = "not-a-dict"
    with pytest.raises(CardError, match=r"profile\.name"):
        content.parse_card(d)


def test_resume_non_dict_value():
    """resume key present but value is not a dict → CardError with 'resume'."""
    d = copy.deepcopy(_VALID)
    d["resume"] = "not-a-dict"
    with pytest.raises(CardError, match="resume"):
        content.parse_card(d)


def test_parse_rejects_deeply_nested_resume_entry():
    d = copy.deepcopy(_VALID)
    inner: object = {"leaf": "v"}
    for _ in range(200):  # > _MAX_JSON_DEPTH (64), << python recursion limit
        inner = {"x": inner}
    resume = cast("dict[str, object]", d["resume"])
    resume["experience"] = [inner]
    with pytest.raises(content.CardError) as ei:
        content.parse_card(d)
    assert "deep" in str(ei.value).lower()


def test_sanitize_json_strict_depth_bound_raises_carderror():
    deep: object = "leaf"
    for _ in range(content._MAX_JSON_DEPTH + 5):
        deep = [deep]
    with pytest.raises(content.CardError):
        content._sanitize_json_strict(deep)


def test_sanitize_json_strict_dict_direct():
    out = content._sanitize_json_strict_dict({"k\x00": "v\x1bx", "n": 3})
    assert out == {"k": "vx", "n": 3}


def test_shallow_nested_experience_valid():
    """A legitimately nested (but shallow) experience entry parses fine."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["resume"])["experience"] = [{"role": {"a": {"b": "c"}}}]
    c = content.parse_card(d)
    assert c.resume.experience == [{"role": {"a": {"b": "c"}}}]
