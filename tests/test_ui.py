"""The Dash layer: the icon set, the header pieces, the docs drawer, the shared stylesheet.

These render real components and boot a real Dash app rather than asserting on source,
because the two things most likely to break here — a glyph name that does not exist, and a
stylesheet that is packaged but never linked — are both invisible to a source-level check.
"""

# pylint: disable=no-member
#   Dash components assign their props dynamically, so pylint cannot see ``Img.src`` or
#   ``Img.style``. The alternative is not asserting on the rendered SVG at all.

from __future__ import annotations

import dash_mantine_components as dmc
import pytest
from dash import Dash, Input, dcc, html

from pbi_app_shell import AppIdentity
from pbi_app_shell.ui import assets, header, icons

ONE_APP = AppIdentity(name="MSpecViz", version="2.1.0", repo="AG-Walz/spectrum_visualizer")
WITH_HOST = AppIdentity(name="Data Transfer", version="1.1.0", repo="AG-Walz/infra",
                        host="nacho", qualify_titles=True)


# --- icons ----------------------------------------------------------------------

def test_every_house_glyph_renders_tiled_and_tile_less():
    for name in icons.HOUSE_GLYPHS:
        for tile in (True, False):
            svg = icons.HOUSE.markup(name, 24, tile)
            assert svg.startswith("<svg") and svg.endswith("</svg>")
            assert "{fg}" not in svg          # the placeholder was substituted
            assert ("<rect" in svg) is tile or not tile


def test_every_house_glyph_names_a_colour_the_house_palette_has():
    unknown = {c for c, _ in icons.HOUSE_GLYPHS.values()} - set(icons.HOUSE_PALETTE)
    assert not unknown


def test_an_unknown_glyph_raises_rather_than_drawing_a_blank_tile():
    # A typo in an app's nav map has to fail at render. A silent empty tile is the failure
    # mode this replaces: it looks like a styling bug and gets triaged as one.
    with pytest.raises(KeyError):
        icons.HOUSE.icon("no-such-glyph")


def test_the_seed_depends_only_on_the_name_so_the_dict_is_not_append_only():
    before = icons.HOUSE.markup("home", 24, True)
    extended = icons.IconSet(extra={"aaa_first_alphabetically": ("blue", '<path d=""/>')})
    # The extra glyph sorts and inserts ahead of everything; under the old
    # _NAMES.index(name) seeding this changed every icon after it.
    assert extended.markup("home", 24, True) == before


def test_an_app_glyph_can_override_a_house_one_but_not_the_reverse():
    mine = icons.IconSet(extra={"home": ("red", '<path d="M1 1" stroke="{fg}"/>')})
    assert 'd="M1 1"' in mine.markup("home", 24, True)
    assert 'd="M1 1"' not in icons.HOUSE.markup("home", 24, True)


def test_an_app_may_add_a_palette_colour_without_editing_the_package():
    mine = icons.IconSet(extra={"x": ("brandnew", '<path d="M1 1" stroke="{fg}"/>')},
                         palette={"brandnew": ("#000000", "#ffffff")})
    assert "#ffffff" in mine.markup("x", 24, True)


def test_icon_returns_a_scaled_data_uri_image():
    img = icons.HOUSE.icon("home", 24)
    assert img.src.startswith("data:image/svg+xml;base64,")
    assert img.style["width"] == round(24 * icons.SCALE)


# --- header pieces --------------------------------------------------------------

def test_the_host_badge_appears_only_when_the_identity_has_a_host():
    assert header.host_badge(ONE_APP) is None      # Dash skips a None child
    assert header.host_badge(WITH_HOST) is not None


def test_the_resource_chip_survives_psutil_being_absent(monkeypatch):
    monkeypatch.setattr(header, "psutil", None)
    assert isinstance(header.resmon_now(), dmc.Text)


def test_the_resource_chip_never_breaks_the_header(monkeypatch):
    class Exploding:
        @staticmethod
        def virtual_memory():
            raise OSError("no /proc")

    monkeypatch.setattr(header, "psutil", Exploding)
    assert isinstance(header.resmon_now(), dmc.Text)


def test_the_feedback_items_start_on_a_real_form_not_githubs_chooser():
    menu = header.report_menu(ONE_APP)
    hrefs = _hrefs(menu)
    # A bare .../issues/new is the template CHOOSER. Every feedback href has to name a
    # template from the first paint, because the callback that adds the snapshot cannot
    # run until the app's state resolves.
    feedback = [h for h in hrefs if "issues/new" in h]
    assert feedback and all("template=" in h for h in feedback)
    assert any("bug_report.yml" in h for h in feedback)
    assert any("feature_request.yml" in h for h in feedback)


def test_the_menu_also_links_the_repo_itself():
    assert "https://github.com/AG-Walz/spectrum_visualizer" in _hrefs(
        header.report_menu(ONE_APP))


def test_a_copy_button_sits_beside_each_item_not_inside_it():
    # Nested, the copy click would also fire the anchor's navigation.
    row = header.feedback_row(ONE_APP, "bug", "Report a bug", "report", "bug_report.yml")
    kinds = [type(c).__name__ for c in row.children]
    assert kinds == ["MenuItem", "Clipboard"]


def _hrefs(component) -> list[str]:
    """Every href anywhere in a component tree."""
    out = []
    href = getattr(component, "href", None)
    if isinstance(href, str):
        out.append(href)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            out += _hrefs(c)
    elif children is not None:
        out += _hrefs(children)
    return out


