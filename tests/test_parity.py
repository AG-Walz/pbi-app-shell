"""Does the house icon set still match the apps it was extracted from?

The package's admission rule is a claim about the consuming apps, and a claim about code
that lives somewhere else rots quietly. These tests re-measure it: every glyph name a
consuming app shares with :data:`HOUSE_GLYPHS` must still be drawn identically, or the
package has silently changed how that app looks.

They read the apps as *source*, since they may not even be importable from here (one lives
in a conda env, and each runs with its own directory as CWD). They skip when the apps are
absent, which is the normal case in CI — this is a local guard for whoever edits a glyph,
not a gate on the package.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from pbi_app_shell.ui.icons import HOUSE_GLYPHS, HOUSE_PALETTE

#: Where the sibling app checkouts live when this repo sits beside them.
_SIBLINGS = Path(__file__).resolve().parents[2]

APPS = {
    # pbi_app_template was retired in 2026-09 once its shared parts lived here; the three
    # live consumers are what parity is measured against.
    "spectrum_visualizer": _SIBLINGS / "spectrum_visualizer/dash_app/components/icons.py",
    "immunoxplore": _SIBLINGS / "immunoxplore/dash-app/components/icons.py",
    "data_transfer": _SIBLINGS / "infra/data_transfer/components/icons.py",
}

_GLYPH_ENTRY = re.compile(r'^    "([a-z_0-9]+)":\s*\("([a-z]+)",\s*(.*)\),\s*$', re.M)
_PALETTE_ENTRY = re.compile(r'"([a-z]+)": \("(#[0-9a-fA-F]{6})", "(#[0-9a-fA-F]{6})"\)')


def _source_of(app: str) -> str:
    path = APPS[app]
    if not path.exists():
        pytest.skip(f"{app} is not checked out beside this repo")
    return path.read_text(encoding="utf-8")


def _glyph_body(src: str) -> str:
    """The text of the app's ``_GLYPHS`` dict, or "" when it has none.

    Absent is the GOAL state, not a failure: once an app's ``icons.py`` is a binding of the
    package, an app with no domain glyphs defines no glyph dict at all. Sliced to the first
    line that is exactly ``}`` so it works both for the pre-package files (whose dict was
    followed by ``_NAMES = ...``) and for a shim (whose next statement is ``_icons = ...``).
    """
    marker = "_GLYPHS: dict[str, tuple[str, str]] = {"
    if marker not in src:
        return ""
    body = src[src.index(marker):]
    end = body.index("\n}") if "\n}" in body else len(body)
    return body[:end]


def _palette_body(src: str) -> str:
    """The text of the app's ``_PALETTE`` dict, or "" when it has none — a shim takes the
    house palette and defines nothing."""
    if "_PALETTE = {" not in src:
        return ""
    body = src[src.index("_PALETTE = {"):]
    return body[:body.index("\n}")] if "\n}" in body else body


def _app_glyphs(src: str) -> dict[str, tuple[str, str]]:
    """The app's ``_GLYPHS`` dict, parsed out of the source rather than imported.

    ``literal_eval`` on the captured SVG matters: the source carries the quotes, and
    comparing a quoted literal against an evaluated string reports every glyph as drifted.
    """
    return {m[0]: (m[1], ast.literal_eval(m[2]))
            for m in _GLYPH_ENTRY.findall(_glyph_body(src))}


def _app_palette(src: str) -> dict[str, tuple[str, str]]:
    return {m[0]: (m[1], m[2]) for m in _PALETTE_ENTRY.findall(_palette_body(src))}


@pytest.mark.parametrize("app", sorted(APPS))
def test_a_shared_glyph_is_still_drawn_the_same_way(app):
    theirs = _app_glyphs(_source_of(app))
    # An empty overlap is the goal state: the app's icons.py is a shim holding only its
    # own domain glyphs, so there is nothing left to disagree about.
    shared = sorted(set(theirs) & set(HOUSE_GLYPHS))
    drifted = sorted(n for n in shared if theirs[n] != HOUSE_GLYPHS[n])
    assert not drifted, (
        f"{app} draws {drifted} differently from the house set. Either the app has drifted "
        f"and should adopt the house drawing, or the house drawing changed and every app "
        f"needs to agree — this is not a test to silence.")


@pytest.mark.parametrize("app", sorted(APPS))
def test_a_shared_palette_colour_is_still_the_same_pair(app):
    theirs = _app_palette(_source_of(app))
    shared = sorted(set(theirs) & set(HOUSE_PALETTE))
    drifted = sorted(n for n in shared if theirs[n] != HOUSE_PALETTE[n])
    assert not drifted, f"{app}'s tile colours {drifted} differ from the house palette"


@pytest.mark.parametrize("app", sorted(APPS))
def test_the_parser_found_the_dict_whenever_the_app_has_one(app):
    """Guard against vacuous passes: a parser that silently returns nothing would make
    every check below green while measuring absolutely nothing."""
    body = _glyph_body(_source_of(app))
    entries = body.count('": (')          # counted a different way than the parser does
    assert len(_app_glyphs(_source_of(app))) == entries


@pytest.mark.parametrize("app", sorted(APPS))
def test_the_app_only_keeps_glyphs_the_house_set_does_not_have(app):
    """A glyph an app defines that the house set ALSO has is a duplicate, not a domain
    glyph. This is the check that keeps a shim honest after the package grows a name."""
    theirs = _app_glyphs(_source_of(app))
    duplicated = sorted(set(theirs) & set(HOUSE_GLYPHS))
    assert not duplicated, (
        f"{app} still defines house glyphs {duplicated}; its icons.py should pass only "
        f"its domain glyphs as IconSet(extra=...)")
