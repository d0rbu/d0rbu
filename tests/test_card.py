import copy
import dataclasses
import errno
import functools
import http.client
import http.server
import json as _json
import os as _os_mod
import pathlib
import socket as _socket_mod
import socketserver
import tempfile as _tempfile_mod
import threading
import unicodedata
import urllib.request as _urllib_request
from typing import cast

import pytest

from henry_castillo import _log, content
from henry_castillo.content import (
    Card,
    CardError,
    Demo,
    Links,
    Profile,
    Project,
    Resume,
)

_C = content  # short alias used in R2-fix tests below

_VALID: dict[str, object] = {
    "schema_version": 2,
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
    "demos": [],
}


def test_parse_valid():
    c = content.parse_card(copy.deepcopy(_VALID))
    assert isinstance(c, Card)
    assert c.schema_version == content.SCHEMA_VERSION == 2
    assert c.profile == Profile(
        name="Henry Castillo",
        handle="d0rbu",
        tagline="Interpretability and safety researcher",
        about="DRAFT — about.",
        email="henryandrecastillo@gmail.com",
        links=Links(github="https://github.com/d0rbu", blog=""),
    )
    assert c.projects == [
        Project(
            name="mc-dreamer",
            blurb="b",
            url="https://github.com/d0rbu/mc-dreamer",
            tags=["x"],
        )
    ]
    assert c.resume == Resume(
        pdf="",
        experience=[{"org": "DRAFT —"}],
        education=[{"school": "DRAFT —"}],
        highlights=["DRAFT —"],
    )
    assert c.demos == []


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d.__setitem__("schema_version", 1), "schema_version"),
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


def test_sanitize_residue_note():
    # ESC (Cc) removed; the "[31m" residue text remains (acceptable per design).
    assert (
        content._sanitize("a\x1b[31mX\x1b[0m\x07b\x00\x9bc\nd\te")
        == "a[31mX[0mbc\nd\te"
    )
    assert content._sanitize("plain") == "plain"


@pytest.mark.parametrize("cp", list(range(0x00, 0x100)))
def test_sanitize_exhaustive_latin1(cp):
    ch = chr(cp)
    out = content._sanitize(ch)
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
    for dc in (Resume, Links, Profile, Project, Demo, Card):
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


def test_sanitize_json_passthrough():
    """Non-str/dict/list values pass through unchanged."""
    assert content._sanitize_json(42) == 42
    assert content._sanitize_json(None) is None
    assert content._sanitize_json(3.14) == 3.14


def test_sanitize_json_nested():
    """Nested dict/list sanitization recurses correctly."""
    obj = {"k\x00": ["v\x01", {"inner\x07": "data\x1b"}]}
    result = content._sanitize_json(obj)
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


def test_sanitize_json_depth_bound_raises_carderror():
    deep: object = "leaf"
    for _ in range(content._MAX_JSON_DEPTH + 5):
        deep = [deep]
    with pytest.raises(content.CardError):
        content._sanitize_json(deep)


def test_sanitize_json_dict_direct():
    out = content._sanitize_json_dict({"k\x00": "v\x1bx", "n": 3})
    assert out == {"k": "vx", "n": 3}


