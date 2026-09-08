"""The hand-drawn house icon set — the tiles and glyphs shared across AG-Walz's apps.

Each icon is a small SVG: a tinted rounded tile plus a drawn glyph, softened with a subtle
``feTurbulence`` displacement so it reads organic rather than clip-art. Rendered as a
data-URI ``html.Img``, so the set needs no extra dependency, no static files and no build
step, and displays identically everywhere.

:data:`HOUSE_GLYPHS` holds the 32 drawings that were byte-identical wherever two or more
apps shared them — navigation, header actions, header badges and the functional inline
glyphs. Domain glyphs stay with the app that needs them and are passed in::

    from pbi_app_shell.ui.icons import IconSet

    _APP_GLYPHS = {"volcano": ("red", '<path d="..." stroke="{fg}"/>')}
    _icons = IconSet(extra=_APP_GLYPHS)
    icon, gicon = _icons.icon, _icons.gicon

An app glyph may reuse a house name to override the drawing, which is the escape hatch for
a house glyph that turns out wrong for one app; the reverse — a house glyph quietly
changing an app's drawing — cannot happen, because ``extra`` wins.

Turbulence seeds come from a hash of the glyph NAME, not its position, so this dict is not
append-only and a glyph always wobbles the same way no matter what else is defined. (The
apps this was extracted from seeded on ``_NAMES.index(name)``, which is why their icon
dicts carried an append-only rule; adopting this module re-wobbles every icon once.)
"""

from __future__ import annotations

import base64
import hashlib

from dash import html

#: Tile colour name -> (tile background, glyph foreground). Tinted tiles read on both
#: the light and the dark header, so there is no per-theme variant — except the theme
#: toggle itself, which swaps moon/sun by intent.
HOUSE_PALETTE = {
    "blue": ("#edf2ff", "#4c6ef5"), "grape": ("#f8f0fc", "#9c36b5"),
    "teal": ("#e6fcf5", "#0ca678"), "orange": ("#fff4e6", "#f76707"),
    "cyan": ("#e3fafc", "#1098ad"), "pink": ("#fff0f6", "#e64980"),
    "indigo": ("#edf2ff", "#4263eb"), "lime": ("#f4fce3", "#5c940d"),
    "violet": ("#f3f0ff", "#7048e8"), "red": ("#fff5f5", "#e03131"),
    "green": ("#ebfbee", "#2f9e44"), "yellow": ("#fff9db", "#e8940c"),
    "gray": ("#f1f3f5", "#495057"), "gold": ("#f6f1e5", "#9c8544"),
    "lavender": ("#f0edfb", "#8577c9"),  # matches the user pill (#aaa3db)
}

