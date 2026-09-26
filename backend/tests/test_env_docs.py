"""
The deployment env vars are documented in .env.example files that nothing
executes, so they drift silently: a rename in code leaves the instructions
pointing at a variable that no longer exists, which on Render means a
deployment that looks configured and is not.

These tests read the real examples and cross-check them against the code.
"""
import pathlib
import re

BACKEND = pathlib.Path(__file__).parent.parent
FRONTEND = BACKEND.parent / "frontend"


def _documented(path: pathlib.Path) -> set:
    text = path.read_text(encoding="utf-8")
    # Only the KEY= at the start of a line, ignoring commented-out examples.
    return {
        m.group(1)
        for m in re.finditer(r"^([A-Z][A-Z0-9_]*)\s*=", text, re.MULTILINE)
    }


def test_backend_env_example_lists_every_documented_safety_var():
    documented = _documented(BACKEND / ".env.example")
    for var in (
        "API_SECRET",
        "ALLOW_UNAUTHENTICATED_CONTROL",
        "AUTO_START",
        "LIVE_TRADING_ENABLED",
        "PAPER_TRADING",
    ):
        assert var in documented, f"{var} is read by the code but missing from .env.example"


def test_every_env_var_the_code_reads_is_documented():
    """
    Catch the rename case: a getenv() whose name is absent from .env.example.
    Only deployment-relevant vars are checked, so unrelated reads do not fail.
    """
    documented = _documented(BACKEND / ".env.example")
    interesting = re.compile(
        r'getenv\(\s*"([A-Z][A-Z0-9_]*)"', re.MULTILINE
    )

    missing = {}
    for path in BACKEND.rglob("*.py"):
        if "venv" in path.parts or "tests" in path.parts:
            continue
        for name in interesting.findall(path.read_text(encoding="utf-8")):
            if name.startswith("BINANCE_") or name.startswith("EMAIL_"):
                continue                      # credentials, not deployment config
            if name not in documented:
                missing.setdefault(name, []).append(path.name)

    assert not missing, f"read by the code but undocumented in .env.example: {missing}"


def test_frontend_env_example_explains_the_api_secret():
    """
    Without this the operator sets API_SECRET on Render, the control endpoints
    come back 503, and there is no hint on the frontend side that the same
    value is needed here.
    """
    text = (FRONTEND / ".env.example").read_text(encoding="utf-8")
    assert "VITE_API_SECRET" in text
    assert "API_SECRET" in text


def test_secret_generation_hint_is_present():
    """A 32-byte random secret, not something a human would pick."""
    text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    assert "token_urlsafe" in text