def test_shallow_nested_experience_valid():
    """A legitimately nested (but shallow) experience entry parses fine."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["resume"])["experience"] = [{"role": {"a": {"b": "c"}}}]
    c = content.parse_card(d)
    assert c.resume.experience == [{"role": {"a": {"b": "c"}}}]


# ---------------------------------------------------------------------------
# Fixtures and helpers for load_card / fetch / cache tests
# ---------------------------------------------------------------------------

# Save the real socket and urlopen BEFORE the autouse _block_network fixture
# patches them. These are captured at module-import time (collection phase),
# before any fixture runs, so they always hold the genuine implementations.
_REAL_SOCKET = _socket_mod.socket
_REAL_URLOPEN = _urllib_request.urlopen


@pytest.fixture()
def real_network(monkeypatch):
    """Restore real socket/urlopen for tests that genuinely need localhost HTTP.

    The autouse _block_network fixture replaces socket.socket and
    urllib.request.urlopen with a deny-all stub.  This fixture (NOT autouse)
    undoes that patch for the duration of one test by re-patching with the
    real implementations captured at module import time (before any fixture
    ran).  It is intentionally narrow: only the two real-localhost tests use
    it, so the rest of the suite stays network-isolated.
    """
    monkeypatch.setattr(_socket_mod, "socket", _REAL_SOCKET)
    monkeypatch.setattr(_urllib_request, "urlopen", _REAL_URLOPEN)


def _doc_bytes(d=None):
    return _json.dumps(d if d is not None else _VALID).encode()


# ---------------------------------------------------------------------------
# load_card tests
# ---------------------------------------------------------------------------


def test_load_card_fetch_success_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "c.json")
    got = content.load_card(fetch=lambda _u: _doc_bytes())
    assert isinstance(got, content.Card)
    assert (tmp_path / "c.json").read_bytes() == _doc_bytes()


def test_load_card_fetch_fail_uses_cache(tmp_path, monkeypatch):
    cp = tmp_path / "c.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(content, "_cache_path", lambda: cp)
    assert isinstance(
        content.load_card(fetch=lambda _u: (_ for _ in ()).throw(OSError("offline"))),
        content.Card,
    )


def test_load_card_invalid_fetch_keeps_valid_cache(tmp_path, monkeypatch):
    cp = tmp_path / "c.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(content, "_cache_path", lambda: cp)
    got = content.load_card(fetch=lambda _u: b"{not json")
    assert isinstance(got, content.Card)
    assert cp.read_bytes() == _doc_bytes()  # bad fetch did NOT overwrite cache


def test_load_card_fetch_fail_no_cache_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "nope.json")
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: (_ for _ in ()).throw(OSError()))


def test_load_card_invalid_fetch_invalid_cache_raises(tmp_path, monkeypatch):
    cp = tmp_path / "c.json"
    cp.write_bytes(b"garbage")
    monkeypatch.setattr(content, "_cache_path", lambda: cp)
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: b"also not json")


def test_load_card_schema_invalid_fetch_no_cache_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "nope.json")
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: b'{"schema_version": 99}')


def test_load_card_default_fetch_used_when_not_injected(tmp_path, monkeypatch):
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "c.json")
    calls = []
    monkeypatch.setattr(
        content, "_default_fetch", lambda u: calls.append(u) or _doc_bytes()
    )
    assert isinstance(content.load_card(), content.Card)
    assert calls == [content._card_url()]


def test_card_url_default_and_env_override(monkeypatch):
    monkeypatch.delenv("HENRY_CASTILLO_CARD_URL", raising=False)
    assert content._card_url() == "https://d0rbu.github.io/d0rbu/data/card.json"
    monkeypatch.setenv("HENRY_CASTILLO_CARD_URL", "https://example.invalid/x.json")
    assert content._card_url() == "https://example.invalid/x.json"


def test_cache_path_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = content._cache_path()
    assert p == tmp_path / "henry-castillo" / "card.json"
    monkeypatch.setenv("XDG_CACHE_HOME", "relative-not-abs")
    assert (
        content._cache_path()
        == pathlib.Path.home() / ".cache" / "henry-castillo" / "card.json"
    )


def test_write_cache_atomic_and_best_effort(tmp_path, monkeypatch):
    cp = tmp_path / "sub" / "c.json"
    monkeypatch.setattr(content, "_cache_path", lambda: cp)
    content._write_cache(b"hello")
    assert cp.read_bytes() == b"hello"
    # best-effort: an un-writable cache dir must not raise
    bad_path = tmp_path / "x" / "\x00bad" / "c"
    monkeypatch.setattr(content, "_cache_path", lambda: bad_path)
    content._write_cache(b"data")  # must not raise


def test_default_fetch_real_localhost(tmp_path, real_network):
    body = _doc_bytes()
    d = tmp_path / "srv"
    d.mkdir()
    (d / "card.json").write_bytes(body)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as srv:
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            assert content._default_fetch(f"http://127.0.0.1:{port}/card.json") == body
        finally:
            srv.shutdown()
            t.join()


def test_default_fetch_rejects_non_http():
    with pytest.raises(OSError):
        content._default_fetch("file:///etc/passwd")


def test_default_fetch_body_cap(tmp_path, real_network):
    big = b"x" * (300 * 1024)
    d = tmp_path / "srv2"
    d.mkdir()
    (d / "big.bin").write_bytes(big)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as srv:
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            out = content._default_fetch(f"http://127.0.0.1:{port}/big.bin")
            assert len(out) <= content._MAX_BYTES
        finally:
            srv.shutdown()
            t.join()


# ---------------------------------------------------------------------------
# R2-fix tests: HTTPException handling, non-bytes fetch, _write_cache leak-proof
# ---------------------------------------------------------------------------


def test_load_card_httpexception_treated_as_failure(tmp_path, monkeypatch):
    cp = tmp_path / "c.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)

    def incomplete(_u):
        raise http.client.IncompleteRead(b"partial")

    assert isinstance(_C.load_card(fetch=incomplete), _C.Card)  # falls back to cache


def test_load_card_httpexception_no_cache_raises_carderror(tmp_path, monkeypatch):
    monkeypatch.setattr(_C, "_cache_path", lambda: tmp_path / "nope.json")

    def bad(_u):
        raise http.client.BadStatusLine("nope")

    with pytest.raises(_C.CardError):
        _C.load_card(fetch=bad)


def test_load_card_non_bytes_fetch_no_cache_raises_carderror(tmp_path, monkeypatch):
    monkeypatch.setattr(_C, "_cache_path", lambda: tmp_path / "nope.json")
    with pytest.raises(_C.CardError):
        _C.load_card(fetch=lambda _u: None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


def test_load_card_non_bytes_fetch_uses_valid_cache(tmp_path, monkeypatch):
    cp = tmp_path / "c.json"
    cp.write_bytes(_doc_bytes())
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)
    assert isinstance(_C.load_card(fetch=lambda _u: None), _C.Card)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    assert cp.read_bytes() == _doc_bytes()  # non-bytes fetch did not clobber cache


def test_parse_bytes_rejects_non_bytes():
    with pytest.raises(_C.CardError):
        _C._parse_bytes(None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    with pytest.raises(_C.CardError):
        _C._parse_bytes("not bytes")  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


def test_write_cache_no_temp_leak_on_replace_failure(tmp_path, monkeypatch):
    cp = tmp_path / "cd" / "card.json"
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)
    real_replace = pathlib.Path.replace

    def boom(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(pathlib.Path, "replace", boom)
    _C._write_cache(b"data")  # must not raise
    monkeypatch.setattr(pathlib.Path, "replace", real_replace)
    leftovers = list((tmp_path / "cd").glob("tmp*"))
    assert leftovers == [], f"temp file leaked: {leftovers}"
    assert not cp.exists()  # replace failed -> no cache file


def test_write_cache_no_leak_on_fdopen_failure(tmp_path, monkeypatch):
    """Exercises the fd != -1 finally branch: mkstemp succeeds, fdopen raises before
    taking ownership of the fd, so the finally must close and unlink without leaking."""
    cp = tmp_path / "cd2" / "card.json"
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)

    opened_fds: list[int] = []
    real_mkstemp = _tempfile_mod.mkstemp

    def capture_mkstemp(*a, **k):
        fd, path = real_mkstemp(*a, **k)
        opened_fds.append(fd)
        return fd, path

    monkeypatch.setattr(_tempfile_mod, "mkstemp", capture_mkstemp)

    def boom(fd, *a, **k):
        # Do NOT close fd here — let the finally branch handle it
        raise OSError("fdopen failed")

    monkeypatch.setattr(_os_mod, "fdopen", boom)
    _C._write_cache(b"data")  # must not raise

    # Restore real fdopen before assertions (monkeypatch teardown handles this too)
    monkeypatch.setattr(_os_mod, "fdopen", _os_mod.fdopen)

    # No tmp* residue in the parent dir
    parent = tmp_path / "cd2"
    assert list(parent.glob("tmp*")) == []

    # The fd must have been closed by the finally branch (trying to close again raises)
    for fd in opened_fds:
        try:
            _os_mod.close(fd)
            raise AssertionError(f"fd {fd} was not closed by finally")
        except OSError as e:
            assert e.errno == errno.EBADF, f"unexpected errno {e.errno}"


def test_write_cache_finally_close_oserror_suppressed(tmp_path, monkeypatch):
    """Exercises the contextlib.suppress(OSError) inside finally's os.close(fd) branch.

    We let mkstemp succeed, then make fdopen raise (so fd != -1 in finally),
    and also make os.close raise OSError — the function must still not raise.
    """
    cp = tmp_path / "cd3" / "card.json"
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)

    def boom_fdopen(fd, *a, **k):
        raise OSError("fdopen failed")

    def boom_close(fd):
        raise OSError("close failed")

    monkeypatch.setattr(_os_mod, "fdopen", boom_fdopen)
    monkeypatch.setattr(_os_mod, "close", boom_close)
    _C._write_cache(b"data")  # must not raise despite double OSError in finally


def test_write_cache_finally_unlink_oserror_suppressed(tmp_path, monkeypatch):
    """Exercises the contextlib.suppress(OSError) inside finally's Path.unlink() branch.

    We simulate: mkstemp ok, fdopen ok (fd = -1 after context manager), write ok,
    but Path.replace raises → tmp is not None in finally → unlink raises OSError.
    The function must still not raise.
    """
    cp = tmp_path / "cd4" / "card.json"
    monkeypatch.setattr(_C, "_cache_path", lambda: cp)

    def boom_replace(self, target):
        raise OSError("replace failed")

    def boom_unlink(self):
        raise OSError("unlink failed")

    monkeypatch.setattr(pathlib.Path, "replace", boom_replace)
    monkeypatch.setattr(pathlib.Path, "unlink", boom_unlink)
    _C._write_cache(b"data")  # must not raise


# ---------------------------------------------------------------------------
# schema_version 1 is rejected
# ---------------------------------------------------------------------------


def test_schema_version_1_is_rejected():
    """schema_version==1 is no longer current and must raise CardError."""
    with pytest.raises(CardError):
        content.parse_card({**_VALID, "schema_version": 1})


# ---------------------------------------------------------------------------
# Root unknown-key rejection + $schema passthrough
# ---------------------------------------------------------------------------


def test_parse_rejects_extra_root_key():
    """An extra top-level key that isn't in _CARD_ALLOWED_KEYS raises CardError."""
    d = copy.deepcopy(_VALID)
    d["oops"] = 1
    with pytest.raises(CardError, match="card"):
        content.parse_card(d)


