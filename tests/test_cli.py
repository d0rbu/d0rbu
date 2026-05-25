"""Exhaustive behavioral tests for the CLI entrypoint (henry_castillo.__main__).

Exact-output assertions where the contract is exact. The argparse
``allow_abbrev=False`` lock and the explicit update-check env contract are
pinned here. No real network (see tests/conftest.py).
"""

import argparse
import importlib.metadata
import io
import unicodedata
import urllib.error

import pytest
from packaging.version import Version
from rich.console import Console

import henry_castillo.__main__ as _m
import henry_castillo.update as up
from henry_castillo import __version__, _log, render
from henry_castillo.__main__ import (
    _harden_stream,
    _maybe_notice,
    _update_check_disabled_by_env,
    main,
)
from henry_castillo.content import CardError, parse_card

_EXPECTED_NOTICE = (
    f"A new release of henry-castillo is available: {__version__} -> 9.9.9. "
    f"Run `henry-castillo --update` to upgrade.\n"
)

# ---------------------------------------------------------------------------
# Shared valid card doc used for monkeypatching load_card
# ---------------------------------------------------------------------------

_CLI_PROFILE_DOC: dict[str, object] = {
    "name": "Henry Castillo",
    "handle": "d0rbu",
    "tagline": "ML / interpretability",
    "about": "I work on interpretability.",
    "email": "henryandrecastillo@gmail.com",
    "links": {
        "github": "https://github.com/d0rbu",
        "blog": "https://henrycastillo.substack.com",
    },
}
_CLI_RESUME_DOC: dict[str, object] = {
    "pdf": "https://example.com/cv.pdf",
    "experience": [
        {"role": "Researcher", "org": "Acme", "period": "2024", "summary": "S"}
    ],
    "education": [{"degree": "BS", "school": "MIT", "period": "2020"}],
    "highlights": ["Published a paper"],
}
_VALID_DOC: dict[str, object] = {
    "schema_version": 2,
    "profile": _CLI_PROFILE_DOC,
    "projects": [
        {
            "name": "saebench",
            "blurb": "SAE eval suite",
            "url": "https://github.com/d0rbu/saebench",
            "tags": ["interp", "python"],
        }
    ],
    "resume": _CLI_RESUME_DOC,
    "demos": [],
}

_VALID_CARD = parse_card(_VALID_DOC)


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