# --- callback wiring ------------------------------------------------------------

def test_report_urls_gives_each_item_and_its_copy_button_the_same_link():
    urls = header.report_urls(ONE_APP, {"user": "Ada", "page": "/explore"})
    assert len(urls) == 4                          # two hrefs + two clipboard contents
    assert urls[0] == urls[2] and urls[1] == urls[3]
    assert "Ada" in urls[0] and "explore" in urls[0]
    assert "bug_report.yml" in urls[0] and "feature_request.yml" in urls[1]


def test_a_droppable_field_is_shed_before_the_identifying_ones():
    url = header.report_urls(ONE_APP, {"page": "/explore", "result": "x" * 20000},
                             droppable=("result",))[0]
    assert "explore" in url          # the pointer survived
    assert "xxxxxxxx" not in url     # the bulk did not


def test_register_report_links_wires_four_outputs_and_returns_its_callback():
    app = Dash(__name__, suppress_callback_exceptions=True)
    with app.server.app_context():
        fn = header.register_report_links(
            ONE_APP,
            inputs=[Input("user-store", "data"), Input("url", "pathname")],
            snapshot=lambda u, p: {"user": (u or {}).get("user") or "Guest",
                                   "page": p or "/"},
        )
    urls = fn({"user": "Ada"}, "/explore")
    assert len(urls) == 4 and "Ada" in urls[0]


def test_register_theme_returns_both_halves_and_they_agree_on_the_glyph():
    # Two callbacks, because forceColorScheme resets to "light" on a full page load and
    # the toggle only fires on a click — without the restore, dark mode dies on refresh.
    app = Dash(__name__, suppress_callback_exceptions=True)
    with app.server.app_context():
        toggle, restore = header.register_theme(boot_tick_id="ws-init")
    scheme, is_dark, glyph = toggle(1, False)
    assert (scheme, is_dark) == ("dark", True)
    restored_scheme, restored_glyph = restore(1, True)
    # Compare the rendered SVG, not the components: two Img objects with identical src
    # are still distinct objects.
    assert (restored_scheme, restored_glyph.src) == ("dark", glyph.src)


def test_register_sysmon_returns_a_callback_that_renders_a_reading():
    app = Dash(__name__, suppress_callback_exceptions=True)
    with app.server.app_context():
        fn = header.register_sysmon()
    assert fn(1) is not None


# --- docs drawer ----------------------------------------------------------------

def test_a_mapped_route_gets_its_own_doc(tmp_path):
    from pbi_app_shell.ui.docs import DocsDrawer
    (tmp_path / "home.md").write_text("# Home", encoding="utf-8")
    (tmp_path / "explore.md").write_text("# Explore", encoding="utf-8")
    d = DocsDrawer(tmp_path, {"/": "home", "/explore": "explore"})
    assert d.load("/explore") == "# Explore"


def test_an_unmapped_route_falls_back_to_the_overview(tmp_path):
    from pbi_app_shell.ui.docs import DocsDrawer
    (tmp_path / "home.md").write_text("# Home", encoding="utf-8")
    d = DocsDrawer(tmp_path, {"/": "home"})
    assert d.load("/brand-new-page") == "# Home"


def test_a_mapped_stem_whose_file_vanished_also_falls_back(tmp_path):
    from pbi_app_shell.ui.docs import DocsDrawer
    (tmp_path / "home.md").write_text("# Home", encoding="utf-8")
    d = DocsDrawer(tmp_path, {"/gone": "gone"})
    assert d.load("/gone") == "# Home"


def test_no_docs_at_all_is_a_message_not_an_exception(tmp_path):
    from pbi_app_shell.ui.docs import DocsDrawer, EMPTY
    assert DocsDrawer(tmp_path, {}).load("/") == EMPTY


# --- the shared stylesheet ------------------------------------------------------

def _mounted_app():
    app = Dash(__name__, suppress_callback_exceptions=True)
    href = assets.mount(app)
    app.layout = html.Div([dcc.Location(id="url")])
    return app, href


def test_mounting_links_the_stylesheet_into_the_served_index():
    # The load-bearing claim: Dash reads external_stylesheets when it renders the index,
    # not when it is constructed, so mounting after Dash(...) still reaches the browser.
    app, href = _mounted_app()
    page = app.server.test_client().get("/").get_data(as_text=True)
    assert href in page


def test_the_stylesheet_is_actually_served_as_css():
    app, href = _mounted_app()
    resp = app.server.test_client().get(href)
    assert resp.status_code == 200
    assert "text/css" in resp.headers["Content-Type"]
    assert ".mantine-Card-root" in resp.get_data(as_text=True)
    assert "immutable" in resp.headers["Cache-Control"]


def test_the_url_carries_the_package_version_so_an_upgrade_busts_the_cache():
    from pbi_app_shell import __version__
    assert __version__ in assets.CSS_RELATIVE_URL


def test_mounting_twice_is_a_no_op_not_a_flask_endpoint_clash():
    app, href = _mounted_app()
    assert assets.mount(app) == href
    assert app.config.external_stylesheets.count(href) == 1


def test_the_stylesheet_names_no_brand_colour():
    # A shared stylesheet that hardcoded a brand would fight every theme it is loaded
    # into. The one literal allowed is the neutral resting tint.
    import re
    literals = set(re.findall(r"#[0-9a-fA-F]{3,8}", assets.stylesheet()))
    assert literals <= {"#f7f9fd"}