def test_parse_allows_dollar_schema_root_key():
    """$schema at the root is explicitly allowed and ignored; Card builds fine."""
    d = copy.deepcopy(_VALID)
    d["$schema"] = "https://example.com/card.schema.json"
    card = content.parse_card(d)
    assert isinstance(card, Card)
    assert card.schema_version == 2


# ---------------------------------------------------------------------------
# Nested unknown-key rejection
# ---------------------------------------------------------------------------


def test_parse_rejects_extra_profile_key():
    """An extra key inside profile raises CardError mentioning 'profile'."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["profile"])["stray"] = "x"
    with pytest.raises(CardError, match="profile"):
        content.parse_card(d)


def test_parse_rejects_extra_links_key():
    """An extra key inside profile.links raises CardError mentioning 'profile.links'."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", cast("dict[str, object]", d["profile"])["links"])["x"] = 1
    with pytest.raises(CardError, match=r"profile\.links"):
        content.parse_card(d)


def test_parse_rejects_extra_project_key():
    """An extra key in a project dict raises CardError mentioning 'projects[0]'."""
    d = copy.deepcopy(_VALID)
    cast("list[dict[str, object]]", d["projects"])[0]["extra"] = "y"
    with pytest.raises(CardError, match=r"projects\[0\]"):
        content.parse_card(d)


