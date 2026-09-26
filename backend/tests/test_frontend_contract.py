"""
Static consistency between the frontend and the backend.

There is no browser in this environment, so nothing here can say the page looks
right. What it can do is catch the failure modes that make a page visibly
broken, and that are invisible in a passing build:

  1. a component importing a name that is not exported -> blank page
  2. api.js calling a path or verb the backend does not serve -> silent 404,
     which shows up as a card stuck on "-"
  3. a className with no rule in App.css -> renders unstyled

(3) is the one that bit: .qty-col sat next to .time-col in the same table
header and was never added, so the Qty column was un-dimmed, free to wrap, and
stayed visible on mobile where Time is hidden. .stat-content was a flex child
with no min-width:0, so a long value overflowed its card. .sc-icon had a
background and colour set inline but no box at all. All three compiled
cleanly and all three were wrong.
"""
import pathlib
import re

import pytest

FRONT = pathlib.Path(__file__).parent.parent.parent / "frontend" / "src"
BACKEND = pathlib.Path(__file__).parent.parent

# `.page` already carries the layout, so these two were a second name for it.
KNOWN_DEAD_CLASSES: set[str] = set()

CLASSNAME_RE = re.compile(r"""className\s*=\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)""")
TEMPLATE_RE = re.compile(r"\$\{[^}]*\}")
NOT_A_CLASS = {"true", "false", "null", "undefined", "NaN"}


def _jsx_files():
    return sorted(FRONT.rglob("*.jsx"))


def _css_classes() -> set:
    css = (FRONT / "App.css").read_text(encoding="utf-8")
    return set(re.findall(r"\.([A-Za-z][\w-]*)", css))


def _backend_routes() -> set:
    src = (BACKEND / "api" / "routes.py").read_text(encoding="utf-8")
    return {
        (m.group(1).upper(), m.group(2))
        for m in re.finditer(r'@router\.(get|post|delete|put|patch)\("([^"]+)"', src)
    }


# ── CSS ───────────────────────────────────────────────────────────────────────

def test_every_class_used_in_jsx_has_a_rule():
    """A typo'd or forgotten class name renders unstyled and looks broken."""
    defined = _css_classes()
    missing = []

    for jsx in _jsx_files():
        for block in CLASSNAME_RE.finditer(jsx.read_text(encoding="utf-8")):
            raw = block.group(1) or block.group(2) or block.group(3) or ""
            for token in TEMPLATE_RE.sub(" ", raw).split():
                for name in re.findall(r"[A-Za-z][\w-]*", token):
                    if name in NOT_A_CLASS or name in KNOWN_DEAD_CLASSES:
                        continue
                    if name not in defined:
                        missing.append(f"{jsx.name}: .{name}")

    assert not missing, "classNames with no rule in App.css:\n  " + "\n  ".join(missing)


def test_the_css_check_actually_inspects_classes():
    """Guard against the matcher silently going quiet and passing everything."""
    defined = _css_classes()
    checked = 0
    for jsx in _jsx_files():
        for block in CLASSNAME_RE.finditer(jsx.read_text(encoding="utf-8")):
            raw = block.group(1) or block.group(2) or block.group(3) or ""
            checked += len(TEMPLATE_RE.sub(" ", raw).split())
    assert checked > 200, f"only {checked} class tokens inspected, matcher is broken"
    assert "stat-card" in defined, "sanity: a known class should be found"


# ── imports ───────────────────────────────────────────────────────────────────

def test_relative_imports_resolve_and_are_exported():
    bad = []
    for jsx in _jsx_files():
        text = jsx.read_text(encoding="utf-8")
        for block in re.finditer(r'import\s*\{([^}]+)\}\s*from\s*"([^"]+)"', text):
            names, src = block.group(1), block.group(2)
            if not src.startswith("."):
                continue                      # a package, e.g. lucide-react
            target = (jsx.parent / src).resolve()
            if target.suffix == "":
                for cand in (target.with_suffix(".jsx"), target.with_suffix(".js")):
                    if cand.exists():
                        target = cand
                        break
            if not target.exists():
                bad.append(f"{jsx.name}: cannot resolve {src}")
                continue
            ttext = target.read_text(encoding="utf-8")
            for raw in names.split(","):
                name = raw.split(" as ")[0].strip()
                if not name:
                    continue
                if not (
                    re.search(rf"export\s+(?:const|function|default)\s+{re.escape(name)}\b", ttext)
                    or re.search(rf"export\s*\{{[^}}]*\b{re.escape(name)}\b", ttext)
                ):
                    bad.append(f"{jsx.name}: `{name}` is not exported by {src}")

    assert not bad, "broken imports:\n  " + "\n  ".join(bad)


# ── api.js vs routes ──────────────────────────────────────────────────────────

def test_every_api_call_maps_to_a_real_route():
    api = (FRONT / "services" / "api.js").read_text(encoding="utf-8")
    routes = _backend_routes()
    bad = []

    for m in re.finditer(r"request\(\s*[`\"]([^`\"]+)[`\"]([^)]*)\)", api):
        raw, tail = m.group(1), m.group(2)
        verb = re.search(r'method:\s*"(POST|DELETE|PUT|PATCH)"', tail)
        verb = verb.group(1) if verb else "GET"
        path = raw.split("?")[0]

        if not path.startswith("/"):
            continue
        if "${" in path:
            prefix = path.split("${")[0]
            hit = any(
                p.startswith(prefix) and "{" in p for _, p in routes
            ) or any(p == prefix for _, p in routes)
            if not hit:
                bad.append(f"{raw} matches no backend route")
            continue

        if (verb, path) in routes:
            continue
        served = sorted(v for v, p in routes if p == path)
        if served:
            bad.append(f"calls {verb} {path}, backend only serves {served}")
        else:
            bad.append(f"{verb} {path} is not a backend route")

    assert not bad, "api.js calls with no matching route:\n  " + "\n  ".join(bad)


def test_the_route_check_actually_inspects_calls():
    api = (FRONT / "services" / "api.js").read_text(encoding="utf-8")
    calls = re.findall(r"request\(\s*[`\"]([^`\"]+)[`\"]", api)

    assert len(calls) > 15, f"only {len(calls)} request() calls inspected, matcher is broken"
    # The watchlist and symbol-search calls carry interpolated query strings, so
    # match on the static prefix rather than the whole literal.
    assert any(c == "/watchlist" for c in calls), "sanity: watchlist call not found"
    assert any(c.startswith("/market/symbols") for c in calls), "sanity: symbol search not found"
