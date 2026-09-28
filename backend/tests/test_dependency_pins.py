"""
Dependency pinning tests.

A Render build failed by backtracking pandas from 1.5.2 down to 1.4.4 and
trying to compile it from source. Nothing about the code was wrong; the
requirements were simply unpinned, which left the resolver free to search and
old pip free to misjudge. These tests keep the numeric stack pinned and keep
the deploy using binary-only installs so that failure mode cannot come back.
"""
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).parent.parent


def _requirements() -> dict:
    out = {}
    for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=!~\[;]", line, 1)[0].strip().lower()
        out[name] = line
    return out


@pytest.mark.parametrize("pkg", ["pandas", "numpy"])
def test_numeric_stack_is_pinned(pkg):
    """Unpinned pandas/numpy is what let the resolver wander into an sdist."""
    req = _requirements().get(pkg)
    assert req, f"{pkg} missing from requirements.txt"
    assert re.search(r"==\s*\d+\.\d+", req), (
        f"{pkg} must be pinned to an exact version, got {req!r}"
    )


def test_no_requirement_is_fully_unpinned():
    """A bare package name lets the resolver pick a different major each deploy."""
    loose = [n for n, line in _requirements().items()
             if not re.search(r"==\s*\d", line)]
    assert not loose, f"unpinned requirements: {sorted(loose)}"


def test_render_build_upgrades_pip_and_installs_binary_only():
    """
    Two guards for the failure above: pip newer than the packages it installs,
    and no source builds. Without --only-binary, a missing wheel still turns
    into a multi-minute compile before it errors out.
    """
    yaml_text = (BACKEND / "render.yaml").read_text(encoding="utf-8")
    build = yaml_text.split("buildCommand:", 1)[1].split("startCommand:", 1)[0]
    assert "--upgrade pip" in build, "build must upgrade pip before installing"
    assert "--only-binary" in build, "build must forbid source builds"


def test_render_python_version_is_pinned():
    """An unpinned interpreter silently changes what production runs."""
    yaml_text = (BACKEND / "render.yaml").read_text(encoding="utf-8")
    assert re.search(r'pythonVersion:\s*"3\.\d+(\.\d+)?"', yaml_text)
    assert re.search(r"PYTHON_VERSION[\s\S]{0,40}?value:\s*3\.\d+\.\d+", yaml_text), \
        "PYTHON_VERSION should be an exact patch version, not a major.minor"
