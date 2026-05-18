import json
from unittest.mock import MagicMock

import pytest

from henry_castillo import content


def _pkg(monkeypatch, tmp_path, *, profile=None, projects=None):
    """Write tmp content files and point _packaged_resource at them.
    A pathlib.Path satisfies the Traversable protocol (is_file/read_text)."""
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    if profile is not None:
        (cdir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    if projects is not None:
        (cdir / "projects.json").write_text(json.dumps(projects), encoding="utf-8")

    def fake(name: str):
        f = cdir / name
        return f if f.is_file() else None

    monkeypatch.setattr(content, "_packaged_resource", fake)
    return cdir


def _force_repo_fallback(monkeypatch):
    """Make the packaged lookup return None so the repo content/ is used."""
    monkeypatch.setattr(content, "_packaged_resource", lambda _name: None)


def test_packaged_resource_used_when_present(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "X"})
    assert content.load_profile().name == "X"


def test_repo_fallback_loads_real_committed_content(monkeypatch):
    _force_repo_fallback(monkeypatch)
    p = content.load_profile()
    assert p.handle == "d0rbu"  # the committed content/profile.json
    assert (content._repo_content_file("profile.json")).is_file()


def test_only_one_packaged_file_present_other_falls_back(tmp_path, monkeypatch):
    # Only projects.json is packaged; profile.json must independently
    # resolve (here: repo fallback) — no all-or-nothing coupling.
    _pkg(monkeypatch, tmp_path, projects=[{"name": "P"}])
    assert [x.name for x in content.load_projects()] == ["P"]
    assert content.load_profile().handle == "d0rbu"  # repo fallback


def test_resource_protocol_stubs_are_covered():
    """Exercise the Protocol method bodies so branch coverage is complete.

    _Resource is a structural Protocol whose method stubs contain ``...``
    bodies that are never called at runtime. Inheriting from _Resource and
    delegating via super() calls the stub bodies, closing the otherwise-missing
    branch arcs in coverage without any pragma annotation in src/."""

    class _Impl(content._Resource):  # type: ignore[misc]
        def is_file(self) -> bool:
            return super().is_file()  # type: ignore[return-value]

        def read_text(self, encoding: str = "utf-8") -> str:
            return super().read_text(encoding)  # type: ignore[return-value]

    impl = _Impl()
    assert impl.is_file() is None
    assert impl.read_text() is None


def test_packaged_resource_guarded_against_files_error(monkeypatch):
    def boom(_pkg_name):
        raise ModuleNotFoundError("no metadata")

    monkeypatch.setattr(content, "files", boom)
    assert content._packaged_resource("profile.json") is None


def test_packaged_resource_real_body_returns_file(tmp_path, monkeypatch):
    cdir = tmp_path / "henry_castillo" / "_content"
    cdir.mkdir(parents=True)
    (cdir / "profile.json").write_text('{"name": "pkg"}', encoding="utf-8")
    monkeypatch.setattr(content, "files", lambda _pkg: tmp_path / "henry_castillo")
    res = content._packaged_resource("profile.json")
    assert res is not None and res.is_file()
    assert content._read_json("profile.json") == {"name": "pkg"}


def test_packaged_resource_real_body_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "files", lambda _pkg: tmp_path / "henry_castillo")
    assert content._packaged_resource("profile.json") is None


def test_read_json_recursionerror_returns_none(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "ok"})

    def recursive_loads(_text):
        raise RecursionError("too deep")

    monkeypatch.setattr(content.json, "loads", recursive_loads)
    assert content._read_json("profile.json") is None
    assert content.load_profile() == content.Profile()
    assert content.load_projects() == []


def test_read_json_utf8_non_ascii(tmp_path, monkeypatch):
    _pkg(monkeypatch, tmp_path, profile={"name": "Héctor Castañeda", "handle": "h"})
    assert content.load_profile().name == "Héctor Castañeda"


def test_read_json_uses_explicit_utf8_encoding(monkeypatch):
    """_read_json must pass encoding='utf-8' explicitly so content does not
    depend on the ambient locale (kills the read_text() encoding mutation
    deterministically on any platform)."""
    resource = MagicMock()
    resource.read_text.return_value = '{"name": "X"}'
    monkeypatch.setattr(content, "_packaged_resource", lambda _name: resource)
    assert content._read_json("profile.json") == {"name": "X"}
    resource.read_text.assert_called_once_with(encoding="utf-8")


