"""The on-disk model: users, workspaces and per-user settings.

Pure Python — no Dash, no third-party imports at all — so it is testable without a
browser and importable by a CLI that has no UI. The Dash side lives in
:mod:`pbi_app_shell.ui`, which is gated behind the ``[dash]`` extra.
"""

from __future__ import annotations

from pbi_app_shell.storage.session import Settings
from pbi_app_shell.storage.workspace import Workspaces, sanitize_filename

__all__ = ["Settings", "Workspaces", "sanitize_filename"]
