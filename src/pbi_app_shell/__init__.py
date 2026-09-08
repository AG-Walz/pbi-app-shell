"""Shared UI plumbing for AG-Walz's Dash apps.

What lives here is decided by measurement, not by intent: a module is eligible only
once it is *semantically* identical in at least two apps — identical after comments,
docstrings and whitespace are stripped away. Everything else stays app-side until
someone reconciles it deliberately. That keeps this a place where settled decisions
live, rather than a place where several apps' disagreements get litigated — which is
how shared UI packages usually die.

Two layers:

* the pure one — :mod:`pbi_app_shell.bug_report`, :mod:`pbi_app_shell.storage` — with
  no dependencies at all, importable from a CLI or a test that has never heard of Dash;
* :mod:`pbi_app_shell.ui`, behind the ``[dash]`` extra, for the icons, header pieces,
  docs drawer and shared stylesheet.

Nothing here imports from a consuming app. Identity is passed in; see
:class:`pbi_app_shell.identity.AppIdentity`.
"""

from __future__ import annotations

from pbi_app_shell.bug_report import (
    MAX_PREFILL_URL_BYTES, TITLE_KINDS, build_issue_title, build_issue_url,
    prefilled_url,
)
from pbi_app_shell.identity import AppIdentity
from pbi_app_shell.storage import Settings, Workspaces, sanitize_filename

__all__ = [
    "AppIdentity",
    "MAX_PREFILL_URL_BYTES",
    "Settings",
    "TITLE_KINDS",
    "Workspaces",
    "build_issue_title",
    "build_issue_url",
    "prefilled_url",
    "sanitize_filename",
]

__version__ = "0.2.0"
