"""The in-app documentation drawer — page-aware Markdown from the app's own docs folder.

The drawer body shows the Markdown doc for the *current* page and swaps as the route
changes. Docs live as one Markdown file per page in a directory the app owns, mapped by a
route -> file-stem dict; an unmapped route falls back to the home overview, so a new page
always shows something rather than an error.

House rule for writing them: describe what a control DOES rather than quoting its label —
"the button that starts the run", not "the Run button". Then renaming a label cannot make a
doc silently wrong.

The app supplies both the directory and the map, since both are its own::

    _docs = DocsDrawer(Path(__file__).parent.parent / "docs", {"/": "home", ...})
    _docs.register()
    ...
    dmc.Drawer(..., children=_docs.content())
"""

from __future__ import annotations

from pathlib import Path

import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc

#: Shown when a route has no doc and the fallback file is missing too.
EMPTY = "# Documentation\n\nNo documentation for this page yet."


class DocsDrawer:
    """Markdown docs for one app, resolved per route.

    ``fallback`` is the stem used for an unmapped route and for a mapped stem whose file
    has gone missing — a doc that was renamed should degrade to the overview, not to an
    exception inside a callback where nobody sees it.
    """

    def __init__(self, docs_dir: Path | str, path_doc: dict[str, str], *,
                 fallback: str = "home") -> None:
        self.docs_dir = Path(docs_dir)
        self.path_doc = path_doc
        self.fallback = fallback

    def load(self, pathname: str) -> str:
        """Markdown for a route — the page's own doc, else the fallback overview."""
        stem = self.path_doc.get(pathname or "/", self.fallback)
        f = self.docs_dir / f"{stem}.md"
        if not f.exists():
            f = self.docs_dir / f"{self.fallback}.md"
        return f.read_text(encoding="utf-8") if f.exists() else EMPTY

    @staticmethod
    def render(md: str):
        return dcc.Markdown(md, className="docs-md", link_target="_blank")

    def content(self, *, body_id: str = "docs-drawer-body"):
        """The drawer body — a container :meth:`register` fills per page."""
        return dmc.Box(id=body_id, children=self.render(self.load("/")))

    def register(self, *, body_id: str = "docs-drawer-body",
                 location_id: str = "url", drawer_id: str = "docs-drawer",
                 opener_id: str = "docs-icon") -> None:
        """Wire the route -> body swap, and the header button that opens the drawer."""
        @callback(Output(body_id, "children"), Input(location_id, "pathname"))
        def _swap_doc(pathname):
            return self.render(self.load(pathname))

        @callback(Output(drawer_id, "opened"), Input(opener_id, "n_clicks"),
                  prevent_initial_call=True)
        def _open_docs(_n):
            return True  # closing is handled by DMC (X / backdrop / Esc)
