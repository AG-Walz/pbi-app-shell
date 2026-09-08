"""Users and workspaces — the on-disk tenancy model the consuming apps hang off.

Two levels under one output root::

    <output_root>/<user>/<workspace_code>/

A **user** is just a directory. Soft identity, no passwords: switching to a user grants
full access to it (a cooperative model, like shared home dirs on a lab machine). ``Guest``
is the undeletable default that anonymous sessions land in. Names are letters-only, so a
user segment never needs escaping in a path.

A **workspace** is a directory under a user, named by a code that can be typed into the UI
to return to it. Workspaces persist until someone deletes them — there is no automatic
cleanup, so the UI reminds users to remove old ones.

There is **no server-side session state**. The active user and workspace code live in
browser-side ``dcc.Store``s and everything heavy stays here on disk, which is what lets
several gunicorn workers serve the same workspace.

Every destructive operation re-validates the path it resolved. The codes arrive from a
client-side store, so they are untrusted input: a tampered value must not be able to
escape the output root, hit a reserved name, or reach anything other than a direct
``<user>/<code>`` child.

The whole model is a class rather than module functions because the output root is the
app's to choose. Apps bind an instance's methods into their own ``services/workspace.py``
so their call sites keep importing plain functions::

    _ws = Workspaces(output_dir_env="PBI_APP_OUTPUT_DIR", default_dir=..., ...)
    output_root = _ws.output_root
    workspace_dir = _ws.workspace_dir
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

_BARE_CODE_RE = re.compile(r"[A-Za-z0-9_-]+")


def sanitize_filename(name: str) -> str:
    """Collapse anything outside ``[A-Za-z0-9._-]`` to underscores, for download names."""
    return _FILENAME_UNSAFE.sub("_", (name or "").strip()) or "file"


class Workspaces:
    """The tenancy model rooted at one output directory.

    ``output_dir_env`` is the environment variable a deployment overrides the root with;
    ``default_dir`` is where it lands when that variable is unset. ``download_prefix`` is
    the leading token of every generated download name, so files from different apps stay
    distinguishable in one flat Downloads folder.

    ``code_factory`` decides what a workspace is called when the caller supplies no name.
    It receives the bare codes already taken under that user and returns a fresh one — an
    app that wants memorable ``adjective_noun`` codes passes a factory that mints them,
    keeping that dependency out of this package. Left as ``None``, a blank name falls back
    to ``workspace_N`` with the lowest free N. Either way an explicit name always wins.
    """

    #: Directory names that may never be a user or a workspace: they would collide with
    #: app-level storage or read as something other than tenancy.
    RESERVED = frozenset({"cache", "figures", "data", "temp"})

    #: The default, undeletable user that anonymous sessions land in.
    GUEST = "Guest"

    #: Per-workspace metadata file, preserved by :meth:`reset_workspace`.
    META_NAME = "workspace.json"

    sanitize_filename = staticmethod(sanitize_filename)

    def __init__(self, *, output_dir_env: str, default_dir: Path | str,
                 download_prefix: str,
                 code_factory: Callable[[set[str]], str] | None = None) -> None:
        self.output_dir_env = output_dir_env
        self.default_dir = Path(default_dir)
        self.download_prefix = download_prefix
        self.code_factory = code_factory
        self._reserved_cf = {r.casefold() for r in self.RESERVED}

    # --- the root ------------------------------------------------------------

    def output_root(self) -> Path:
        """Root dir holding every user's workspaces. Configurable for the deployment."""
        root = Path(os.environ.get(self.output_dir_env, self.default_dir))
        root.mkdir(parents=True, exist_ok=True)
        return root

    def workspace_dir(self, code: str) -> Path:
        # ``code`` is always the FULL ``<user>/<code>`` path, and joining it whole is the
        # only thing that scopes a workspace to its user. Keep it one join: a variant
        # taking (user, code), or one that re-splits ``code``, pushes that scoping decision
        # out into every caller — which is how a workspace ends up readable from the wrong
        # user dir.
        return self.output_root() / code

    @staticmethod
    def display_code(code: str) -> str:
        """The bare workspace code for display / filenames (strips the ``<user>/`` prefix)."""
        return (code or "").split("/")[-1]

    @staticmethod
    def code_user(code: str) -> str:
        """The owning user of a workspace code (the ``<user>`` prefix of ``<user>/<code>``).

        Since the active user always equals the active workspace's owner (no mixing), this
        is how per-user stores resolve the active user from the workspace code alone."""
        return (code or "").split("/")[0]

    def download_filename(self, code: str, stem: str, ext: str, *,
                          extra: str | None = None, when: str | None = None) -> str:
        """Self-describing, collision-resistant download name.

        Format ``{prefix}_{MM-DD-HH-MM}_{workspace}_{stem}.{ext}`` — the prefix + timestamp
        + workspace make every file recognisable and unique in a flat Downloads folder. A
        browser cannot choose a subfolder, so the name has to carry the context. Both the
        workspace and the stem are filesystem-sanitised.

        ``extra`` (a dataset name, a run label) is inserted sanitised before the stem when
        given, so a downloaded artifact says which view it came from.

        ``when`` is the artifact's own ``%Y-%m-%d %H:%M`` stamp — for a run, the same
        ``meta["time"]`` its history entry is labelled from, so the file and the entry it
        came from agree. Without it the name records when the file was *fetched*, which for
        a run downloaded days later is a different day entirely. Unparseable or absent
        falls back to now, so an artifact stamped before that field existed still gets a
        name.
        """
        try:
            ts = datetime.strptime(when, "%Y-%m-%d %H:%M").strftime("%m-%d-%H-%M")
        except (TypeError, ValueError):
            ts = datetime.now().strftime("%m-%d-%H-%M")
        parts = [sanitize_filename(self.display_code(code) or "workspace")]
        if extra:
            parts.append(sanitize_filename(extra))
        parts.append(sanitize_filename(stem))
        return f"{self.download_prefix}_{ts}_{'_'.join(parts)}.{ext}"

    # --- users: the top-level namespace, output_root()/<user> ----------------

    def _user_name_ok(self, name: str) -> bool:
        """Letters only (ASCII), non-empty, and not a reserved / Guest name — all checked
        CASE-INSENSITIVELY, so a variant like 'guest' can't shadow the protected default on
        a case-insensitive filesystem (where output/'guest' IS output/'Guest')."""
        if not (name and name.isascii() and name.isalpha()):
            return False
        cf = name.casefold()
        return cf != self.GUEST.casefold() and cf not in self._reserved_cf

    def list_users(self) -> list[str]:
        """Existing user names, ``Guest`` first then the rest case-insensitively. Any
        on-disk case-variant of Guest folds into the canonical entry (never created via
        the app)."""
        root = self.output_root()
        names = [
            p.name for p in root.iterdir()
            if p.is_dir() and p.name not in self.RESERVED and not p.name.startswith(".")
        ]
        others = sorted((n for n in names if n.casefold() != self.GUEST.casefold()),
                        key=str.lower)
        return [self.GUEST] + others

    def ensure_guest(self) -> None:
        """Create ``<output_root>/Guest`` so the default user always resolves (on boot)."""
        (self.output_root() / self.GUEST).mkdir(parents=True, exist_ok=True)

    def create_user(self, name: str) -> str:
        """Validate + create (or select, if it already exists) a user dir; return the name."""
        name = (name or "").strip()
        if not self._user_name_ok(name):
            raise ValueError("User name must be letters only — and not a reserved name.")
        (self.output_root() / name).mkdir(parents=True, exist_ok=True)
        return name

    def delete_user(self, name: str) -> None:
        """Destroy a user dir and everything under it. ``Guest`` (any case) is undeletable;
        the name is re-validated so a tampered client store value can't escape the output
        root."""
        if name.casefold() == self.GUEST.casefold():
            raise ValueError("The Guest user cannot be deleted.")
        if not self._user_name_ok(name):
            raise ValueError("Invalid user name.")
        target = self.output_root() / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    def rename_user(self, old: str, new: str) -> str:
        """Rename a user dir (its workspaces, settings and snapshots follow it). ``Guest``
        (any case) is fixed; BOTH names are validated so a tampered value can't escape the
        root."""
        new = (new or "").strip()
        if old.casefold() == self.GUEST.casefold():
            raise ValueError("The Guest user cannot be renamed.")
        if not self._user_name_ok(old):
            raise ValueError("Invalid user name.")
        if not self._user_name_ok(new):
            raise ValueError("User name must be letters only (no spaces, digits or "
                             "symbols).")
        root = self.output_root()
        src, dst = root / old, root / new
        if dst.exists():
            raise ValueError(f"User '{new}' already exists.")
        if src.is_dir():
            src.rename(dst)
        return new

    # --- workspaces: output_root()/<user>/<code> -----------------------------

    def _bare_code_ok(self, name: str) -> bool:
        """A valid workspace code: the ``[A-Za-z0-9_-]`` charset only (no dots, spaces or
        slashes), not a reserved name, and not a hidden/dot-name that could escape the user
        dir."""
        return bool(name and _BARE_CODE_RE.fullmatch(name)
                    and not name.startswith(".")
                    and name.casefold() not in self._reserved_cf)

    def _validate_child(self, code: str) -> Path:
        """Resolve *code* and prove it is a direct ``<user>/<code>`` child of the root.

        The one guard every destructive operation shares. Returns the resolved path; raises
        ``ValueError`` when the code escapes the root, is not exactly two segments deep, or
        contains a reserved / hidden segment.
        """
        root = self.output_root().resolve()
        target = self.workspace_dir(code).resolve()
        rel = target.relative_to(root) if root in target.parents else None
        if (rel is None or len(rel.parts) != 2
                or any(p.casefold() in self._reserved_cf or p.startswith(".")
                       for p in rel.parts)):
            raise ValueError("Invalid workspace code.")
        return target

    def workspace_exists(self, code: str) -> bool:
        return bool(code) and self.workspace_dir(code).is_dir()

    def list_workspaces(self, user: str) -> list[str]:
        """Full ``<user>/<code>`` codes for one user, newest first."""
        root = self.output_root() / user
        if not root.is_dir():
            return []
        dirs = [
            p for p in root.iterdir()
            if p.is_dir() and p.name not in self.RESERVED and not p.name.startswith(".")
        ]
        dirs.sort(key=lambda p: p.stat().st_ctime, reverse=True)
        return [f"{user}/{p.name}" for p in dirs]

    def create_workspace(self, user: str, name: str = "") -> str:
        """Create a workspace under *user*; return the full ``<user>/<code>``.

        *name* is the code the user typed. Blank defers to ``code_factory``, and without
        one falls back to ``workspace_N`` with the lowest free N — which is what the
        callers that have nobody to ask always get: the boot path for a user with no
        workspaces, and the re-point after deleting the last one.

        Raises ``ValueError`` on a malformed name or one already taken, matching
        :meth:`rename_workspace` — the two are the same decision made at different times.
        A ``code_factory`` is trusted to return a valid code and is not re-validated
        against the charset, but its result IS path-checked like any other.
        """
        existing = {self.display_code(c) for c in self.list_workspaces(user)}
        name = (name or "").strip()
        if name:
            if not self._bare_code_ok(name):
                raise ValueError("Workspace name may use letters, digits, '_' and '-' "
                                 "only (no dots, spaces or slashes).")
            if name in existing:
                raise ValueError(f"Workspace '{name}' already exists.")
            code = name
        elif self.code_factory is not None:
            code = self.code_factory(existing)
        else:
            n = 1
            while f"workspace_{n}" in existing:
                n += 1
            code = f"workspace_{n}"
        full = f"{user}/{code}"
        self._validate_child(full)  # defence in depth: a direct child of the user dir
        self.workspace_dir(full).mkdir(parents=True, exist_ok=True)
        return full

    def delete_workspace(self, code: str) -> None:
        """Destroy a workspace dir and everything under it (data, runs, snapshots)."""
        if not self.workspace_exists(code):
            return
        shutil.rmtree(self._validate_child(code), ignore_errors=True)

    def reset_workspace(self, code: str) -> None:
        """Wipe a workspace's contents, keeping the dir and its ``workspace.json``.

        Used before loading new data, so results computed from the old data can never be
        mistaken for results from the new. The description survives because it describes
        the workspace, not its contents.
        """
        if not self.workspace_exists(code):
            return
        ws = self._validate_child(code)
        for p in ws.iterdir():
            if p.name == self.META_NAME:
                continue
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)

    def rename_workspace(self, old_code: str, new_bare: str) -> str:
        """Rename a workspace directory; everything inside it follows.

        ``old_code`` is the FULL ``<user>/<code>``; ``new_bare`` is the new bare code within
        the same user. Returns the new full ``<user>/<new_bare>``. Raises ``ValueError`` on
        a bad code, a missing source, or an existing destination.
        """
        new_bare = (new_bare or "").strip()
        if not self.workspace_exists(old_code):
            raise ValueError("Workspace not found.")
        if not self._bare_code_ok(new_bare):
            raise ValueError("Workspace code may use letters, digits, '_' and '-' only "
                             "(no dots, spaces or slashes).")
        user = self.code_user(old_code)
        new_code = f"{user}/{new_bare}"
        dst = self._validate_child(new_code)  # defence in depth: a direct child
        if dst.exists():
            raise ValueError(f"Workspace '{new_bare}' already exists.")
        self.workspace_dir(old_code).rename(dst)
        return new_code

    # --- per-workspace metadata ----------------------------------------------
    # A human-readable description, set in the workspace drawer, stored beside the code.

    def _meta_path(self, code: str) -> Path:
        return self.workspace_dir(code) / self.META_NAME

    def read_meta(self, code: str) -> dict:
        p = self._meta_path(code)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _write_meta(self, code: str, meta: dict) -> None:
        if self.workspace_exists(code):
            self._meta_path(code).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def get_description(self, code: str) -> str:
        return self.read_meta(code).get("description", "")

    def set_description(self, code: str, text: str) -> None:
        meta = self.read_meta(code)
        meta["description"] = text or ""
        self._write_meta(code, meta)

    # --- workspace listing for the picker ------------------------------------

    def _cheap_mtime(self, ws: Path) -> float:
        """Newest mtime among the dir itself and its ``workspace.json`` — a cheap proxy for
        last activity, used only to order the picker. Deliberately NOT a full ``rglob``,
        which would walk every run and artifact in the workspace on every drawer open."""
        times = [ws.stat().st_mtime]
        try:
            times.append((ws / self.META_NAME).stat().st_mtime)
        except OSError:
            pass
        return max(times)

    def workspaces_overview(self, user: str) -> list[dict]:
        """All of *user*'s workspaces with metadata for the picker, newest activity first.

        Each entry is ``{code, description, last_modified}``, where ``code`` is the full
        ``<user>/<code>`` (the picker stores that; ``display_code`` strips it for display)
        and ``last_modified`` is a ``YYYY-MM-DD`` string from the cheap stat above. Dirs
        without a ``workspace.json`` yield ``description=""``.
        """
        root = self.output_root() / user
        rows: list[dict] = []
        if not root.is_dir():
            return rows
        for p in root.iterdir():
            if not p.is_dir() or p.name in self.RESERVED or p.name.startswith("."):
                continue
            code = f"{user}/{p.name}"
            mtime = self._cheap_mtime(p)
            rows.append({
                "code": code,
                "description": self.get_description(code),
                "last_modified": time.strftime("%Y-%m-%d", time.localtime(mtime)),
                "_mtime": mtime,
            })
        rows.sort(key=lambda r: r["_mtime"], reverse=True)
        for r in rows:
            del r["_mtime"]
        return rows
