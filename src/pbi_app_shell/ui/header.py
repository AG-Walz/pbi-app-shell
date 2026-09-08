"""The header pieces every AG-Walz app puts in its 60 px bar.

Layout only, plus the three callback families that keep them alive. What is deliberately
NOT here is the header itself: the left-hand side carries the app's identity pills, so
assembling the bar stays each app's job. These are the parts that were identical wherever
two apps shared them — a resource chip, a host badge, a feedback menu, a divider — plus
``register_sysmon`` / ``register_theme`` / ``register_report_links`` to wire them.

The element ids are the contract between this module and the app's layout. They are the
ids the extracted apps already used, and every ``register_*`` function takes them as
arguments so an app with different ones is not locked out::

    header.register_sysmon()                      # sysmon-tick -> sysmon
    header.register_theme(boot_tick_id="ws-init")  # mp / theme / dark
    header.register_report_links(
        APP,
        inputs=[Input("user-store", "data"), Input("url", "pathname")],
        snapshot=lambda u, p: {"user": (u or {}).get("user") or "Guest", "page": p or "/"},
    )

Nothing here reads app config; identity arrives as an :class:`~pbi_app_shell.AppIdentity`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc

from pbi_app_shell.bug_report import build_issue_url, prefilled_url
from pbi_app_shell.identity import AppIdentity
from pbi_app_shell.ui.icons import HOUSE

try:  # optional; the header resource monitor degrades to "—" without it
    import psutil
except ImportError:  # pragma: no cover - depends on the venv, not on our code
    psutil = None

icon = HOUSE.icon

#: Feedback menu entries: (element-id kind, menu label, glyph, issue form).
FEEDBACK_KINDS: tuple[tuple[str, str, str], ...] = (
    ("bug", "Report a bug", "report", "bug_report.yml"),
    ("feature", "Request a feature", "feature", "feature_request.yml"),
)


# --- resource monitor --------------------------------------------------------

def resmon(cpu: float, ram_pct: float, ram_used_gb: float, ram_total_gb: float):
    """A compact CPU/RAM status chip; the full two-bar view (plus RAM in GB) on hover.

    Hover, not click: the chip is rebuilt every 5 s by the poll, which would reset a
    click-managed open state — a HoverCard keeps its own.
    """
    def _color(v: float) -> str:
        return "green" if v < 70 else ("yellow" if v < 90 else "red")

    def _bar(label: str, val: float):
        return dmc.Group(gap=4, wrap="nowrap", align="center", children=[
            dmc.Text(label, size="xs", c="dimmed", w=26),
            dmc.Progress(value=val, color=_color(val), size="sm", w=64, radius="sm"),
            dmc.Text(f"{val:.0f}%", size="xs", w=30, ta="right"),
        ])

    chip = dmc.Group(gap=6, wrap="nowrap", align="center", children=[
        icon("server", size=16),
        dmc.Box(w=8, h=8, bg=_color(max(cpu, ram_pct)),
                style={"borderRadius": "50%", "flexShrink": 0}),
        dmc.Text(f"CPU {cpu:.0f}% · RAM {ram_pct:.0f}%", size="xs", c="dimmed"),
    ])
    detail = dmc.Stack(gap=4, children=[
        _bar("CPU", cpu), _bar("RAM", ram_pct),
        dmc.Text(f"RAM {ram_used_gb:.1f} / {ram_total_gb:.1f} GB · system-wide",
                 size="xs", c="dimmed"),
    ])
    return dmc.HoverCard(withArrow=True, shadow="md", position="bottom-end", children=[
        dmc.HoverCardTarget(chip),
        dmc.HoverCardDropdown(detail),
    ])


def resmon_now():
    """Point-in-time system CPU/RAM, or a dash when psutil is unavailable.

    Deliberately SYSTEM-WIDE rather than per-process, so it reads identically from any
    gunicorn worker — a per-worker number would jump around as requests land on different
    workers and would tell the user nothing about whether the machine is busy.
    ``cpu_percent(interval=0.1)`` is stateless (no per-worker drift) at the cost of a 100 ms
    sample, which is negligible at the 5 s poll. Captured at call time: at the build-time
    call site it is a one-shot boot snapshot, then refreshed by the tick.
    """
    if psutil is None:
        return dmc.Text("—", size="xs", c="dimmed")
    try:
        vm = psutil.virtual_memory()
        # The GB figure uses (total - available) so it matches vm.percent's accounting,
        # which excludes reclaimable cache — bar and tooltip then never disagree.
        return resmon(psutil.cpu_percent(interval=0.1), vm.percent,
                      (vm.total - vm.available) / 1e9, vm.total / 1e9)
    except Exception:  # pragma: no cover - never let the monitor break the header
        return dmc.Text("—", size="xs", c="dimmed")


# --- badges and dividers -----------------------------------------------------

def host_badge(identity: AppIdentity):
    """Deployment marker for the header — only when the identity carries a host.

    Returns ``None`` otherwise; Dash skips a ``None`` child, so an unset host leaves the
    header unchanged. Neutral grey and square radius so it reads as a non-clickable label,
    distinct from the coloured identity pills.
    """
    if not identity.host:
        return None
    return dmc.Tooltip(
        label="Host",
        children=dmc.Badge(identity.host, color="gray", variant="light", size="sm",
                           radius="sm", leftSection=icon("instance", size=15)),
    )


def header_divider() -> dmc.Divider:
    """A vertical rule between header groups.

    ``alignSelf`` is load-bearing: Mantine gives a vertical Divider ``align-self: stretch``,
    which only stretches while the cross size is auto. The explicit height makes it
    definite, and stretch then behaves as flex-start — which pinned the divider to the top
    of the group, where the parent's ``align="center"`` could not override it.
    """
    return dmc.Divider(orientation="vertical",
                       style={"height": "1.6rem", "alignSelf": "center"})


def drawer_alert(text: str, color: str):
    """A severity-coloured message for a drawer (or nothing when empty)."""
    return (dmc.Alert(text, color=color, variant="light", radius="sm",
                      withCloseButton=False, p="xs") if text else None)


# --- feedback menu -----------------------------------------------------------

def feedback_row(identity: AppIdentity, kind: str, label: str, icon_name: str,
                 template: str) -> dmc.Group:
    """One feedback entry: a menu item opening a pre-filled GitHub issue in a new tab, plus
    a sibling copy button that copies that same pre-filled link.

    The copy button is placed *beside* the anchor, not nested inside it, so copying never
    also fires the tab navigation. Both are refreshed by ``register_report_links``; the
    href starts as the snapshot-free form rather than a bare ``issues/new``, so the window
    before that callback resolves still shows a real form instead of GitHub's template
    chooser. The copy fallback matters because the new tab can be blocked by the browser or
    simply go unnoticed, and a user who thinks nothing happened does not report the bug.
    """
    return dmc.Group(
        gap=4, wrap="nowrap", align="center",
        children=[
            dmc.MenuItem(label, id=f"report-{kind}-item",
                         leftSection=icon(icon_name, size=18),
                         href=prefilled_url(identity, template), target="_blank",
                         style={"flex": 1}),
            dcc.Clipboard(
                id=f"report-{kind}-copy", content="", title="Copy link",
                children=icon("copy", size=16), copied_children=icon("check", size=16),
                style={"cursor": "pointer", "marginInlineEnd": "8px"}),
        ],
    )


def report_menu(identity: AppIdentity) -> dmc.Menu:
    """Feedback menu (octopus icon): open a pre-filled bug report or feature request, or
    copy the pre-filled link. Both item hrefs and copy contents are rebuilt by
    ``register_report_links`` so each issue carries the app's current snapshot."""
    return dmc.Menu(
        id="report-menu", position="bottom-end", withArrow=True, shadow="md", width=260,
        children=[
            dmc.MenuTarget(
                dmc.ActionIcon(icon("github", size=24), id="report-icon",
                               variant="subtle", size="lg")
            ),
            dmc.MenuDropdown([
                dmc.MenuLabel("Feedback on GitHub"),
                *(feedback_row(identity, kind, label, glyph, template)
                  for kind, label, glyph, template in FEEDBACK_KINDS),
                dmc.MenuDivider(),
                dmc.MenuItem("View on GitHub", leftSection=icon("github", size=18),
                             href=f"https://github.com/{identity.repo}", target="_blank"),
                dmc.Text("No new tab? Use the copy icon to copy the link, then paste it "
                         "into your browser.", size="xs", c="dimmed", px="xs", pt="xs"),
                dmc.Text("Attach a screenshot (bug) or sketch (feature) in the issue.",
                         size="xs", c="dimmed", px="xs", pb="xs", pt=4),
            ]),
        ],
    )


