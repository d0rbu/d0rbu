import subprocess

import henry_castillo.update as up
from henry_castillo.__main__ import main


def test_version_flag(capsys):
    rc = main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_check_update_reports(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    rc = main(["--check-update"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "9.9.9" in out


def test_check_update_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    rc = main(["--check-update"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "up to date" in out.lower()


def test_update_invokes_perform(monkeypatch):
    called = {}
    monkeypatch.setattr(up, "perform_update", lambda: called.setdefault("x", 0) or 0)
    rc = main(["--update"])
    assert rc == 0
    assert "x" in called


def test_default_run_is_quiet_and_zero(capsys):
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_console_entrypoint_still_runs():
    r = subprocess.run(["henry-castillo"], capture_output=True, text=True, check=False)
    assert r.returncode == 0
    assert "henry-castillo" in r.stdout


def test_maybe_notice_shown_when_tty_and_update_available(monkeypatch, capsys):
    """_maybe_notice prints the update notice when stdout is a TTY and update exists."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: "9.9.9")
    monkeypatch.setattr(up, "update_notice", lambda v: f"UPDATE AVAILABLE: {v}")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "UPDATE AVAILABLE: 9.9.9" in out


def test_maybe_notice_suppressed_with_no_update_check(monkeypatch, capsys):
    """_maybe_notice is skipped when --no-update-check is passed."""
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main(["--no-update-check"])
    capsys.readouterr()
    assert rc == 0
    assert len(called) == 0


def test_maybe_notice_suppressed_by_env_var(monkeypatch, capsys):
    """_maybe_notice is skipped when HENRY_CASTILLO_NO_UPDATE_CHECK env var is set."""
    called = []
    monkeypatch.setattr(up, "check_for_update", lambda **k: called.append(1) or "9.9.9")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("HENRY_CASTILLO_NO_UPDATE_CHECK", "1")
    rc = main([])
    capsys.readouterr()
    assert rc == 0
    assert len(called) == 0


def test_maybe_notice_no_update_available(monkeypatch, capsys):
    """_maybe_notice prints nothing when check_for_update returns None (up to date)."""
    monkeypatch.setattr(up, "check_for_update", lambda **k: None)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    # No update notice should appear beyond the standard banner lines
    assert "henry-castillo" in out
    assert "new release" not in out.lower()