def test_parse_rejects_extra_resume_key():
    """An extra key inside resume raises CardError mentioning 'resume'."""
    d = copy.deepcopy(_VALID)
    cast("dict[str, object]", d["resume"])["stray"] = "z"
    with pytest.raises(CardError, match="resume"):
        content.parse_card(d)


# ---------------------------------------------------------------------------
# Demos: valid paths
# ---------------------------------------------------------------------------


def test_parse_empty_demos():
    """demos: [] is valid and produces card.demos == []."""
    d = copy.deepcopy(_VALID)
    d["demos"] = []
    card = content.parse_card(d)
    assert card.demos == []


def test_parse_demos_single():
    """One valid demo dict produces a Demo dataclass with sanitized fields."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [
        {"name": "My\x00Demo", "summary": "sum\x07mary", "min_version": "1.2.3"}
    ]
    card = content.parse_card(d)
    assert len(card.demos) == 1
    dm = card.demos[0]
    assert isinstance(dm, Demo)
    assert dm.name == "MyDemo"
    assert dm.summary == "summary"
    assert dm.min_version == "1.2.3"


def test_parse_demos_multiple():
    """Multiple demo dicts are all parsed and present in the list."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [
        {"name": "alpha", "summary": "first", "min_version": "0.1.0"},
        {"name": "beta", "summary": "second", "min_version": "2.0.0"},
    ]
    card = content.parse_card(d)
    assert len(card.demos) == 2
    assert card.demos[0] == Demo(name="alpha", summary="first", min_version="0.1.0")
    assert card.demos[1] == Demo(name="beta", summary="second", min_version="2.0.0")