# --- callback wiring ---------------------------------------------------------

def register_sysmon(*, box_id: str = "sysmon", tick_id: str = "sysmon-tick"):
    """Refresh the resource chip on every tick. The header already renders an initial
    reading at build time; this replaces it every ``dcc.Interval`` period."""
    @callback(Output(box_id, "children"), Input(tick_id, "n_intervals"),
              prevent_initial_call=True)
    def _update_sysmon(_n):
        return resmon_now()

    return _update_sysmon


def register_theme(*, boot_tick_id: str, provider_id: str = "mp",
                   store_id: str = "theme", toggle_id: str = "dark"):
    """Wire the header's light/dark toggle to the MantineProvider, and restore it on load.

    Two callbacks, and the second is the non-obvious one: ``forceColorScheme`` resets to
    "light" on every full page load, and the toggle only fires on a click, so without a
    restore off the app's boot tick dark mode is lost on a hard refresh.

    ``store_id`` keeps a plain boolean contract (True = dark) that pages can read.
    """
    @callback(Output(provider_id, "forceColorScheme"), Output(store_id, "data"),
              Output(toggle_id, "children"),
              Input(toggle_id, "n_clicks"), State(store_id, "data"),
              prevent_initial_call=True)
    def _toggle_scheme(_n, is_dark):
        # An ActionIcon, not a Switch -> derive the next scheme from the persisted bool.
        dark = not is_dark
        return ("dark" if dark else "light"), dark, (icon("light", size=24) if dark
                                                     else icon("dark", size=24))

    @callback(Output(provider_id, "forceColorScheme", allow_duplicate=True),
              Output(toggle_id, "children", allow_duplicate=True),
              Input(boot_tick_id, "n_intervals"), State(store_id, "data"),
              prevent_initial_call=True)
    def _restore_scheme(_n, is_dark):
        dark = bool(is_dark)
        return ("dark" if dark else "light"), (icon("light", size=24) if dark
                                               else icon("dark", size=24))

    return _toggle_scheme, _restore_scheme


