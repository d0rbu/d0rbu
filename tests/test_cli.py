"""Exhaustive behavioral tests for the CLI entrypoint (henry_castillo.__main__).

Exact-output assertions where the contract is exact. The argparse
``allow_abbrev=False`` lock and the explicit update-check env contract are
pinned here. No real network (see tests/conftest.py).
"""

import argparse
import importlib.metadata

import pytest
from packaging.version import Version

import henry_castillo.update as up
from henry_castillo import __version__
from henry_castillo.__main__ import _maybe_notice, _update_check_disabled_by_env, main

_DEFAULT_STDOUT = (
    f"henry-castillo {__version__}\n"
    "Personal website + CLI business card — scaffold.\n"
    "CLI features land in a later release.\n"
    "Repo: https://github.com/d0rbu/d0rbu\n"
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
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or None)
    rc = main([])
    assert rc == 0
    assert (len(called) == 0) is suppressed


def test_env_contract_unset_not_suppressed(monkeypatch):
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


def test_maybe_notice_positive_path_exact_real_notice(monkeypatch, capsys):
    """Positive path asserts the EXACT real notice (update_notice NOT mocked)."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr(up, "current_version", lambda: __version__)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == _DEFAULT_STDOUT + (
        f"A new release of henry-castillo is available: {__version__} -> 9.9.9. "
        f"Run `henry-castillo --update` to upgrade.\n"
    )


def test_maybe_notice_no_update_available_prints_nothing_extra(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == _DEFAULT_STDOUT


def test_maybe_notice_suppressed_with_no_update_check_flag(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main(["--no-update-check"])
    assert capsys.readouterr().out == _DEFAULT_STDOUT
    assert rc == 0
    assert called == []


def test_maybe_notice_suppressed_by_env_var(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", "1")
    rc = main([])
    assert capsys.readouterr().out == _DEFAULT_STDOUT
    assert rc == 0
    assert called == []


def test_maybe_notice_suppressed_when_not_tty_and_no_network(monkeypatch, capsys):
    """Non-tty must suppress; conftest blocks real network so a leak would fail."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    # check_for_update is NOT mocked: if the guard were wrong it would attempt
    # a real fetch, which the autouse network block turns into RuntimeError.
    rc = main([])
    assert capsys.readouterr().out == _DEFAULT_STDOUT
    assert rc == 0


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
    assert cap.out == _DEFAULT_STDOUT
    assert cap.err == ""


def test_main_uses_sys_argv_when_argv_is_none(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["henry-castillo"])
    rc = main(None)
    cap = capsys.readouterr()
    assert rc == 0
    assert cap.out == _DEFAULT_STDOUT


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
