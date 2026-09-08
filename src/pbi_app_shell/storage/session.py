"""Per-user UI settings on disk.

The live settings ride in a browser ``dcc.Store`` (localStorage); these helpers persist
them PER USER under ``output_root()/<user>/settings.json`` so a user's preferences follow
them across browsers. The app's shell bridges the two: hydrate the store from disk when
the active user changes, persist the store to disk on every change.

Settings live one level up from a workspace — they belong to the user, not to a workspace —
so they resolve from the active USER and never via ``workspace_dir`` (which would nest them
one level too deep, silently giving each workspace its own copy).
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pbi_app_shell.storage.workspace import Workspaces


class Settings:
    """Per-user settings files under a :class:`Workspaces` root.

    Takes the ``Workspaces`` instance rather than a path because the root is resolved on
    every call (it honours an environment override that a deployment may set after import).
    """

    #: Settings filename inside the user dir, and the sibling lock beside it.
    FILE_NAME = "settings.json"
    LOCK_NAME = ".settings.lock"

    def __init__(self, workspaces: Workspaces) -> None:
        self.workspaces = workspaces

    def _settings_path(self, user: str) -> Path:
        return self.workspaces.output_root() / user / self.FILE_NAME

    def load_settings(self, user: str) -> dict[str, Any]:
        """The user's saved settings dict (empty when none/unreadable)."""
        if not user:
            return {}
        p = self._settings_path(user)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save_settings(self, user: str, data: dict[str, Any]) -> None:
        """Persist the whole settings dict for *user* (no-op without a user).

        Atomic write — temp file in the same dir, fsync'd, then ``os.replace`` — so a reader
        never sees a torn / half-written file and the bytes survive a crash. This is a
        single WRITE; it does NOT serialize a read-modify-write against a concurrent
        writer. Use :meth:`update_settings` for that.
        """
        if not user:
            return
        p = self._settings_path(user)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".settings-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            # mkstemp is 0600; restore the usual rw-r--r-- (don't drop read).
            os.chmod(tmp, 0o644)
            os.replace(tmp, p)  # atomic on POSIX
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def update_settings(self, user: str, mutate) -> None:
        """Read-modify-write the user's settings under an exclusive per-user lock.

        ``mutate`` receives the loaded dict and edits it in place. An ``fcntl.flock`` on a
        sibling ``.settings.lock`` spans the whole load+mutate+save, so two concurrent
        writers (possibly on different gunicorn workers) cannot lose each other's updates.
        Advisory and cross-process; assumes a local POSIX output dir, since flock is
        unreliable over some network filesystems.
        """
        if not user:
            return
        p = self._settings_path(user)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p.parent / self.LOCK_NAME, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            data = self.load_settings(user)
            mutate(data)
            self.save_settings(user, data)  # lock released when lf closes