#: Glyph name -> (palette colour, inner SVG with a ``{fg}`` placeholder).
HOUSE_GLYPHS: dict[str, tuple[str, str]] = {
    # --- navigation ---
    "home": ("blue", '<path d="M18 32 L32 18 L46 32" stroke="{fg}" stroke-width="3.6"/><path d="M22 30 V45 H42 V30" stroke="{fg}" stroke-width="3.6"/><rect x="29" y="37" width="6.5" height="8.5" rx="1.5" fill="{fg}"/>'),
    "load_data": ("blue", '<ellipse cx="32" cy="21" rx="12" ry="5" stroke="{fg}" stroke-width="3"/><path d="M20 21 V39 C20 42 26 44 32 44 C38 44 44 42 44 39 V21" stroke="{fg}" stroke-width="3"/><path d="M20 30 C20 33 26 35 32 35 C38 35 44 33 44 30" stroke="{fg}" stroke-width="2.4" opacity="0.6"/>'),
    "analyse": ("grape", '<path d="M18 45 H46" stroke="{fg}" stroke-width="2.8"/><rect x="21" y="30" width="6" height="14" rx="2" fill="{fg}"/><rect x="29" y="23" width="6" height="21" rx="2" fill="{fg}"/><rect x="37" y="35" width="6" height="9" rx="2" fill="{fg}"/>'),
    "export": ("teal", '<path d="M32 17 V38 M24 31 L32 39 L40 31" stroke="{fg}" stroke-width="3.4"/><path d="M20 44 H44" stroke="{fg}" stroke-width="3"/>'),
    "table": ("cyan", '<rect x="17" y="19" width="30" height="26" rx="4" stroke="{fg}" stroke-width="3.2"/><path d="M17 28 H47 M27 28 V45 M37 28 V45" stroke="{fg}" stroke-width="2.6"/>'),
    "snapshots": ("lime", '<path d="M23 17 H41 V47 L32 40 L23 47 Z" stroke="{fg}" stroke-width="3.4"/>'),
    "batch": ("teal", '<circle cx="32" cy="32" r="16" stroke="{fg}" stroke-width="3.4"/><path d="M28 24 L42 32 L28 40 Z" stroke="{fg}" stroke-width="3.2"/>'),
    # --- header actions ---
    "docs": ("gray", '<path d="M32 22 C 28 19, 22 19, 18 21 V42 C 22 40, 28 40, 32 43 C 36 40, 42 40, 46 42 V21 C 42 19, 36 19, 32 22 Z" stroke="{fg}" stroke-width="3"/><path d="M32 22 V43" stroke="{fg}" stroke-width="2.4"/>'),
    "settings": ("gray", '<g stroke="{fg}" stroke-width="3"><path d="M19 24 H45"/><path d="M19 32 H45"/><path d="M19 40 H45"/></g><circle cx="29" cy="24" r="3.4" fill="{fg}"/><circle cx="38" cy="32" r="3.4" fill="{fg}"/><circle cx="26" cy="40" r="3.4" fill="{fg}"/>'),
    "report": ("gray", '<ellipse cx="32" cy="34" rx="8" ry="10" stroke="{fg}" stroke-width="3"/><g stroke="{fg}" stroke-width="2.6"><path d="M24 30 H17"/><path d="M40 30 H47"/><path d="M24 38 H17"/><path d="M40 38 H47"/><path d="M28 23 L25 17"/><path d="M36 23 L39 17"/></g>'),
    "feature": ("yellow", '<path d="M24 30 a8 8 0 1 1 16 0 c0 3.6 -3 5 -3 8 H27 c0 -3 -3 -4.4 -3 -8 Z" stroke="{fg}" stroke-width="3.2"/><path d="M28 42 H36 M29.5 46 H34.5" stroke="{fg}" stroke-width="2.8"/><g stroke="{fg}" stroke-width="2.4" opacity="0.7"><path d="M32 11 V15"/><path d="M18 21 L21 23"/><path d="M46 21 L43 23"/></g>'),
    "github": ("gray", '<g transform="translate(8,8) scale(2)"><path d="M12 .3C5.4.3 0 5.7 0 12.3c0 5.3 3.4 9.8 8.2 11.4.6.1.8-.3.8-.6v-2C5.7 21.8 5 19.9 5 19.9c-.4-1-1-1.3-1-1.3-.9-.6.1-.6.1-.6 1 0 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.7.4-1.1.7-1.4-2.2-.2-4.5-1.1-4.5-4.9 0-1.1.4-2 1-2.6-.1-.3-.5-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .6 1.4.2 2.4.1 2.7.6.6 1 1.5 1 2.6 0 3.8-2.3 4.6-4.5 4.9.4.3.7.9.7 1.8v2.6c0 .3.2.7.8.6A12 12 0 0 0 24 12.3C24 5.7 18.6.3 12 .3z" fill="{fg}"/></g>'),
    "dark": ("indigo", '<path d="M43 35 A13 13 0 1 1 27 19 A10 10 0 0 0 43 35 Z" fill="{fg}"/><circle cx="41" cy="22" r="1.6" fill="{fg}"/><circle cx="35" cy="17" r="1.2" fill="{fg}"/>'),
    "light": ("orange", '<circle cx="32" cy="32" r="8" stroke="{fg}" stroke-width="3.2"/><g stroke="{fg}" stroke-width="3"><path d="M32 15 V20"/><path d="M32 44 V49"/><path d="M15 32 H20"/><path d="M44 32 H49"/><path d="M20 20 L23.5 23.5"/><path d="M40.5 40.5 L44 44"/><path d="M44 20 L40.5 23.5"/><path d="M23.5 40.5 L20 44"/></g>'),
    # --- header badges ---
    "user": ("lavender", '<circle cx="32" cy="25" r="7.5" stroke="{fg}" stroke-width="3.2"/><path d="M19 46 C 19 36, 45 36, 45 46" stroke="{fg}" stroke-width="3.2"/>'),
    "server": ("gray", '<rect x="22" y="22" width="20" height="20" rx="4" stroke="{fg}" stroke-width="3.2"/><rect x="28" y="28" width="8" height="8" rx="2" fill="{fg}"/><g stroke="{fg}" stroke-width="2.6"><path d="M22 28 H16"/><path d="M22 36 H16"/><path d="M42 28 H48"/><path d="M42 36 H48"/><path d="M28 22 V16"/><path d="M36 22 V16"/><path d="M28 42 V48"/><path d="M36 42 V48"/></g>'),
    "workspace": ("gold", '<path d="M18 24 H28 L31 28 H46 V44 H18 Z" stroke="{fg}" stroke-width="3.2"/>'),
    "instance": ("gray", '<path d="M25 43 C18 43 15 37 19 33 C17 25 27 22 31 28 C34 22 44 24 43 32 C48 33 47 43 40 43 Z" stroke="{fg}" stroke-width="3.2"/>'),
    # --- functional glyphs (rendered tile-less via ``gicon`` for inline buttons) ---
    "add": ("gray", '<path d="M32 20 V44 M20 32 H44" stroke="{fg}" stroke-width="4"/>'),
    "close": ("gray", '<path d="M22 22 L42 42 M42 22 L22 42" stroke="{fg}" stroke-width="4"/>'),
    "download": ("gray", '<path d="M32 18 V38 M23 30 L32 39 L41 30" stroke="{fg}" stroke-width="4"/><path d="M20 44 H44" stroke="{fg}" stroke-width="4"/>'),
    "star": ("gray", '<path d="M32 17 L37 28 L49 29 L40 37 L43 49 L32 43 L21 49 L24 37 L15 29 L27 28 Z" stroke="{fg}" stroke-width="3.4"/>'),
    "search": ("gray", '<circle cx="29" cy="29" r="10" stroke="{fg}" stroke-width="4"/><path d="M37 37 L46 46" stroke="{fg}" stroke-width="4"/>'),
    "file": ("gray", '<path d="M24 16 H36 L42 22 V48 H24 Z" stroke="{fg}" stroke-width="3.4"/><path d="M36 16 V22 H42" stroke="{fg}" stroke-width="3"/><path d="M28 30 H38 M28 36 H38 M28 42 H34" stroke="{fg}" stroke-width="2.6" opacity="0.8"/>'),
    "folder": ("gray", '<path d="M16 24 H28 L31 28 H48 V46 H16 Z" stroke="{fg}" stroke-width="3.4"/>'),
    "trash": ("gray", '<path d="M22 24 H42 M26 24 V45 a2 2 0 0 0 2 2 H36 a2 2 0 0 0 2 -2 V24 M28 24 V20 a2 2 0 0 1 2 -2 H34 a2 2 0 0 1 2 2 V24" stroke="{fg}" stroke-width="3.2"/><path d="M30 30 V41 M34 30 V41" stroke="{fg}" stroke-width="2.6" opacity="0.7"/>'),
    "save": ("gray", '<path d="M20 20 H40 L44 24 V44 H20 Z" stroke="{fg}" stroke-width="3.2"/><path d="M26 20 V28 H38 V20 M26 44 V36 H38 V44" stroke="{fg}" stroke-width="2.8"/>'),
    "edit": ("gray", '<path d="M40 18 L46 24 L28 42 L20 44 L22 36 Z" stroke="{fg}" stroke-width="3.2"/><path d="M36 22 L42 28" stroke="{fg}" stroke-width="2.6"/>'),
    "warning": ("orange", '<path d="M32 18 L48 44 H16 Z" stroke="{fg}" stroke-width="3.4"/><path d="M32 28 V36" stroke="{fg}" stroke-width="3.4"/><circle cx="32" cy="40" r="1.9" fill="{fg}"/>'),
    "copy": ("gray", '<rect x="18" y="15" width="23" height="28" rx="4" stroke="{fg}" stroke-width="3" opacity="0.5"/><rect x="24" y="21" width="23" height="28" rx="4" stroke="{fg}" stroke-width="3"/>'),
    "check": ("green", '<path d="M19 33 L28 42 L45 22" stroke="{fg}" stroke-width="4.5"/>'),
    # A drawing pin seen head-on: round head, collar, needle down to the point.
    "pin": ("orange", '<circle cx="32" cy="23" r="8.5" stroke="{fg}" stroke-width="3.4"/><path d="M21 35 H43" stroke="{fg}" stroke-width="3.4"/><path d="M32 35 V48" stroke="{fg}" stroke-width="3.4"/>'),
}

