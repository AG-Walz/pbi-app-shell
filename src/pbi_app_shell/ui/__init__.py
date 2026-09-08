"""The Dash side of the shell: icons, header pieces, the docs drawer, the shared CSS.

Everything in here needs ``dash`` and ``dash-mantine-components``, which the package does
not require — the pure layer (``bug_report``, ``storage``) has to stay installable in a
CLI or a test environment that has never heard of Dash. Install the extra::

    pip install "pbi-app-shell[dash] @ git+https://github.com/AG-Walz/pbi-app-shell@v0.2.0"

Importing this subpackage without it fails here, with that instruction, rather than as a
bare ``ModuleNotFoundError: dash`` from three imports deep.
"""

from __future__ import annotations

try:
    import dash as _dash  # noqa: F401
    import dash_mantine_components as _dmc  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the venv, not on our code
    raise ImportError(
        "pbi_app_shell.ui needs dash and dash-mantine-components. Install the extra: "
        'pip install "pbi-app-shell[dash]"'
    ) from exc

from pbi_app_shell.ui import assets, docs, header, icons
from pbi_app_shell.ui.docs import DocsDrawer
from pbi_app_shell.ui.icons import HOUSE, HOUSE_GLYPHS, HOUSE_PALETTE, IconSet

__all__ = [
    "DocsDrawer",
    "HOUSE",
    "HOUSE_GLYPHS",
    "HOUSE_PALETTE",
    "IconSet",
    "assets",
    "docs",
    "header",
    "icons",
]
