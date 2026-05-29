import importlib
import os
import subprocess
import sys

from henry_castillo import _log


def test_logger_silent_by_default(capsys):
    _log.configure(debug=False)
    _log.logger.error("should-not-appear")
    captured = capsys.readouterr()
    assert "should-not-appear" not in captured.err
    assert "should-not-appear" not in captured.out


def test_logger_emits_on_debug(capsys):
    _log.configure(debug=True)
    try:
        _log.logger.error("diag-msg-xyz")
        captured = capsys.readouterr()
        assert "diag-msg-xyz" in captured.err
    finally:
        _log.configure(debug=False)  # restore global state


def test_configure_idempotent_toggle(capsys):
    _log.configure(debug=True)
    _log.configure(debug=True)  # second enable must not double-sink
    _log.configure(debug=False)
    _log.configure(debug=False)  # second disable must be a no-op
    _log.logger.error("none-xyz")
    assert "none-xyz" not in capsys.readouterr().err


def test_debug_enabled_cli_flag_wins():
    assert _log.debug_enabled(cli_flag=True) is True


def test_cli_flag_overrides_falsey_env(monkeypatch):
    """cli_flag=True wins even when HENRY_CASTILLO_DEBUG is a falsey value like '0'."""
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "0")
    assert _log.debug_enabled(cli_flag=True) is True


def test_debug_enabled_strip_lower_normalization(monkeypatch):
    """debug_enabled strips whitespace and lower-cases the env value before lookup."""
    # Leading/trailing spaces, mixed case — all treated as falsey when value is 'off'
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "  OFF  ")
    assert _log.debug_enabled(cli_flag=False) is False

    # Whitespace-only string strips to "" which is in _FALSEY
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "   ")
    assert _log.debug_enabled(cli_flag=False) is False

    # Truthy values with mixed case / spaces
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "TRUE")
    assert _log.debug_enabled(cli_flag=False) is True

    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "  TrUe  ")
    assert _log.debug_enabled(cli_flag=False) is True

    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "FALSE")
    assert _log.debug_enabled(cli_flag=False) is False


def test_debug_enabled_env(monkeypatch):
    monkeypatch.delenv("HENRY_CASTILLO_DEBUG", raising=False)
    assert _log.debug_enabled(cli_flag=False) is False
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "1")
    assert _log.debug_enabled(cli_flag=False) is True
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "true")
    assert _log.debug_enabled(cli_flag=False) is True
    for falsey in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("HENRY_CASTILLO_DEBUG", falsey)
        assert _log.debug_enabled(cli_flag=False) is False


def test_module_import_is_silent(capsys):
    importlib.reload(_log)
    _log.logger.info("import-noise-xyz")
    out = capsys.readouterr()
    assert "import-noise-xyz" not in out.err and "import-noise-xyz" not in out.out
    _log.configure(debug=False)  # leave global state clean


# ---------------------------------------------------------------------------
# Subprocess-based tests: observe REAL (fd-level) stderr so loguru's default
# sink cannot sneak past capsys's Python-object-level patch.
# ---------------------------------------------------------------------------


def _run_child(
    code: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    run_env = {**os.environ}
    if env:
        run_env.update(env)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
        timeout=30,
    )


def test_import_is_truly_silent_subprocess():
    """Importing _log and logging without configure() must emit NOTHING on
    real (fd-level) stderr — kills the 'delete logger.remove()' mutation
    that capsys cannot catch (loguru's default sink bypasses capsys)."""
    r = _run_child(
        "import henry_castillo._log as m; "
        "m.logger.error('leak-xyz'); m.logger.info('leak2-xyz')"
    )
    assert r.returncode == 0, r.stderr
    assert "leak-xyz" not in r.stderr
    assert "leak2-xyz" not in r.stderr
    assert r.stdout == ""


def test_configure_false_is_silent_subprocess():
    r = _run_child(
        "import henry_castillo._log as m; m.configure(debug=False); "
        "m.logger.error('silent-xyz')"
    )
    assert r.returncode == 0, r.stderr
    assert "silent-xyz" not in r.stderr


def test_configure_true_emits_on_real_stderr_subprocess():
    """configure(debug=True) must add a sink that reaches REAL stderr
    (fd-level), proving the debug path genuinely works end-to-end."""
    r = _run_child(
        "import henry_castillo._log as m; m.configure(debug=True); "
        "m.logger.error('shown-xyz')"
    )
    assert r.returncode == 0, r.stderr
    assert "shown-xyz" in r.stderr


def test_debug_enabled_env_drives_emit_subprocess():
    """End-to-end: HENRY_CASTILLO_DEBUG gates real-stderr output via the
    debug_enabled→configure path a real CLI would use."""
    code = (
        "import henry_castillo._log as m; "
        "m.configure(debug=m.debug_enabled(cli_flag=False)); "
        "m.logger.error('envgate-xyz')"
    )
    on = _run_child(code, env={"HENRY_CASTILLO_DEBUG": "1"})
    off = _run_child(code, env={"HENRY_CASTILLO_DEBUG": "0"})
    assert on.returncode == 0 and off.returncode == 0, (on.stderr, off.stderr)
    assert "envgate-xyz" in on.stderr
    assert "envgate-xyz" not in off.stderr