# ---------------------------------------------------------------------------
# Demos: error paths
# ---------------------------------------------------------------------------


def test_parse_demos_not_a_list():
    """demos is not a list → CardError mentioning 'demos'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = "not-a-list"
    with pytest.raises(CardError, match="demos"):
        content.parse_card(d)


def test_parse_demos_item_not_a_dict():
    """A demo element that is not a dict → CardError mentioning 'demos[0]'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = ["not-a-dict"]
    with pytest.raises(CardError, match=r"demos\[0\]"):
        content.parse_card(d)


def test_parse_demos_missing_name():
    """A demo missing 'name' → CardError mentioning 'demos[0].name'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"summary": "s", "min_version": "1.0.0"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.name"):
        content.parse_card(d)


def test_parse_demos_empty_name():
    """A demo with empty 'name' string → CardError mentioning 'demos[0].name'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "", "summary": "s", "min_version": "1.0.0"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.name"):
        content.parse_card(d)


def test_parse_demos_missing_summary():
    """A demo missing 'summary' → CardError mentioning 'demos[0].summary'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "min_version": "1.0.0"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.summary"):
        content.parse_card(d)


def test_parse_demos_empty_summary():
    """A demo with empty 'summary' string → CardError mentioning 'demos[0].summary'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "", "min_version": "1.0.0"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.summary"):
        content.parse_card(d)


def test_parse_demos_missing_min_version():
    """A demo missing 'min_version' → CardError mentioning 'demos[0].min_version'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.min_version"):
        content.parse_card(d)


def test_parse_demos_empty_min_version():
    """A demo with empty 'min_version' → CardError mentioning 'demos[0].min_version'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": ""}]
    with pytest.raises(CardError, match=r"demos\[0\]\.min_version"):
        content.parse_card(d)


def test_parse_demos_invalid_min_version():
    """A demo with non-PEP-440 min_version → CardError on 'demos[0].min_version'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": "not.a.version"}]
    with pytest.raises(CardError, match=r"demos\[0\]\.min_version"):
        content.parse_card(d)


def test_parse_demos_extra_key():
    """An unknown key in a demo dict → CardError mentioning 'demos[0]'."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": "1.0.0", "extra": "x"}]
    with pytest.raises(CardError, match=r"demos\[0\]"):
        content.parse_card(d)


# ---------------------------------------------------------------------------
# new_demos helper
# ---------------------------------------------------------------------------