def test_version_flag_exact(capsys):
    rc = main(["--version"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == f"henry-castillo {__version__}\n"
    assert cap.err == ""


def test_version_does_not_call_load_card(monkeypatch, capsys):
    """--version must short-circuit before load_card is ever called."""
    monkeypatch.setattr(
        _m.content, "load_card", lambda **k: (_ for _ in ()).throw(CardError("no data"))
    )
    rc = main(["--version"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == f"henry-castillo {__version__}\n"


# ---------------------------------------------------------------------------
# --check-update
# ---------------------------------------------------------------------------


def test_check_update_available_exact(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    rc = main(["--check-update"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == (
        f"henry-castillo {__version__}: a newer release 9.9.9 "
        f"is available. Run `henry-castillo --update`.\n"
    )
    assert cap.err == ""


def test_check_update_up_to_date_exact(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    rc = main(["--check-update"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == f"henry-castillo {__version__} is up to date.\n"
    assert cap.err == ""


def test_check_update_does_not_call_load_card(monkeypatch, capsys):
    """--check-update must short-circuit before load_card is ever called."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr(
        _m.content, "load_card", lambda **k: (_ for _ in ()).throw(CardError("no data"))
    )
    rc = main(["--check-update"])
    assert rc == 0


# ---------------------------------------------------------------------------
# --update — rc propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rc", [0, 1, 2, 42, 130])
def test_update_propagates_returncode(rc, monkeypatch):
    monkeypatch.setattr(up, "perform_update", lambda: rc)
    assert main(["--update"]) == rc


def test_update_invokes_perform(monkeypatch):
    called = []
    monkeypatch.setattr(up, "perform_update", lambda: called.append(1) or 0)
    assert main(["--update"]) == 0
    assert called == [1]


def test_update_does_not_call_load_card(monkeypatch):
    """--update must short-circuit before load_card is ever called."""
    monkeypatch.setattr(up, "perform_update", lambda: 0)
    monkeypatch.setattr(
        _m.content, "load_card", lambda **k: (_ for _ in ()).throw(CardError("no data"))
    )
    rc = main(["--update"])
    assert rc == 0


# ---------------------------------------------------------------------------
# flag precedence matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--version", "--update"],
        ["--update", "--version"],
        ["--version", "--check-update"],
        ["--check-update", "--version"],
    ],
)
def test_version_beats_other_actions(argv, monkeypatch, capsys):
    monkeypatch.setattr(
        up, "perform_update", lambda: pytest.fail("perform_update called")
    )
    monkeypatch.setattr(
        up, "check_for_update", lambda **k: pytest.fail("check_for_update called")
    )
    rc = main(argv)
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == f"henry-castillo {__version__}\n"


@pytest.mark.parametrize(
    "argv", [["--update", "--check-update"], ["--check-update", "--update"]]
)
def test_update_beats_check_update(argv, monkeypatch):
    monkeypatch.setattr(up, "perform_update", lambda: 0)
    monkeypatch.setattr(
        up, "check_for_update", lambda **k: pytest.fail("check_for_update called")
    )
    assert main(argv) == 0


# ---------------------------------------------------------------------------
# allow_abbrev=False lock + unknown flags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--up"],
        ["--upd"],
        ["--update-"],
        ["--ver"],
        ["--vers"],
        ["--check"],
        ["--check-up"],
        ["--no-update"],
        ["--bogus"],
    ],
)
def test_abbrev_disabled_and_unknown_flags_exit_2(argv, monkeypatch):
    monkeypatch.setattr(
        up, "perform_update", lambda: pytest.fail("perform_update called")
    )
    monkeypatch.setattr(
        up, "check_for_update", lambda **k: pytest.fail("check_for_update called")
    )
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2


@pytest.mark.parametrize("argv", [["-h"], ["--help"]])
def test_help_exits_zero(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# env-var truthiness — the NEW explicit contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "suppressed"),
    [
        # truthy / non-falsey -> suppressed
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("anything", True),
        (" 1 ", True),
        # recognized false values -> NOT suppressed
        ("", False),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("off", False),
        (" off ", False),
    ],
)
def test_env_contract_drives_check_for_update(
    value, suppressed, monkeypatch, stub_tui_run
):
    called = []
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", value)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or None)
    rc = main([])
    assert rc == 0
    assert (len(called) == 0) is suppressed


def test_env_contract_unset_not_suppressed(monkeypatch, stub_tui_run):
    called = []
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or None)
    assert main([]) == 0
    assert called == [1]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("1", True),
        ("true", True),
        ("YES", True),
        ("whatever", True),
    ],
)
def test_update_check_disabled_by_env_unit(value, expected, monkeypatch):
    if value is None:
        monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    else:
        monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", value)
    assert _update_check_disabled_by_env() is expected


# ---------------------------------------------------------------------------
# _maybe_notice — three independent guards
# ---------------------------------------------------------------------------


def test_maybe_notice_positive_path_tty_rc0_no_crash(monkeypatch, capsys, stub_tui_run):
    """TTY path with update available: rc==0, tui.run gets update_available=True.

    In the new design the update notice is shown INSIDE tui.run (via the
    Demos badge), NOT via _maybe_notice which is only called on the non-TTY
    default path and on the subcommand path.  stub_tui_run is a no-op, so
    the badge text does not appear in stdout — that is expected and correct.
    """
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr(up, "current_version", lambda: __version__)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}
    _orig_stub = lambda *_a, **_k: None  # noqa: E731

    def capturing_stub(*a, **k):
        captured["update_available"] = k.get("update_available")

    monkeypatch.setattr(_m.tui, "run", capturing_stub)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert captured.get("update_available") is True
    assert "A new release" not in out  # notice not printed on TTY default path


def test_maybe_notice_no_update_available_prints_nothing_extra(
    monkeypatch, capsys, stub_tui_run
):
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_maybe_notice_suppressed_with_no_update_check_flag(
    monkeypatch, capsys, stub_tui_run
):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main(["--no-update-check"])
    out = capsys.readouterr().out
    assert rc == 0
    assert called == []
    assert "A new release" not in out


def test_maybe_notice_suppressed_by_env_var(monkeypatch, capsys, stub_tui_run):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", "1")
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert called == []
    assert "A new release" not in out


def test_maybe_notice_suppressed_when_not_tty_and_no_network(monkeypatch, capsys):
    """Non-tty must suppress; conftest blocks real network so a leak would fail."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    # check_for_update is NOT mocked: if the guard were wrong it would attempt
    # a real fetch, which the autouse network block turns into RuntimeError.
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_maybe_notice_offline_under_tty_does_not_crash_and_prints_no_notice(
    tmp_path, monkeypatch, capsys, stub_tui_run
):
    """Interactive TTY, update check ENABLED, but real fetch fails."""
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(up, "cache_path", lambda: tmp_path / "u.json")

    def boom(*a, **k):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(up.urllib.request, "urlopen", boom)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_maybe_notice_under_tty_non_dict_body_prints_no_notice(
    tmp_path, monkeypatch, capsys, stub_tui_run
):
    """A non-dict PyPI body (null) drives the real fetch path."""
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(up, "cache_path", lambda: tmp_path / "u.json")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *_a):
            return b"null"

    monkeypatch.setattr(up.urllib.request, "urlopen", lambda *a, **k: _Resp())
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_main_under_tty_info_null_body_rc0_no_notice_no_traceback(
    tmp_path, monkeypatch, capsys, stub_tui_run
):
    """End-to-end FIX 1 through the CLI: {info: null} body under interactive TTY."""
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(up, "cache_path", lambda: tmp_path / "u.json")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a):
            return b'{"info": null}'

    monkeypatch.setattr(up.urllib.request, "urlopen", lambda *a, **k: _Resp())
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out
    assert "Traceback" not in out


def test_maybe_notice_guard_unit_no_update_check(monkeypatch):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1))
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    _maybe_notice(argparse.Namespace(no_update_check=True))
    assert called == []


def test_maybe_notice_guard_unit_env(monkeypatch):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1))
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", "yes")
    _maybe_notice(argparse.Namespace(no_update_check=False))
    assert called == []


def test_maybe_notice_guard_unit_not_tty(monkeypatch):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1))
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    _maybe_notice(argparse.Namespace(no_update_check=False))
    assert called == []


# ---------------------------------------------------------------------------
# argv defaulting + default run
# ---------------------------------------------------------------------------


def test_default_run_exact_stdout(capsys):
    rc = main([])
    cap = capsys.readouterr()
    assert rc == 0
    assert "About" in cap.out
    assert "Projects" in cap.out
    assert cap.err == ""


def test_main_uses_sys_argv_when_argv_is_none(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["henry-castillo"])
    rc = main(None)
    cap = capsys.readouterr()
    assert rc == 0
    assert "About" in cap.out


def test_main_uses_sys_argv_version_when_argv_is_none(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["henry-castillo", "--version"])
    rc = main(None)
    assert rc == 0
    assert capsys.readouterr().out == f"henry-castillo {__version__}\n"


# ---------------------------------------------------------------------------
# version drift
# ---------------------------------------------------------------------------


def test_version_matches_distribution_metadata():
    assert __version__ == importlib.metadata.version("henry-castillo")


def test_version_is_pep440_parseable():
    assert str(Version(__version__)) == __version__


def _run(argv, monkeypatch, *, tty=False):
    """Run main() with stdout captured; isatty controllable."""
    buf = io.StringIO()
    buf.isatty = lambda: tty  # type: ignore[attr-defined]  # ty:ignore[invalid-assignment]
    monkeypatch.setattr("sys.stdout", buf)
    rc = main(argv)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def test_subcommand_about(monkeypatch):
    rc, out = _run(["about"], monkeypatch)
    assert rc == 0
    assert "About" in out


def test_subcommand_projects(monkeypatch):
    rc, out = _run(["projects"], monkeypatch)
    assert rc == 0
    assert "Projects" in out


def test_subcommand_projects_tag(monkeypatch):
    rc, out = _run(["projects", "--tag", "zzznotareal_tag"], monkeypatch)
    assert rc == 0
    assert "No projects tagged 'zzznotareal_tag'." in out


def test_subcommand_projects_tag_match(monkeypatch, valid_card):
    """projects --tag match uses the seeded card via load_card."""
    # The seeded card (from conftest) includes a project with tag "interp"
    rc, _out = _run(["projects", "--tag", "interp"], monkeypatch)
    assert rc == 0


def test_subcommand_resume_and_accent_alias(monkeypatch):
    rc, out = _run(["resume"], monkeypatch)
    assert rc == 0 and "Résumé" in out
    rc2, out2 = _run(["résumé"], monkeypatch)
    assert rc2 == 0 and "Résumé" in out2


def test_subcommand_resume_open_no_pdf(monkeypatch, valid_card):
    """The seeded card has an empty pdf -> --open must NOT open a browser."""
    # Rebuild the seeded card with an empty pdf to test this path
    empty_pdf_card = parse_card(
        {
            **_VALID_DOC,
            "resume": {**_CLI_RESUME_DOC, "pdf": ""},
        }
    )
    monkeypatch.setattr(_m.content, "load_card", lambda **k: empty_pdf_card)
    opened: list[str] = []
    monkeypatch.setattr("henry_castillo.__main__._open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0
    assert opened == []
    assert "no résumé" in out.lower()


def test_resume_open_with_pdf(monkeypatch):
    """resume --open with a pdf set opens the URL."""
    monkeypatch.setattr(_m.content, "load_card", lambda **k: _VALID_CARD)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, _ = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == ["https://example.com/cv.pdf"]


def test_resume_open_without_pdf_message(monkeypatch):
    """resume --open without a pdf prints message and doesn't open."""
    empty_pdf_card = parse_card(
        {**_VALID_DOC, "resume": {**_CLI_RESUME_DOC, "pdf": ""}}
    )
    monkeypatch.setattr(_m.content, "load_card", lambda **k: empty_pdf_card)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == []
    assert "no résumé" in out.lower()


def test_subcommand_contact(monkeypatch):
    rc, out = _run(["contact"], monkeypatch)
    assert rc == 0 and "Contact" in out


def test_subcommand_blog(monkeypatch):
    """blog subcommand returns rc0 and shows 'Blog'."""
    rc, out = _run(["blog"], monkeypatch)
    assert rc == 0 and "Blog" in out


def test_subcommand_blog_with_url_opens(monkeypatch):
    """blog subcommand opens the URL when blog is set."""
    monkeypatch.setattr(_m.content, "load_card", lambda **k: _VALID_CARD)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["blog"], monkeypatch)
    assert rc == 0 and "Blog" in out
    assert opened == ["https://henrycastillo.substack.com"]


def test_subcommand_blog_without_url_does_not_open(monkeypatch):
    """blog subcommand does not open when blog is empty."""
    no_blog_card = parse_card(
        {
            **_VALID_DOC,
            "profile": {
                **_CLI_PROFILE_DOC,
                "links": {"github": "https://github.com/d0rbu", "blog": ""},
            },
        }
    )
    monkeypatch.setattr(_m.content, "load_card", lambda **k: no_blog_card)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["blog"], monkeypatch)
    assert rc == 0 and opened == []
    assert "Blog" in out


def test_default_non_tty_renders_all_plain(monkeypatch):
    rc, out = _run([], monkeypatch, tty=False)
    assert rc == 0
    # plain full render: banner + every section, no interactive prompt
    assert "About" in out and "Projects" in out and "Contact" in out


def test_default_tty_runs_interactive_loop(monkeypatch):
    called = {}

    def fake_run(card, *, console, **kw):
        called["yes"] = True
        console.print("INTERACTIVE_CALLED")

    monkeypatch.setattr(_m.tui, "run", fake_run)
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    rc, out = _run([], monkeypatch, tty=True)
    assert rc == 0 and called.get("yes") and "INTERACTIVE_CALLED" in out


def test_subcommand_suppresses_notice_in_pipe(monkeypatch):
    monkeypatch.setattr(
        up,
        "check_for_update",
        lambda **_k: (_ for _ in ()).throw(AssertionError("net!")),
    )
    rc, out = _run(["about"], monkeypatch, tty=False)
    assert rc == 0 and "new release" not in out.lower()


def test_version_still_short_circuits(monkeypatch):
    rc, out = _run(["--version"], monkeypatch)
    assert rc == 0
    assert out.strip() == f"henry-castillo {__import__('henry_castillo').__version__}"


def test_open_url_calls_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(_m.webbrowser, "open", lambda u: calls.append(u) or True)
    _m._open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_render_section_unknown_section_is_noop(monkeypatch):
    """Cover the fallthrough branch in _render_section for unrecognized section."""
    buf = io.StringIO()
    console = Console(file=buf, highlight=False)
    args = argparse.Namespace(section="__unknown__", no_update_check=True)
    rc = _m._render_section(args, console, _VALID_CARD)
    assert rc == 0
    assert buf.getvalue() == ""


def test_subcommand_on_tty_emits_update_notice(monkeypatch):
    monkeypatch.setattr(up, "check_for_update", lambda **_k: "9.9.9")
    rc, out = _run(["about"], monkeypatch, tty=True)
    assert rc == 0
    assert "About" in out
    assert _EXPECTED_NOTICE in out


def test_subcommand_on_tty_no_update_no_notice(monkeypatch):
    """Covers _maybe_notice's `if latest:` false branch (no update available)."""
    monkeypatch.setattr(up, "check_for_update", lambda **_k: None)
    rc, out = _run(["about"], monkeypatch, tty=True)
    assert rc == 0
    assert "About" in out
    assert "A new release" not in out


# ---------------------------------------------------------------------------
# encoding hardening + NFC argv
# ---------------------------------------------------------------------------


def test_harden_stream_makes_unencodable_writes_not_raise():
    raw = io.BytesIO()
    w = io.TextIOWrapper(raw, encoding="ascii", newline="")
    _harden_stream(w)
    w.write("box ─ em — dot · é")  # would raise UnicodeEncodeError pre-fix
    w.flush()
    assert b"?" in raw.getvalue()  # degraded, not crashed


def test_harden_stream_noop_on_stringio():
    _harden_stream(io.StringIO())  # no reconfigure attr -> silent no-op


def test_resume_accent_alias_accepts_nfd_argv(monkeypatch):
    nfd = unicodedata.normalize("NFD", "résumé")
    assert nfd != "résumé"  # decomposed form differs
    rc, out = _run([nfd], monkeypatch)
    assert rc == 0 and "Résumé" in out


# ---------------------------------------------------------------------------
# section-name coherence
# ---------------------------------------------------------------------------


def test_section_names_single_source_of_truth():
    """render.SECTIONS (display titles) and __main__._SEC_* (subcommand
    names) must describe the same five logical sections; the only mapping
    is Résumé<->resume (plus the résumé accent alias)."""
    display = {name for name, _ in render.SECTIONS}
    assert display == {"About", "Projects", "Résumé", "Contact", "Blog"}
    canonical = {
        _m._SEC_ABOUT,
        _m._SEC_PROJECTS,
        _m._SEC_RESUME,
        _m._SEC_CONTACT,
        _m._SEC_BLOG,
    }
    assert canonical == {"about", "projects", "resume", "contact", "blog"}
    mapped = {("resume" if d == "Résumé" else d).lower() for d in display}
    assert mapped == canonical
    assert _m._SEC_RESUME_ACCENT == "résumé"


# ---------------------------------------------------------------------------
# CardError → failure_ui
# ---------------------------------------------------------------------------


def test_card_error_non_tty_rc1_stderr(monkeypatch, capsys):
    """When load_card raises CardError in non-tty mode, rc==1 and message+contact
    appear on stderr."""
    monkeypatch.setattr(
        _m.content,
        "load_card",
        lambda **k: (_ for _ in ()).throw(CardError("no usable data")),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    rc = main([])
    cap = capsys.readouterr()
    assert rc == 1
    assert "no usable data" in cap.err
    assert "henryandrecastillo@gmail.com" in cap.err


def test_card_error_tty_calls_show_no_data(monkeypatch):
    """When load_card raises CardError in tty mode, show_no_data is called."""
    monkeypatch.setattr(
        _m.content,
        "load_card",
        lambda **k: (_ for _ in ()).throw(CardError("no usable data")),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_show_no_data(message, *, url, is_tty, console, **kw):
        captured["message"] = message
        captured["url"] = url
        captured["is_tty"] = is_tty
        return 99

    monkeypatch.setattr(_m.failure_ui, "show_no_data", fake_show_no_data)
    rc = main([])
    assert rc == 99
    assert "no usable data" in captured["message"]
    assert captured["is_tty"] is True


# ---------------------------------------------------------------------------
# --debug flag
# ---------------------------------------------------------------------------


def test_debug_flag_calls_log_configure(monkeypatch, stub_tui_run):
    """--debug must call _log.configure(debug=True)."""
    configured: dict = {}
    original_configure = _log.configure

    def fake_configure(*, debug):
        configured["debug"] = debug
        original_configure(debug=debug)

    monkeypatch.setattr(_m._log, "configure", fake_configure)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main(["--debug"])
    assert rc == 0
    assert configured.get("debug") is True


def test_no_debug_flag_calls_log_configure_false(monkeypatch, stub_tui_run):
    """Without --debug, _log.configure(debug=False)."""
    configured: dict = {}
    original_configure = _log.configure

    def fake_configure(*, debug):
        configured["debug"] = debug
        original_configure(debug=debug)

    monkeypatch.setattr(_m._log, "configure", fake_configure)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    assert rc == 0
    assert configured.get("debug") is False


# ---------------------------------------------------------------------------
# Demos badge: tty no-subcommand + check_for_update→version → tui.run receives
# update_available=True
# ---------------------------------------------------------------------------


def test_tui_run_receives_update_available_true_when_update_exists(monkeypatch):
    """When check_for_update returns a version, tui.run gets update_available=True."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_run(card, *, console, update_available, **kw):
        captured["update_available"] = update_available

    monkeypatch.setattr(_m.tui, "run", fake_run)
    rc = main([])
    assert rc == 0
    assert captured.get("update_available") is True


def test_tui_run_receives_update_available_false_when_no_update(monkeypatch):
    """When check_for_update returns None, tui.run gets update_available=False."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_run(card, *, console, update_available, **kw):
        captured["update_available"] = update_available

    monkeypatch.setattr(_m.tui, "run", fake_run)
    rc = main([])
    assert rc == 0
    assert captured.get("update_available") is False


def test_tui_run_receives_update_available_false_when_check_suppressed(monkeypatch):
    """When --no-update-check is set, tui.run gets update_available=False."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_run(card, *, console, update_available, **kw):
        captured["update_available"] = update_available

    monkeypatch.setattr(_m.tui, "run", fake_run)
    rc = main(["--no-update-check"])
    assert rc == 0
    assert captured.get("update_available") is False


# ---------------------------------------------------------------------------
# new_demos wiring: __main__ computes new_demos only when update available
# ---------------------------------------------------------------------------


def _card_with_high_min_version():
    """Return a card whose sole demo has min_version=999.0.0 (always newer)."""
    demo = {
        "name": "futuredemo",
        "summary": "from the future",
        "min_version": "999.0.0",
    }
    doc = {**_VALID_DOC, "demos": [demo]}
    return parse_card(doc)


def test_tui_run_receives_nonempty_new_demos_when_update_exists(monkeypatch):
    """When update available + card has a high min_version demo, new_demos non-empty."""
    high_card = _card_with_high_min_version()
    monkeypatch.setattr(_m.content, "load_card", lambda **k: high_card)
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr(up, "current_version", lambda: __version__)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_run(card, *, console, update_available, new_demos, **kw):
        captured["update_available"] = update_available
        captured["new_demos"] = list(new_demos)

    monkeypatch.setattr(_m.tui, "run", fake_run)
    rc = main([])
    assert rc == 0
    assert captured.get("update_available") is True
    assert len(captured.get("new_demos", [])) == 1
    assert captured["new_demos"][0].name == "futuredemo"


def test_tui_run_receives_empty_new_demos_when_no_update(monkeypatch):
    """When no update available, new_demos passed as [] regardless of card demos."""
    high_card = _card_with_high_min_version()
    monkeypatch.setattr(_m.content, "load_card", lambda **k: high_card)
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    captured: dict = {}

    def fake_run(card, *, console, update_available, new_demos, **kw):
        captured["update_available"] = update_available
        captured["new_demos"] = list(new_demos)

    monkeypatch.setattr(_m.tui, "run", fake_run)
    rc = main([])
    assert rc == 0
    assert captured.get("update_available") is False
    assert captured.get("new_demos") == []
