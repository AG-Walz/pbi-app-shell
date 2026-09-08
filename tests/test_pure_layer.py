"""The pure layer has to stay importable in an environment with no Dash.

``[project] dependencies`` is empty on purpose: a CLI, a batch job or a test that never
renders anything still wants the issue-URL builder and the on-disk model. That promise is
easy to break with one convenience import at the top of a module, and nothing else in the
suite would notice — the dev environment has Dash installed.

Run in a subprocess with ``dash`` and ``dash_mantine_components`` blocked at import, which
is the same thing a consumer's non-UI environment does, without needing a second venv.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_BLOCK = """
import sys

class _Blocker:
    BLOCKED = ("dash", "dash_mantine_components", "flask", "plotly")

    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in self.BLOCKED:
            raise ImportError(f"blocked for this test: {name}")
        return None

sys.meta_path.insert(0, _Blocker())
"""


def _run(body: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", _BLOCK + textwrap.dedent(body)],
                          capture_output=True, text=True, check=False)


def test_the_pure_api_imports_and_works_without_dash():
    r = _run("""
        import pbi_app_shell
        from pbi_app_shell import AppIdentity, Settings, Workspaces, build_issue_url
        app = AppIdentity(name="X", version="1.0", repo="AG-Walz/x")
        url, complete = build_issue_url(app, "bug_report.yml", {"page": "/"})
        assert "issues/new" in url and complete
        ws = Workspaces(output_dir_env="X_OUT", default_dir="/tmp/x-out",
                        download_prefix="x")
        assert ws.display_code("Ada/one") == "one"
        assert Settings(ws).load_settings("") == {}
        print("ok")
    """)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_importing_the_ui_without_dash_says_which_extra_to_install():
    # Not a bare ModuleNotFoundError from three imports deep: the message has to name the
    # extra, because "no module named dash" in an app that has Dash installed sends people
    # looking in the wrong place.
    r = _run("""
        try:
            import pbi_app_shell.ui  # noqa: F401
        except ImportError as exc:
            print("MSG:", exc)
    """)
    assert r.returncode == 0, r.stderr
    assert "pbi-app-shell[dash]" in r.stdout
