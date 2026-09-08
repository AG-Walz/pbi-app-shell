"""The URL builder, and the issue forms it has to agree with.

Four of these read the YAML rather than the Python, because that is where the defect
that motivated this package lived: ``render: markdown`` on the ``context`` field made
GitHub re-wrap an already-fenced snapshot, and the report arrived as raw text with the
backticks showing. Every test of the builder passed throughout.
"""

from __future__ import annotations

import pathlib
import urllib.parse

import pytest
import yaml

from pbi_app_shell import AppIdentity, build_issue_title, build_issue_url, prefilled_url
from pbi_app_shell import bug_report

FORMS = pathlib.Path(__file__).resolve().parents[1] / ".github" / "ISSUE_TEMPLATE"

ONE_APP = AppIdentity(name="MSpecViz", version="2.1.0", repo="AG-Walz/spectrum_visualizer")
MANY_APPS = AppIdentity(name="Data Transfer", version="1.1.0", repo="AG-Walz/infra",
                        host="nacho", qualify_titles=True)


def _query(url: str) -> dict:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


# --- identity -------------------------------------------------------------------

def test_an_identity_without_a_repo_is_refused_at_construction():
    # A missing repo would silently build https://github.com//issues/new.
    with pytest.raises(ValueError):
        AppIdentity(name="X", version="1.0", repo="")
    with pytest.raises(ValueError):
        AppIdentity(name="X", version="1.0", repo="not-owner-slash-name")


# --- titles ---------------------------------------------------------------------

def test_a_single_app_repo_gets_the_bare_house_prefix():
    assert build_issue_title(ONE_APP, "bug_report.yml") == "[Bug]: "
    assert build_issue_title(ONE_APP, "feature_request.yml") == "[Enhancement]: "


def test_a_repo_holding_several_apps_says_which_one():
    # AG-Walz/infra holds data_transfer and data_mover; a shared tracker cannot be
    # read without opening every issue unless the title carries the app.
    assert build_issue_title(MANY_APPS, "bug_report.yml") == "[Bug][Data Transfer]: "


# --- the URL --------------------------------------------------------------------

def test_the_snapshot_is_inlined_as_a_fenced_json_block():
    url, complete = build_issue_url(ONE_APP, "bug_report.yml", {"page": "/spectra"})
    query = _query(url)
    assert complete
    assert query["template"] == "bug_report.yml"
    assert query["title"] == build_issue_title(ONE_APP, "bug_report.yml")
    assert query["context"].startswith("```json")
    assert "/spectra" in query["context"]


def test_an_oversized_snapshot_sheds_the_fields_the_app_named_first():
    """``droppable`` is ordered by what the app is willing to lose.

    The fields that identify the report must be the last thing to go: a report that
    survives as "something failed somewhere" is not worth the bytes it kept.
    """
    snapshot = {"from": "highmem1:/data", "to": "this computer:/mnt/f",
                "selection": "x" * 9000, "result": "y" * 9000}
    url, complete = build_issue_url(MANY_APPS, "bug_report.yml", snapshot,
                                    droppable=("result", "selection"))
    context = _query(url)["context"]
    assert not complete
    assert len(url.encode("utf-8")) <= bug_report.MAX_PREFILL_URL_BYTES
    assert "highmem1:/data" in context and "this computer:/mnt/f" in context


def test_an_overflowing_report_still_arrives_titled():
    # The title costs ~30 bytes and identifies the report; it is never what is shed.
    url, complete = build_issue_url(MANY_APPS, "bug_report.yml",
                                    {"result": "y" * 9000}, droppable=("result",))
    assert not complete
    assert _query(url)["title"] == build_issue_title(MANY_APPS, "bug_report.yml")


def test_the_caller_is_told_when_nothing_was_dropped():
    _, complete = build_issue_url(ONE_APP, "bug_report.yml", {"page": "/x"},
                                  droppable=("page",))
    assert complete


# --- the link before there is anything to say -----------------------------------

def test_the_menu_opens_a_real_form_before_any_snapshot_exists():
    """Never a bare ``issues/new`` — that is GitHub's template chooser, not a form."""
    for template in ("bug_report.yml", "feature_request.yml"):
        query = _query(prefilled_url(MANY_APPS, template))
        assert query["template"] == template
        assert query["title"] == build_issue_title(MANY_APPS, template)


# --- the forms themselves -------------------------------------------------------
# Reference copies. Issue forms live per-repo — GitHub resolves ?template= only on a
# repo's own default branch — so these cannot be inherited from a package. They are
# here to be copied, and to be guarded.

def _form(name: str) -> dict:
    return yaml.safe_load((FORMS / name).read_text())


def _field(form: dict, field_id: str) -> dict:
    return next(b for b in form["body"] if b.get("id") == field_id)


@pytest.mark.parametrize("name", ["bug_report.yml", "feature_request.yml"])
def test_the_snapshot_field_does_not_re_wrap_what_is_already_fenced(name):
    """``render:`` makes GitHub wrap submitted text in a code block of its own.

    The snapshot arrives already fenced as ```json, so the two nest at the same
    backtick depth and break each other. This is the defect that reached one app
    through a copied template and stayed there.
    """
    assert "render" not in _field(_form(name), "context")["attributes"]


@pytest.mark.parametrize("name,prefix,label", [
    ("bug_report.yml", "[Bug]", "bug"),
    ("feature_request.yml", "[Enhancement]", "enhancement"),
])
def test_the_forms_default_to_the_same_prefix_the_builder_uses(name, prefix, label):
    form = _form(name)
    assert form["title"].startswith(prefix)
    assert form["labels"] == label
    assert bug_report.TITLE_KINDS[name] == prefix


@pytest.mark.parametrize("name,field", [("bug_report.yml", "screenshots"),
                                        ("feature_request.yml", "sketches")])
def test_each_form_offers_a_place_to_drop_an_image(name, field):
    # A footnote saying "drag a screenshot in" is not a field, and does not get used.
    assert _field(_form(name), field)


@pytest.mark.parametrize("name", ["bug_report.yml", "feature_request.yml"])
def test_the_field_the_builder_fills_is_the_field_the_form_declares(name):
    # ?context= only lands if the form declares that exact id; a rename on either
    # side silently drops the whole snapshot with no error anywhere.
    assert "context" in _query(build_issue_url(ONE_APP, name, {"a": 1})[0])
    assert _field(_form(name), "context")