def register_report_links(identity: AppIdentity, *, inputs: Sequence[Input],
                          snapshot: Callable[..., Mapping[str, Any]],
                          droppable: Iterable[str] = ()):
    """Keep the feedback links pointing at a pre-filled issue carrying the app's snapshot.

    ``inputs`` are the app's own state Inputs and ``snapshot`` turns their values into the
    report payload — the two things that are genuinely per-app here, since one app's
    "what was I doing" is a user and a workspace and another's is both ends of a transfer.
    Runs on load and whenever any input changes, and feeds each menu item's ``href`` and
    its copy button's ``content`` the same URL.

    ``droppable`` is passed straight through to
    :func:`~pbi_app_shell.bug_report.build_issue_url`: bulky optional fields, largest
    first, shed one at a time if the URL would overflow.

    Returns the registered callback, as every ``register_*`` here does — Dash only needs
    the decoration, but handing it back means a test can call it without reaching into
    Dash's global callback registry.
    """
    outputs = [Output(f"report-{kind}-item", "href") for kind, *_ in FEEDBACK_KINDS]
    outputs += [Output(f"report-{kind}-copy", "content") for kind, *_ in FEEDBACK_KINDS]

    @callback(*outputs, *inputs)
    def _build_report_links(*values):
        return report_urls(identity, snapshot(*values), droppable=droppable)

    return _build_report_links


def report_urls(identity: AppIdentity, snapshot: Mapping[str, Any],
                droppable: Iterable[str] = ()) -> tuple[str, ...]:
    """The feedback menu's outputs for one snapshot: each item's href, then each copy
    button's content, in :data:`FEEDBACK_KINDS` order.

    Split out of the callback so the URL-building can be tested without a Dash app. The
    item and its copy button deliberately get the SAME url — the copy exists because the
    new tab can be blocked, not to offer something different.
    """
    urls = tuple(build_issue_url(identity, template, snapshot, droppable=droppable)[0]
                 for *_, template in FEEDBACK_KINDS)
    return (*urls, *urls)