def test_load_profile_full(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        profile={
            "name": "Henry Castillo",
            "handle": "d0rbu",
            "tagline": "ML / interpretability",
            "about": "Bio.",
            "contact": {"email": "a@b.c"},
            "links": {"github": "https://github.com/d0rbu", "x": 5},
            "resume": {
                "pdf": "r.pdf",
                "experience": [{"org": "O"}, "bad"],
                "education": [{"school": "S"}],
                "highlights": ["h1", 2],
            },
        },
    )
    p = content.load_profile()
    assert (p.name, p.handle, p.tagline, p.about) == (
        "Henry Castillo",
        "d0rbu",
        "ML / interpretability",
        "Bio.",
    )
    assert p.email == "a@b.c"
    assert p.links == {"github": "https://github.com/d0rbu"}
    assert p.resume.pdf == "r.pdf"
    assert p.resume.experience == [{"org": "O"}]
    assert p.resume.education == [{"school": "S"}]
    assert p.resume.highlights == ["h1", "2"]


@pytest.mark.parametrize("blob", ["[]", '"x"', "5", "null", "not json", ""])
def test_load_profile_malformed_returns_empty(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "profile.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda name: (cdir / name) if (cdir / name).is_file() else None,
    )
    assert content.load_profile() == content.Profile()


def test_load_profile_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_packaged_resource", lambda _n: None)
    monkeypatch.setattr(content, "_repo_content_file", lambda n: tmp_path / "nope" / n)
    assert content.load_profile() == content.Profile()
    assert content.load_projects() == []


def test_load_profile_partial_and_bad_subtypes(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        profile={"name": "N", "contact": "nope", "links": "nope", "resume": "nope"},
    )
    p = content.load_profile()
    assert p.name == "N" and p.email == "" and p.links == {}
    assert p.resume == content.Resume()


def test_load_projects(tmp_path, monkeypatch):
    _pkg(
        monkeypatch,
        tmp_path,
        projects=[
            {"name": "A", "blurb": "b", "url": "u", "tags": ["t", 1]},
            "garbage",
            {"name": "B"},
        ],
    )
    ps = content.load_projects()
    assert [x.name for x in ps] == ["A", "B"]
    assert ps[0].tags == ["t"]
    assert (ps[1].blurb, ps[1].url, ps[1].tags) == ("", "", [])


@pytest.mark.parametrize("blob", ["{}", '"x"', "5", "null", "bad", ""])
def test_load_projects_malformed_returns_empty_list(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "projects.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(
        content,
        "_packaged_resource",
        lambda name: (cdir / name) if (cdir / name).is_file() else None,
    )
    assert content.load_projects() == []


def test_real_repo_content_loads_and_is_coherent(monkeypatch):
    _force_repo_fallback(monkeypatch)
    p = content.load_profile()
    assert isinstance(p, content.Profile)
    assert p.handle == "d0rbu"
    assert p.name
    assert p.links.get("github") == "https://github.com/d0rbu"
    assert isinstance(p.resume, content.Resume)
    projects = content.load_projects()
    assert isinstance(projects, list)
    for proj in projects:
        assert isinstance(proj, content.Project)
        assert proj.name
        assert isinstance(proj.tags, list)


def test_control_chars_stripped_from_all_string_fields(tmp_path, monkeypatch):
    evil = "a\x1b[31mRED\x1b[0m\x07b\x9bc"  # ESC seq, BEL, C1 CSI
    _pkg(
        monkeypatch,
        tmp_path,
        profile={
            "name": evil,
            "handle": evil,
            "tagline": evil,
            "about": "line1\nline2\ttabbed" + evil,  # \n and \t preserved
            "contact": {"email": evil},
            "links": {"git\x1bhub": "https://x/\x1b]0;pwn\x07"},
            "resume": {
                "pdf": evil,
                "experience": [{"role": evil, "summary": ["nested" + evil]}],
                "education": [{"school": evil}],
                "highlights": ["h" + evil, 1],
            },
        },
        projects=[{"name": evil, "blurb": evil, "url": evil, "tags": ["t" + evil]}],
    )
    p = content.load_profile()
    blob = repr(
        (
            p.name,
            p.handle,
            p.tagline,
            p.about,
            p.email,
            p.links,
            p.resume.pdf,
            p.resume.experience,
            p.resume.education,
            p.resume.highlights,
        )
    )
    assert "\x1b" not in blob and "\x07" not in blob and "\x9b" not in blob
    assert p.name == "aRED" + "b" + "c"
    assert "\n" in p.about and "\t" in p.about  # legitimate whitespace kept
    assert p.links == {"github": "https://x/]0;pwn"}
    assert p.resume.experience == [{"role": "aREDbc", "summary": ["nestedaREDbc"]}]
    assert p.resume.highlights == ["haREDbc", "1"]
    proj = content.load_projects()[0]
    assert "\x1b" not in repr((proj.name, proj.blurb, proj.url, proj.tags))


def test_sanitize_returns_str_and_strips_controls():
    assert content._sanitize("a\x1bb\x00c\nd\te") == "abc\nd\te"
    assert content._sanitize("a\rb\x0cc") == "abc"  # CR/FF stripped; keep-set: \n \t
    assert content._sanitize("plain") == "plain"
    # _sanitize_json passthrough: non-str/dict/list values are returned as-is
    assert content._sanitize_json(42) == 42
    assert content._sanitize_json(None) is None
