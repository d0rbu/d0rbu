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
from henry_castillo import __version__
from henry_castillo.__main__ import (
    _harden_stream,
    _maybe_notice,
    _update_check_disabled_by_env,
    main,
)
from henry_castillo.content import Profile, Project, Resume

_EXPECTED_NOTICE = (
    f"A new release of henry-castillo is available: {__version__} -> 9.9.9. "
    f"Run `henry-castillo --update` to upgrade.\n"
)


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


def test_version_flag_exact(capsys):
    rc = main(["--version"])
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == f"henry-castillo {__version__}\n"
    assert cap.err == ""


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
def test_env_contract_drives_check_for_update(value, suppressed, monkeypatch):
    called = []
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", value)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or None)
    rc = main([])
    assert rc == 0
    assert (len(called) == 0) is suppressed


def test_env_contract_unset_not_suppressed(monkeypatch):
    called = []
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
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


def test_maybe_notice_positive_path_exact_real_notice(monkeypatch, capsys):
    """Positive path asserts the EXACT real notice (update_notice NOT mocked)."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr(up, "current_version", lambda: __version__)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == _EXPECTED_NOTICE


def test_maybe_notice_no_update_available_prints_nothing_extra(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_maybe_notice_suppressed_with_no_update_check_flag(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    rc = main(["--no-update-check"])
    out = capsys.readouterr().out
    assert rc == 0
    assert called == []
    assert "A new release" not in out


def test_maybe_notice_suppressed_by_env_var(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
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
    tmp_path, monkeypatch, capsys
):
    """End-to-end graceful-offline (pairs with the FIX-1 non-dict guard).

    Interactive TTY, update check ENABLED (flag off, env unset), but the
    real fetch path fails (``urlopen`` raises ``URLError``). ``main([])``
    must return 0, print NO update-notice line, and not raise -- proving the
    CLI's background update check can never crash the program on a network
    failure. ``check_for_update`` is NOT stubbed; only ``urlopen`` is, so the
    real ``fetch_latest_version`` error path executes.
    """
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(up, "cache_path", lambda: tmp_path / "u.json")

    def boom(*a, **k):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(up.urllib.request, "urlopen", boom)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_maybe_notice_under_tty_non_dict_body_prints_no_notice(
    tmp_path, monkeypatch, capsys
):
    """Same offline guarantee, end-to-end through the FIX-1 guard.

    A non-dict PyPI body (``null``) drives the real
    ``fetch_latest_version`` -> ``None`` path (the FIX-1 ``isinstance(data,
    dict)`` guard). ``check_for_update``/``fetch_latest_version`` are NOT
    stubbed; only ``urlopen``. ``main([])`` must return 0, print no notice,
    and not raise -- a real regression of the FIX-1 guard would surface here
    as an uncaught ``TypeError`` crashing the CLI.
    """
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(up, "cache_path", lambda: tmp_path / "u.json")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *_a):
            # Accept + ignore the size arg: production caps the body via
            # ``resp.read(_MAX_PYPI_BYTES + 1)``; the small body is returned
            # verbatim.
            return b"null"

    monkeypatch.setattr(up.urllib.request, "urlopen", lambda *a, **k: _Resp())
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A new release" not in out


def test_main_under_tty_info_null_body_rc0_no_notice_no_traceback(
    tmp_path, monkeypatch, capsys
):
    """End-to-end FIX 1 through the CLI: a ``{"info": null}`` PyPI body under
    an interactive TTY with the update check enabled must return rc 0, print
    NO update notice, and NOT raise a traceback.

    ``check_for_update``/``fetch_latest_version`` are NOT stubbed; only
    ``urlopen``. A regression of the nested-``info`` guard would surface here
    as an uncaught ``TypeError`` crashing ``main([])`` on every interactive
    run.
    """
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(_m.tui, "run", lambda *_a, **_k: None)
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


def test_subcommand_projects_tag_match(monkeypatch):
    monkeypatch.setattr(
        _m.content,
        "load_projects",
        lambda: [
            Project("p-alpha", "d", "https://a.io", ["ml", "python"]),
            Project("p-beta", "d", "https://b.io", ["web"]),
        ],
    )
    rc, out = _run(["projects", "--tag", "ml"], monkeypatch)
    assert rc == 0
    assert "p-alpha" in out
    assert "p-beta" not in out


def test_subcommand_resume_and_accent_alias(monkeypatch):
    rc, out = _run(["resume"], monkeypatch)
    assert rc == 0 and "Résumé" in out
    rc2, out2 = _run(["résumé"], monkeypatch)
    assert rc2 == 0 and "Résumé" in out2


def test_subcommand_resume_open_draft_no_pdf(monkeypatch):
    """The committed DRAFT résumé has an empty pdf -> --open must NOT open
    a browser and must print the no-link message."""
    opened: list[str] = []
    monkeypatch.setattr("henry_castillo.__main__._open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0
    assert opened == []
    assert "no résumé" in out.lower()


def test_resume_open_with_pdf(monkeypatch):
    monkeypatch.setattr(
        _m.content,
        "load_profile",
        lambda: Profile(resume=Resume(pdf="https://x/cv.pdf")),
    )
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, _ = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == ["https://x/cv.pdf"]


def test_resume_open_without_pdf_message(monkeypatch):
    monkeypatch.setattr(_m.content, "load_profile", Profile)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["resume", "--open"], monkeypatch)
    assert rc == 0 and opened == []
    assert "no résumé" in out.lower()


def test_subcommand_contact(monkeypatch):
    rc, out = _run(["contact"], monkeypatch)
    assert rc == 0 and "Contact" in out


def test_subcommand_substack(monkeypatch):
    rc, out = _run(["substack"], monkeypatch)
    assert rc == 0 and "Substack" in out


def test_default_non_tty_renders_all_plain(monkeypatch):
    rc, out = _run([], monkeypatch, tty=False)
    assert rc == 0
    # plain full render: banner + every section, no interactive prompt
    assert "About" in out and "Projects" in out and "Contact" in out


def test_default_tty_runs_interactive_loop(monkeypatch):
    called = {}

    def fake_run(profile, projects, *, console, **kw):
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


def test_subcommand_substack_with_url_opens(monkeypatch):
    monkeypatch.setattr(
        _m.content,
        "load_profile",
        lambda: Profile(links={"substack": "https://s.substack.com"}),
    )
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["substack"], monkeypatch)
    assert rc == 0 and "Substack" in out
    assert opened == ["https://s.substack.com"]


def test_render_section_unknown_section_is_noop(monkeypatch):
    """Cover the fallthrough branch in _render_section for unrecognized section."""
    buf = io.StringIO()
    console = Console(file=buf, highlight=False)
    args = argparse.Namespace(section="__unknown__", no_update_check=True)
    rc = _m._render_section(args, console)
    assert rc == 0
    assert buf.getvalue() == ""


def test_subcommand_substack_without_url_does_not_open(monkeypatch):
    monkeypatch.setattr(_m.content, "load_profile", Profile)
    opened: list[str] = []
    monkeypatch.setattr(_m, "_open_url", opened.append)
    rc, out = _run(["substack"], monkeypatch)
    assert rc == 0 and opened == []
    assert "Substack" in out


def test_subcommand_on_tty_emits_update_notice(monkeypatch):
    monkeypatch.setattr(up, "check_for_update", lambda **_k: "9.9.9")
    rc, out = _run(["about"], monkeypatch, tty=True)
    assert rc == 0
    assert "About" in out
    assert _EXPECTED_NOTICE in out


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
