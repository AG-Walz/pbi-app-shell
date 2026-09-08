"""Serving the shared stylesheet without stealing the app's ``assets/`` folder.

Dash links everything it finds in ``assets/`` automatically, but it serves exactly one such
folder and that one belongs to the app. So the house polish ships inside this package and
is mounted on the app's own Flask server instead::

    app = Dash(__name__, use_pages=True, external_stylesheets=[*dmc.styles.ALL, FONT_URL])
    assets.mount(app)          # after Dash(...), before app.layout
    app.layout = build_shell()

Mounting works after construction because Dash reads ``config.external_stylesheets`` when
it renders the index page, not when it is built — ``tests/test_assets.py`` asserts the link
actually reaches the served HTML rather than trusting that.

The package version is in the URL, so a consumer that upgrades gets the new stylesheet
instead of a cached old one, and the response can be marked immutable.
"""

from __future__ import annotations

from pathlib import Path

from flask import Response

from pbi_app_shell import __version__

#: The packaged stylesheet. It lives in ``static/`` rather than ``assets/``
#: because ``assets`` is this module's own name — a sibling directory of that
#: name is a namespace package Python would have to disambiguate on every import.
CSS_PATH = Path(__file__).resolve().parent / "static" / "shell.css"

#: URL path (relative to the app's root) the stylesheet is served at. Versioned, so an
#: upgrade cannot be masked by a cached response.
CSS_RELATIVE_URL = f"_pbi-app-shell/{__version__}/shell.css"

_ENDPOINT = "pbi_app_shell_stylesheet"


def stylesheet() -> str:
    """The stylesheet's text. Read per request; it is a few KB and this keeps a dev-mode
    edit of the installed package visible on reload."""
    return CSS_PATH.read_text(encoding="utf-8")


def mount(app) -> str:
    """Serve the shared stylesheet from *app* and link it. Returns the href.

    Idempotent: mounting twice (two Dash apps in one process, or a re-imported module) is a
    no-op rather than a Flask "endpoint already registered" error.

    The Flask rule uses ``routes_pathname_prefix`` (what the server sees) while the link
    uses ``requests_pathname_prefix`` (what the browser asks for). Those differ whenever
    the app sits behind a proxy that strips a prefix, and using one for both is the bug
    that only shows up in production.
    """
    href = app.config.requests_pathname_prefix + CSS_RELATIVE_URL
    if _ENDPOINT not in app.server.view_functions:
        route = app.config.routes_pathname_prefix + CSS_RELATIVE_URL

        def _serve_stylesheet():
            return Response(stylesheet(), mimetype="text/css",
                            headers={"Cache-Control": "public, max-age=31536000, "
                                                      "immutable"})

        app.server.add_url_rule(route, endpoint=_ENDPOINT,
                                view_func=_serve_stylesheet)
    if href not in app.config.external_stylesheets:
        # In-place append, not an assignment: Dash's config is an AttributeDict and this
        # has to survive being called after construction.
        app.config.external_stylesheets.append(href)
    return href
