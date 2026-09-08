# pbi-app-shell

Shared UI plumbing for AG-Walz's Dash apps — the on-disk user/workspace model, the house
icon set, the header pieces, the docs drawer, the shared stylesheet, and the pre-filled
GitHub issue reporting that `immunoxplore`, `spectrum_visualizer`, `pbi_app_template` and
`data_transfer` each carried their own copy of.

Public on purpose. There is no data, no secret and no IP in a generic Dash shell, and
being public removes the auth problem entirely — consumers install from a git tag with
no SSH key, no PAT, and no CI credential.

## Install

Pin a tag. Never `@main` — that rebuilds the copy-paste problem as silent drift.

```toml
# pyproject.toml, under the `dash` dependency group — immunoxplore
"pbi-app-shell[dash] @ git+https://github.com/AG-Walz/pbi-app-shell@v0.2.0"
```

```yaml
# environment.yml, under pip: — spectrum_visualizer
  - pip:
    - pbi-app-shell[dash] @ git+https://github.com/AG-Walz/pbi-app-shell@v0.2.0
```

```
# requirements.txt — data_transfer
pbi-app-shell[dash] @ git+https://github.com/AG-Walz/pbi-app-shell@v0.2.0
```

Drop the `[dash]` for a consumer that only wants the pure layer.

## Two layers

| | needs | holds |
|---|---|---|
| `pbi_app_shell` | nothing | `AppIdentity`, `bug_report`, `storage` |
| `pbi_app_shell.ui` | `[dash]` extra | `icons`, `header`, `docs`, `assets` |

`[project] dependencies` is empty and stays empty. A CLI or a batch job wants the issue-URL
builder and the on-disk model without Dash, and one convenience import at the top of a
module would break that silently — so a CI job installs the package with no extras and
imports it, and `tests/test_pure_layer.py` blocks `dash` in a subprocess to prove the
boundary holds. `psutil` is not required either: the header's resource chip degrades to
`—` without it.

## Use

The app says who it is; the package never imports the app.

```python
from pbi_app_shell import AppIdentity

APP = AppIdentity(name="MSpecViz", version="2.1.0", repo="AG-Walz/spectrum_visualizer")
```

`AppIdentity` also takes `host` (the machine the app runs on, when the user needs to know)
and `qualify_titles=True` (put the app name in the issue title — for a repo like
`AG-Walz/infra` that tracks several apps in one issue list).

### Feedback links

```python
from pbi_app_shell import build_issue_url, prefilled_url

# The menu item, before any snapshot exists — a real form, not GitHub's chooser.
href = prefilled_url(APP, "bug_report.yml")

# Once the app knows what it was doing. `droppable` is ordered largest-first: the
# fields the app is willing to lose, shed one at a time if the URL would overflow.
url, complete = build_issue_url(APP, "bug_report.yml",
                                {"page": page, "workspace": code, "result": result},
                                droppable=("result",))
```

### The on-disk model

`<output_root>/<user>/<workspace>/`, with every destructive operation re-validating the
path it resolved — codes arrive from a browser store and reach `shutil.rmtree`. Bind the
methods into the app's own `services/workspace.py` so its call sites keep importing plain
functions:

```python
from pbi_app_shell.storage import Settings, Workspaces
from config import DEFAULT_OUTPUT_DIR, DOWNLOAD_PREFIX, OUTPUT_DIR_ENV

_ws = Workspaces(output_dir_env=OUTPUT_DIR_ENV, default_dir=DEFAULT_OUTPUT_DIR,
                 download_prefix=DOWNLOAD_PREFIX)
GUEST = _ws.GUEST
output_root = _ws.output_root
workspace_dir = _ws.workspace_dir
# ... one binding per name the app already imports
```

`create_workspace(user, name="")` is where the three apps disagreed. An explicit `name` is
validated and used. A blank one defers to the optional `code_factory`, which receives the
codes already taken and returns a fresh one — that is how an app keeps memorable
`adjective_noun` codes without this package depending on a word list. With no factory it
falls back to `workspace_N`.

### Icons

`HOUSE_GLYPHS` holds the 32 drawings that were byte-identical wherever two or more apps
shared them. Domain glyphs stay with the app that needs them:

```python
from pbi_app_shell.ui.icons import IconSet

_GLYPHS: dict[str, tuple[str, str]] = {          # this app's own
    "volcano": ("red", '<path d="…" stroke="{fg}"/>'),
}
icon, gicon = (lambda s: (s.icon, s.gicon))(IconSet(extra=_GLYPHS))
```

