import json
import socket
import urllib.request

import pytest
from hypothesis import HealthCheck as _HealthCheck
from hypothesis import settings as _hyp_settings

import henry_castillo.__main__ as _main_mod
from henry_castillo import content

_hyp_settings.register_profile(
    "ci",
    derandomize=True,
    deadline=None,
    print_blob=False,
    suppress_health_check=[_HealthCheck.function_scoped_fixture],
)
_hyp_settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Valid card document used to seed cache and build fixtures.
# ---------------------------------------------------------------------------

_VALID_CARD_DOC: dict = {
    "schema_version": 1,
    "profile": {
        "name": "Henry Castillo",
        "handle": "d0rbu",
        "tagline": "ML / interpretability researcher",
        "about": "I work on mechanistic interpretability.",
        "email": "henryandrecastillo@gmail.com",
        "links": {
            "github": "https://github.com/d0rbu",
            "blog": "https://henrycastillo.substack.com",
        },
    },
    "projects": [
        {
            "name": "saebench",
            "blurb": "SAE eval suite",
            "url": "https://github.com/d0rbu/saebench",
            "tags": ["interp", "python"],
        },
        {
            "name": "moe-router",
            "blurb": "routing study",
            "url": "https://github.com/d0rbu/moe-router",
            "tags": ["moe"],
        },
    ],
    "resume": {
        "pdf": "",
        "experience": [
            {
                "role": "Researcher",
                "org": "Acme",
                "period": "2024",
                "summary": "Did research",
            }
        ],
        "education": [{"degree": "BS", "school": "MIT", "period": "2020"}],
        "highlights": ["Published paper on SAE evaluation"],
    },
}

# Verify the seed doc is schema-valid at import time so a typo here is caught early.
assert content.parse_card(_VALID_CARD_DOC) is not None


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _deny(*args, **kwargs):
        raise RuntimeError("Real network access is blocked in tests")

    monkeypatch.setattr(urllib.request, "urlopen", _deny)
    monkeypatch.setattr(socket, "socket", _deny)


@pytest.fixture(autouse=True)
def _env_hygiene(monkeypatch):
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)


@pytest.fixture(autouse=True)
def _seed_card_cache(monkeypatch, tmp_path):
    """Seed the XDG cache with a valid card.json so load_card() succeeds offline.

    - Sets XDG_CACHE_HOME to a per-session tmp dir.
    - Writes a valid card.json to <tmp>/henry-castillo/card.json.
    - Patches content._default_fetch to raise OSError (simulates network
      failure) so load_card's fetch step fails and falls through to the cache.
    - Sets HENRY_CASTILLO_CARD_URL to an unreachable URL so subprocesses
      also fail the fetch and fall through to their own seeded cache
      (subprocess tests that need the env var set up their own caches).

    This runs after _env_hygiene (which deletes XDG_CACHE_HOME), so we
    always write a fresh seed.
    """
    cache_dir = tmp_path / "xdg_cache"
    card_dir = cache_dir / "henry-castillo"
    card_dir.mkdir(parents=True)
    card_file = card_dir / "card.json"
    card_file.write_text(json.dumps(_VALID_CARD_DOC), encoding="utf-8")

    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    monkeypatch.setenv("HENRY_CASTILLO_CARD_URL", "http://127.0.0.1:1/card.json")

    # Re-patch urlopen to raise OSError (instead of RuntimeError from
    # _block_network) so that content._default_fetch fails gracefully and
    # load_card falls back to the seeded cache above.
    # The real_network fixture in test_card.py will override this with the
    # real urlopen for tests that genuinely need localhost HTTP.
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(
            OSError("simulated offline — no network in tests")
        ),
    )


@pytest.fixture
def valid_card() -> content.Card:
    """Return a valid Card built from the shared seed document."""
    return content.parse_card(_VALID_CARD_DOC)


@pytest.fixture
def stub_tui_run(monkeypatch):
    """Replace the interactive loop with a silent no-op so a tty-default
    main([]) does not enter questionary under pytest."""
    monkeypatch.setattr(_main_mod.tui, "run", lambda *_a, **_k: None)
