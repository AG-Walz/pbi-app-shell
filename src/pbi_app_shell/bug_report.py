"""Pre-filled GitHub issue URLs carrying a snapshot of what the app was doing.

The feedback menu points at these: a bug report or feature request that arrives
answerable instead of as "it broke".

This module is the *mechanism* and nothing else. What goes IN the snapshot is the
app's business and stays app-side — immunoxplore sends the user, the workspace code
and the page; data_transfer sends both endpoints, both folders and the last result.
Only the URL building is invariant, which is why it is here: the three copies this
was extracted from were byte-identical apart from one line (where ``REPO`` came from).

No Dash imports, and no imports from any consuming app — kept pure so it stays
trivially unit-testable and genuinely reusable.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Iterable, Mapping

from pbi_app_shell.identity import AppIdentity

#: Conservative ceiling on the pre-filled issue URL. GitHub's edge rejects URLs past
#: ~8 KB with HTTP 414, so stay well under to leave room for encoding.
MAX_PREFILL_URL_BYTES = 7000

#: Title prefix per form, the house style across AG-Walz's apps.
TITLE_KINDS = {"bug_report.yml": "[Bug]", "feature_request.yml": "[Enhancement]"}


def build_issue_title(identity: AppIdentity, template: str) -> str:
    """The pre-filled issue title: the house prefix, and the app name when asked for.

    The form's YAML carries the same prefix as its default, so opening the form
    directly on GitHub gives the same result as opening it from the app.
    """
    kind = TITLE_KINDS.get(template, "[Bug]")
    return f"{kind}[{identity.name}]: " if identity.qualify_titles else f"{kind}: "


def build_issue_url(identity: AppIdentity, template: str,
                    snapshot: Mapping[str, Any],
                    droppable: Iterable[str] = ()) -> tuple[str, bool]:
    """A URL opening ``template`` with ``snapshot`` inlined. Returns ``(url, complete)``.

    The snapshot goes into the form's ``context`` textarea fenced as a ```json block.
    That field must NOT set ``render:`` in the YAML — ``render`` wraps the submitted
    text in a code block of its own, and the two fences nest at the same backtick
    depth, so GitHub closes the outer block at the inner one and the rest of the report
    spills out as raw text.

    ``droppable`` names the bulky optional fields, **largest first**, to shed one at a
    time if the URL would pass GitHub's limit. Order is the app's call: it is a
    statement about what the app is willing to lose, and the fields that identify the
    report must be the last thing to go. ``complete`` is False when anything was shed.
    """
    base = f"https://github.com/{identity.repo}/issues/new"
    remaining = dict(snapshot)
    title = build_issue_title(identity, template)

    # Try the full snapshot first, then shed the heaviest fields until it fits.
    for dropped, field in enumerate((None, *droppable)):
        if field is not None:
            remaining.pop(field, None)
        query: dict[str, str] = {"template": template, "title": title}
        if remaining:
            query["context"] = (
                f"```json\n{json.dumps(remaining, indent=2, default=str)}\n```")
        url = f"{base}?{urllib.parse.urlencode(query)}"
        if len(url.encode("utf-8")) <= MAX_PREFILL_URL_BYTES:
            return url, dropped == 0

    # Even the bare snapshot overflowed: fall back to the empty form, still titled.
    bare = {"template": template, "title": title}
    return f"{base}?{urllib.parse.urlencode(bare)}", False


def prefilled_url(identity: AppIdentity, template: str) -> str:
    """The form to point a menu item at BEFORE there is a snapshot to add.

    Not belt-and-braces. The callback that supplies a snapshot cannot run until the
    app's state has resolved, and where that means ssh round trips it can take tens of
    seconds — measured at ~25 s in data_transfer, because an endpoint that is down
    burns its full connect timeout first. A bare ``issues/new`` for that window is
    GitHub's template CHOOSER, not a form, which is precisely how a feature that works
    can look like one that was never built.
    """
    url, _ = build_issue_url(identity, template, {})
    return url