Turbulence seeds come from a hash of the glyph NAME, not its position, so the dict is no
longer append-only. The apps this was extracted from seeded on `_NAMES.index(name)`, which
is why each of them documented an append-only rule — **adopting this module re-wobbles
every icon once.** That is cosmetic and deliberate; it is the price of a house set an app
can extend without disturbing.

### Header pieces

Layout only, plus the callbacks that keep them alive. The header itself stays app-side —
its left half carries the app's identity pills.

```python
from pbi_app_shell.ui import header

dmc.Box(header.resmon_now(), id="sysmon")   # the CPU/RAM chip
header.host_badge(APP)                      # None when the identity has no host
header.report_menu(APP)                     # the feedback menu
header.header_divider()

header.register_sysmon()
header.register_theme(boot_tick_id="ws-init")
header.register_report_links(
    APP,
    inputs=[Input("user-store", "data"), Input("ws-store", "data"),
            Input("url", "pathname")],
    snapshot=lambda u, w, p: {"user": (u or {}).get("user") or GUEST,
                              "workspace": (w or {}).get("code") or "—",
                              "page": p or "/"},
)
```

Every `register_*` takes its element ids as arguments and returns the callback it made, so
an app with different ids is not locked out and a test does not have to reach into Dash's
callback registry.

### The shared stylesheet

Dash serves exactly one `assets/` folder and it belongs to the app, so the house polish
ships inside the package and mounts on the app's Flask server:

```python
app = Dash(__name__, use_pages=True, external_stylesheets=[*dmc.styles.ALL, FONT_URL])
assets.mount(app)                 # after Dash(...), before app.layout
```

That works after construction because Dash reads `external_stylesheets` when it renders
the index page, not when it is built. External stylesheets are linked *before* `assets/`,
so any rule an app keeps in its own `assets/app.css` still wins.

### The forms have to be copied

`.github/ISSUE_TEMPLATE/` here is a **reference copy**, not something you inherit.
GitHub resolves `?template=` only against a repo's own default branch, so each
consuming repo needs its own copy on `main` before any of these links resolve.

Copy both files, and keep two things: the field id `context` (a rename on either side
drops the whole snapshot with no error anywhere), and the *absence* of `render:` on it.
`render` wraps submitted text in a code block; the snapshot arrives already fenced as
` ```json `, the two fences nest at the same backtick depth, and the report lands as raw
text with the backticks showing. That defect travelled between these apps by copied
template — which is what this package exists to stop.

## What is allowed in

Only code that is **semantically identical in at least two apps** — identical once
comments, docstrings and whitespace are stripped away. Everything else stays app-side until
someone reconciles it deliberately. That keeps this a place where settled decisions live,
rather than where several apps' disagreements get litigated — which is how shared UI
packages usually die.

The rule started as *byte*-identical, which turned out to measure documentation habits
rather than agreement. Re-measured semantically across `pbi_app_template`,
`spectrum_visualizer` and `immunoxplore`:

| module | identical in all three | identical in two | genuinely disagree |
|---|---|---|---|
| `services/session.py` | 4 of 4 functions | — | — |
| `services/workspace.py` | 17 of 28 | 7 | 1 (`create_workspace`) |
| `components/icons.py` | machinery + 32 glyphs | — | — (zero same-name-different-drawing) |
| `components/docs_drawer.py` | all but the route map | — | — |
| `components/shell.py` | 26 of 41 | 12 | 3 |

`tests/test_parity.py` re-measures the icon half against the apps themselves whenever they
are checked out beside this repo, because a claim about code that lives somewhere else rots
quietly.

Still out, and recorded so it is not lost: `build_shell` and the AppShell, the user and
workspace drawers, the delete modals, the settings drawer and the remaining shell callbacks
(next round, once this API has been under real use); `services/runs.py` and
`snapshots.py` (not shared by two apps yet); `settings_panel.py` (identical in two apps
only because one never replaced the example controls its own docstring tells it to
replace); and `data_transfer`'s drifted `_resmon` / `_report_menu` / `_host_badge`.

## Develop

```sh
uv run --group dev python -m pytest tests/ -v
uv run --group dev pylint src/ --errors-only
```

Four of the `bug_report` tests read the YAML rather than the Python, because that is where
the defect that motivated this package lived — every test of the URL builder passed
throughout.
