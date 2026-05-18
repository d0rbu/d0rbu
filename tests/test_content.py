import json
from pathlib import Path

import pytest

from henry_castillo import content


def _write(
    dirpath: Path, profile: dict | None = None, projects: object | None = None
) -> Path:
    cdir = dirpath / "_content"
    cdir.mkdir(parents=True, exist_ok=True)
    if profile is not None:
        (cdir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    if projects is not None:
        (cdir / "projects.json").write_text(json.dumps(projects), encoding="utf-8")
    return cdir


def test_content_dir_prefers_packaged(tmp_path, monkeypatch):
    cdir = _write(tmp_path, profile={"name": "X"})
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content._content_dir() == cdir


def test_content_dir_falls_back_to_repo(tmp_path, monkeypatch):
    (tmp_path / "_content").mkdir(parents=True)
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    got = content._content_dir()
    assert got.name == "content"
    assert (got / "profile.json").is_file()


def test_load_profile_full(tmp_path, monkeypatch):
    _write(
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
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert (p.name, p.handle, p.tagline, p.about) == (
        "Henry Castillo", "d0rbu", "ML / interpretability", "Bio.")
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
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert p == content.Profile()


def test_load_profile_missing_file_returns_empty(tmp_path, monkeypatch):
    (tmp_path / "_content").mkdir(parents=True)
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content.load_profile() == content.Profile()


def test_load_profile_partial_and_bad_subtypes(tmp_path, monkeypatch):
    _write(tmp_path, profile={"name": "N", "contact": "nope", "links": "nope",
                              "resume": "nope"})
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    p = content.load_profile()
    assert p.name == "N" and p.email == "" and p.links == {}
    assert p.resume == content.Resume()


def test_load_projects(tmp_path, monkeypatch):
    _write(tmp_path, projects=[
        {"name": "A", "blurb": "b", "url": "u", "tags": ["t", 1]},
        "garbage",
        {"name": "B"},
    ])
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    ps = content.load_projects()
    assert [x.name for x in ps] == ["A", "B"]
    assert ps[0].tags == ["t"]
    assert (ps[1].blurb, ps[1].url, ps[1].tags) == ("", "", [])


@pytest.mark.parametrize("blob", ["{}", '"x"', "5", "null", "bad", ""])
def test_load_projects_malformed_returns_empty_list(tmp_path, monkeypatch, blob):
    cdir = tmp_path / "_content"
    cdir.mkdir(parents=True)
    (cdir / "projects.json").write_text(blob, encoding="utf-8")
    monkeypatch.setattr(content, "_packaged_content", lambda: tmp_path / "_content")
    assert content.load_projects() == []


def test_packaged_content_returns_path():
    p = content._packaged_content()
    assert isinstance(p, Path)
    assert p.name == "_content"
