"""Who the consuming app is — the one thing every shared component needs to know.

This module exists to invert a dependency. In every app this code was extracted from,
the shared modules reached *into* the app for their identity::

    from config import REPO            # spectrum_visualizer, pbi_app_template
    REPO = "AG-Walz/immunoxplore"      # immunoxplore, hardcoded

Either form makes the module unpackageable: a library cannot import its consumer. So
the app builds an :class:`AppIdentity` and passes it in, and nothing here ever imports
app code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppIdentity:
    """What the shared components need in order to name the app they are serving.

    ``repo`` is the issue tracker that receives feedback — ``owner/name``. Its DEFAULT
    branch must carry ``.github/ISSUE_TEMPLATE/`` forms declaring a ``context`` field;
    GitHub resolves ``?template=`` only on the default branch. Reference copies of
    those forms ship in this repo, because issue forms live per-repo and cannot be
    inherited from a package.

    ``host`` is the machine the app runs on, when that is a fact about the deployment
    the user needs (an app that moves files *to and from* "this computer" cannot leave
    that unsaid). Empty when it does not apply.

    ``qualify_titles`` puts the app name in the issue title. Leave it False for a repo
    holding one app, where "[Bug]: " already identifies the report. Set it True for a
    repo holding several — a shared tracker cannot be read without opening every issue
    unless the title says which app it is about.
    """

    name: str
    version: str
    repo: str
    host: str = ""
    qualify_titles: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.version or not self.repo:
            raise ValueError("AppIdentity needs a name, a version and a repo")
        if self.repo.count("/") != 1:
            raise ValueError(f"repo must be 'owner/name', got {self.repo!r}")