#: Global icon size multiplier — tune here to grow or shrink every icon at once.
SCALE = 1.25


def _seed(name: str) -> int:
    """A stable per-name turbulence seed.

    Derived from the name so that adding, removing or reordering glyphs — in this module or
    in an app's ``extra`` — cannot change how any other glyph is drawn. Truncated only to
    keep the generated ``filter`` id short.
    """
    return int(hashlib.md5(name.encode("utf-8")).hexdigest()[:4], 16)


class IconSet:
    """The house glyphs plus whatever domain glyphs an app adds.

    ``extra`` is merged over :data:`HOUSE_GLYPHS`, so an app can add names and, if it must,
    override one. ``palette`` does the same for the tile colours: an app naming a colour
    the house palette does not have supplies it here rather than editing this module.
    """

    def __init__(self, *, extra: dict[str, tuple[str, str]] | None = None,
                 palette: dict[str, tuple[str, str]] | None = None) -> None:
        self.glyphs = {**HOUSE_GLYPHS, **(extra or {})}
        self.palette = {**HOUSE_PALETTE, **(palette or {})}

    def markup(self, name: str, size: int, tile: bool,
               fg_override: str | None = None) -> str:
        """The raw SVG for one glyph. Raises ``KeyError`` on an unknown name, which is what
        makes a typo in a nav map fail loudly at render rather than draw a blank tile."""
        color, inner = self.glyphs[name]
        bg, fg = self.palette[color]
        fg = fg_override or fg
        seed = _seed(name)
        filt = (f'<filter id="f{seed}" x="-20%" y="-20%" width="140%" height="140%">'
                f'<feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="2" '
                f'seed="{seed}" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" '
                f'scale="2.4"/></filter>')
        rect = (f'<rect x="4" y="4" width="56" height="56" rx="16" fill="{bg}"/>'
                if tile else "")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
                f'width="{size}" height="{size}" fill="none" stroke-linecap="round" '
                f'stroke-linejoin="round">'
                f'<defs>{filt}</defs>{rect}<g filter="url(#f{seed})">'
                f'{inner.format(fg=fg)}</g></svg>')

    def icon(self, name: str, size: int = 24, *, tile: bool = True,
             color: str | None = None, style: dict | None = None):
        """A drawn app icon as a data-URI ``html.Img``.

        ``tile`` draws the tinted tile; ``color`` overrides the glyph colour (used for
        tile-less functional glyphs). Every call is scaled by :data:`SCALE`, so the whole
        set resizes in one place.
        """
        size = round(size * SCALE)
        svg = self.markup(name, size, tile, color)
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        st = {"width": size, "height": size, "display": "block", "flexShrink": 0}
        if style:
            st.update(style)
        return html.Img(src=f"data:image/svg+xml;base64,{b64}", style=st)

    def gicon(self, name: str, size: int = 16, color: str = "#868e96"):
        """A small tile-less functional glyph for inline buttons / menu items. Mid-grey by
        default reads on both light and dark surfaces; pass ``color`` for semantic tints."""
        return self.icon(name, size, tile=False, color=color)


#: The house set with no app glyphs — what :mod:`pbi_app_shell.ui.header` draws with.
HOUSE = IconSet()