def test_new_demos_equal_version_not_new():
    """Demo whose min_version equals current is NOT included (strictly greater)."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": "1.0.0"}]
    card = content.parse_card(d)
    result = content.new_demos(card, current="1.0.0")
    assert result == []


def test_new_demos_lower_min_version_not_new():
    """Demo whose min_version is lower than current is NOT included."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": "0.9.0"}]
    card = content.parse_card(d)
    result = content.new_demos(card, current="1.0.0")
    assert result == []


def test_new_demos_higher_min_version_is_new():
    """Demo whose min_version is strictly greater than current IS included."""
    d = copy.deepcopy(_VALID)
    d["demos"] = [{"name": "n", "summary": "s", "min_version": "1.0.1"}]
    card = content.parse_card(d)
    result = content.new_demos(card, current="1.0.0")
    assert len(result) == 1
    assert result[0].name == "n"


def test_new_demos_empty_demos():
    """Card with no demos → new_demos returns []."""
    d = copy.deepcopy(_VALID)
    d["demos"] = []
    card = content.parse_card(d)
    assert content.new_demos(card, current="1.0.0") == []


def test_new_demos_invalid_current_raises():
    """new_demos with a non-PEP-440 current version raises CardError."""
    d = copy.deepcopy(_VALID)
    d["demos"] = []
    card = content.parse_card(d)
    with pytest.raises(CardError, match="invalid current version"):
        content.new_demos(card, current="not-a-version")


def test_new_demos_version_ordering():
    """PEP 440 pre/rc/post ordering is respected correctly.

    current = "1.0.0"
    min_versions: "0.9", "1.0.0", "1.0.1", "1.0.0.post1", "2.0rc1"
    Only "1.0.1", "1.0.0.post1", and "2.0rc1" are strictly greater.
    """
    d = copy.deepcopy(_VALID)
    d["demos"] = [
        {"name": "old", "summary": "s", "min_version": "0.9"},
        {"name": "same", "summary": "s", "min_version": "1.0.0"},
        {"name": "patch", "summary": "s", "min_version": "1.0.1"},
        {"name": "post", "summary": "s", "min_version": "1.0.0.post1"},
        {"name": "rc", "summary": "s", "min_version": "2.0rc1"},
    ]
    card = content.parse_card(d)
    result = content.new_demos(card, current="1.0.0")
    assert [dm.name for dm in result] == ["patch", "post", "rc"]


# ---------------------------------------------------------------------------
# new_demos with latest= upper bound
# ---------------------------------------------------------------------------


def _card_with_demos(*min_versions: str) -> content.Card:
    d = copy.deepcopy(_VALID)
    d["demos"] = [
        {"name": f"demo_{mv}", "summary": "s", "min_version": mv} for mv in min_versions
    ]
    return content.parse_card(d)


def test_new_demos_latest_in_range_included():
    """Demo at 0.5.0 with current=0.0.0, latest=1.0.0 → included."""
    card = _card_with_demos("0.5.0")
    result = content.new_demos(card, current="0.0.0", latest="1.0.0")
    assert [dm.name for dm in result] == ["demo_0.5.0"]


def test_new_demos_latest_at_upper_boundary_included():
    """Demo at 1.0.0 (== latest) with current=0.0.0 → included (boundary inclusive)."""
    card = _card_with_demos("1.0.0")
    result = content.new_demos(card, current="0.0.0", latest="1.0.0")
    assert [dm.name for dm in result] == ["demo_1.0.0"]


def test_new_demos_latest_above_upper_excluded():
    """Demo at 2.0.0 (> latest=1.0.0) → NOT included."""
    card = _card_with_demos("2.0.0")
    result = content.new_demos(card, current="0.0.0", latest="1.0.0")
    assert result == []


def test_new_demos_latest_at_current_excluded():
    """Demo at 0.0.0 (== current) → NOT included regardless of latest."""
    card = _card_with_demos("0.0.0")
    result = content.new_demos(card, current="0.0.0", latest="1.0.0")
    assert result == []


