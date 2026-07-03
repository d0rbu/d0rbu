"""Friendly 'no usable profile data' screen: press-any-key or countdown."""

from __future__ import annotations

import select
import sys
import termios
import time
import webbrowser
from collections.abc import Callable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from henry_castillo import _log

_COUNTDOWN = 5
_GUIDANCE = (
    "Try: uvx --refresh henry-castillo  (or update the package).\n"
    "If this persists, contact henryandrecastillo@gmail.com."
)


def _default_wait_for_keypress(timeout: float, *, stream_fd: int | None = None) -> bool:
    # Use TCSANOW (not tty.setcbreak's default TCSADRAIN) so any data already
    # in the kernel buffer is not discarded before select() sees it.
    fd = sys.stdin.fileno() if stream_fd is None else stream_fd
    old = termios.tcgetattr(fd)
    new = list(old)
    new[3] &= ~(termios.ICANON | termios.ECHO)
    new[6][termios.VMIN] = 1
    new[6][termios.VTIME] = 0
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
        ready, _, _ = select.select([fd], [], [], timeout)
        return bool(ready)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _default_open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError) as exc:
        _log.logger.warning("browser launch failed: {}", exc)
        print(f"Couldn't open a browser; visit {url}")


def show_no_data(
    message: str,
    *,
    url: str,
    is_tty: bool,
    console: Console,
    wait_for_keypress: Callable[[float], bool] | None = None,
    open_url: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> int:
    text = f"{message}\n\n{_GUIDANCE}"
    if not is_tty:
        print(text, file=sys.stderr)
        return 1
    _wait = wait_for_keypress or _default_wait_for_keypress
    _open = open_url or _default_open_url
    do_sleep = sleep or time.sleep
    console.print(Panel(Text(text), title="henry-castillo", border_style="red"))
    for n in range(_COUNTDOWN, 0, -1):
        console.print(
            Text(
                f"Opening {url} in {n}…  (press any key to exit)",
                style="dim",
            )
        )
        if _wait(1.0):
            return 0
        do_sleep(0)
    _open(url)
    return 0
