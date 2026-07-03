"""loguru wiring: silent by default; stderr DEBUG sink only when enabled."""

from __future__ import annotations

import os
import sys

from loguru import logger

logger.remove()  # drop loguru's default stderr sink at import → silent

_FALSEY = {"", "0", "false", "no", "off"}
_state: dict[str, int | None] = {"sink_id": None}


def debug_enabled(*, cli_flag: bool) -> bool:
    if cli_flag:
        return True
    val = os.environ.get("HENRY_CASTILLO_DEBUG")
    return val is not None and val.strip().lower() not in _FALSEY


def configure(*, debug: bool) -> None:
    if _state["sink_id"] is not None:
        logger.remove(_state["sink_id"])
        _state["sink_id"] = None
    if debug:
        _state["sink_id"] = logger.add(sys.stderr, level="DEBUG")


__all__ = ["configure", "debug_enabled", "logger"]