def test_new_demos_latest_none_preserves_unbounded_behavior():
    """latest=None: demo at 999.0.0 IS included (old unbounded behaviour)."""
    card = _card_with_demos("999.0.0")
    result = content.new_demos(card, current="0.0.0", latest=None)
    assert [dm.name for dm in result] == ["demo_999.0.0"]


def test_new_demos_bad_min_version_raises_card_error():
    """A directly-constructed Card with Demo(min_version='garbage') → CardError."""
    d = copy.deepcopy(_VALID)
    d["demos"] = []
    card = content.parse_card(d)
    # Construct a Demo with a bad min_version directly (bypasses parse_card validation)
    bad_demo = content.Demo(name="x", summary="s", min_version="not-valid!!")
    card_with_bad = dataclasses.replace(card, demos=[bad_demo])
    with pytest.raises(content.CardError, match="min_version"):
        content.new_demos(card_with_bad, current="0.0.0")


def test_new_demos_bad_latest_raises_card_error():
    """new_demos with a non-PEP-440 latest raises CardError."""
    d = copy.deepcopy(_VALID)
    d["demos"] = []
    card = content.parse_card(d)
    with pytest.raises(content.CardError, match="invalid latest version"):
        content.new_demos(card, current="0.0.0", latest="not-a-version")


# ---------------------------------------------------------------------------
# JSON Schema runtime validation (_validate_schema / _parse_bytes)
# ---------------------------------------------------------------------------


def test_load_card_schema_invalid_missing_keys_raises(tmp_path, monkeypatch):
    """load_card raises CardError when the fetched JSON is missing required keys."""
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "nope.json")
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: b'{"schema_version": 2}')


def test_load_card_schema_invalid_extra_key_raises(tmp_path, monkeypatch):
    """load_card raises CardError when the JSON has an unexpected extra key."""
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "nope.json")
    bad = copy.deepcopy(_VALID)
    bad["unexpected_extra"] = "oops"
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: _json.dumps(bad).encode())


def test_load_card_schema_invalid_demos_wrong_type_raises(tmp_path, monkeypatch):
    """load_card raises CardError when demos is not an array."""
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "nope.json")
    bad = copy.deepcopy(_VALID)
    bad["demos"] = "not-a-list"
    with pytest.raises(content.CardError):
        content.load_card(fetch=lambda _u: _json.dumps(bad).encode())


def test_load_card_schema_valid_body_loads(tmp_path, monkeypatch):
    """load_card successfully loads a schema-valid body via fetch."""
    monkeypatch.setattr(content, "_cache_path", lambda: tmp_path / "c.json")
    got = content.load_card(fetch=lambda _u: _doc_bytes())
    assert isinstance(got, content.Card)
    assert got.schema_version == 2


def test_validate_schema_logs_error_on_validation_failure():
    """_validate_schema logs at ERROR level when the doc fails validation."""
    captured: list[str] = []

    def _sink(msg: str) -> None:
        captured.append(msg)

    sink_id = _log.logger.add(_sink, level="ERROR")
    try:
        with pytest.raises(content.CardError, match="schema"):
            content._validate_schema({"schema_version": 99})
    finally:
        _log.logger.remove(sink_id)
    assert any("schema validation" in m for m in captured)


def test_validate_schema_path_in_error_message():
    """_validate_schema CardError message includes the path of the offending field."""
    # An invalid type for profile.name (not a string) → path includes 'name'
    bad = copy.deepcopy(_VALID)
    cast("dict[str, object]", bad["profile"])["name"] = 123
    with pytest.raises(content.CardError) as ei:
        content._validate_schema(bad)
    assert "profile/name" in str(ei.value)


def test_validate_schema_passes_valid_doc():
    """_validate_schema does not raise for a fully valid document."""
    content._validate_schema(copy.deepcopy(_VALID))  # must not raise


def test_validate_schema_root_path_label():
    """When the error is at the root level, the path label is '(root)'."""
    # A non-object root triggers root-level error.
    with pytest.raises(content.CardError) as ei:
        content._validate_schema("not-an-object")
    # The error path should say '(root)' since absolute_path is empty.
    assert "(root)" in str(ei.value)
