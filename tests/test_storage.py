"""The on-disk tenancy model, and the guards that keep untrusted codes inside it.

Workspace codes reach these functions from a browser ``dcc.Store``, so they are untrusted
input on the way to ``shutil.rmtree``. The traversal tests below are the reason
``_validate_child`` exists, and they are the ones to keep if the rest ever gets trimmed.
"""

from __future__ import annotations

import pytest

from pbi_app_shell import Settings, Workspaces


@pytest.fixture(name="ws")
def _ws(tmp_path):
    """A model rooted in tmp_path, with no environment override in play."""
    return Workspaces(output_dir_env="PBI_TEST_OUTPUT_DIR",
                      default_dir=tmp_path / "output", download_prefix="pbi")


# --- the root -------------------------------------------------------------------

def test_the_env_var_overrides_the_default_root(tmp_path, monkeypatch, ws):
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("PBI_TEST_OUTPUT_DIR", str(elsewhere))
    # Resolved per call, not at construction: a deployment may set the variable after
    # import, and gunicorn workers inherit it rather than the value we booted with.
    assert ws.output_root() == elsewhere
    assert elsewhere.is_dir()


def test_a_workspace_dir_is_the_full_user_slash_code_joined_whole(ws):
    assert ws.workspace_dir("Ada/blue_moon") == ws.output_root() / "Ada" / "blue_moon"
    assert ws.display_code("Ada/blue_moon") == "blue_moon"
    assert ws.code_user("Ada/blue_moon") == "Ada"


# --- users ----------------------------------------------------------------------

def test_guest_is_undeletable_and_unrenameable_in_any_case(ws):
    ws.ensure_guest()
    for name in ("Guest", "guest", "GUEST"):
        with pytest.raises(ValueError):
            ws.delete_user(name)
        with pytest.raises(ValueError):
            ws.rename_user(name, "Ada")
    assert (ws.output_root() / "Guest").is_dir()


def test_a_user_name_must_be_letters_and_not_reserved(ws):
    assert ws.create_user("Ada") == "Ada"
    for bad in ("", "Ada Lovelace", "ada1", "cache", "temp", "Guest", "../escape"):
        with pytest.raises(ValueError):
            ws.create_user(bad)


def test_list_users_puts_guest_first_then_the_rest_case_insensitively(ws):
    ws.ensure_guest()
    for n in ("zoe", "Ada", "bob"):
        ws.create_user(n)
    assert ws.list_users() == ["Guest", "Ada", "bob", "zoe"]


def test_renaming_a_user_carries_their_workspaces(ws):
    ws.create_user("Ada")
    ws.create_workspace("Ada", "one")
    ws.rename_user("Ada", "Grace")
    assert ws.list_workspaces("Grace") == ["Grace/one"]
    assert not (ws.output_root() / "Ada").exists()


# --- workspace naming: the one behaviour the three apps disagreed on ------------

def test_a_typed_name_is_validated_and_used(ws):
    assert ws.create_workspace("Ada", "my-run_2") == "Ada/my-run_2"
    with pytest.raises(ValueError):
        ws.create_workspace("Ada", "my-run_2")           # already taken
    for bad in ("has space", "has.dot", "a/b", ".hidden", "cache"):
        with pytest.raises(ValueError):
            ws.create_workspace("Ada", bad)


def test_a_blank_name_falls_back_to_the_lowest_free_workspace_n(ws):
    # The boot path and the re-point after deleting the last workspace have nobody to ask.
    assert ws.create_workspace("Ada") == "Ada/workspace_1"
    assert ws.create_workspace("Ada") == "Ada/workspace_2"
    ws.delete_workspace("Ada/workspace_1")
    assert ws.create_workspace("Ada") == "Ada/workspace_1"


def test_a_code_factory_names_the_blank_case_and_sees_what_is_taken(tmp_path):
    seen = []

    def factory(existing):
        seen.append(set(existing))
        return f"minted_{len(existing)}"

    ws = Workspaces(output_dir_env="PBI_TEST_OUTPUT_DIR",
                    default_dir=tmp_path / "output", download_prefix="pbi",
                    code_factory=factory)
    assert ws.create_workspace("Ada") == "Ada/minted_0"
    assert ws.create_workspace("Ada") == "Ada/minted_1"
    assert seen[1] == {"minted_0"}
    # An explicit name still wins over the factory.
    assert ws.create_workspace("Ada", "typed") == "Ada/typed"


# --- the destructive-path guard -------------------------------------------------

@pytest.mark.parametrize("code", [
    "Ada/../../escape",     # climbs out of the output root
    "Ada",                  # one segment: a USER dir, not a workspace
    "Ada/deep/nested",      # three segments
    "Ada/cache",            # reserved segment
    "cache/thing",          # reserved segment
    "Ada/.hidden",          # hidden segment
])
def test_validate_child_refuses_anything_that_is_not_a_direct_child(ws, code):
    with pytest.raises(ValueError):
        ws._validate_child(code)  # pylint: disable=protected-access


def test_deleting_a_workspace_cannot_escape_the_root(ws, tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("x", encoding="utf-8")
    ws.create_workspace("Ada", "real")
    # delete_workspace short-circuits on a non-existent dir, so aim the traversal at one
    # that DOES exist: <root>/Ada/real/../../../victim.
    with pytest.raises(ValueError):
        ws.delete_workspace("Ada/real/../../../victim")
    assert (victim / "keep.txt").exists()


def test_reset_keeps_the_dir_and_its_description_but_nothing_else(ws):
    code = ws.create_workspace("Ada", "run")
    ws.set_description(code, "the good one")
    (ws.workspace_dir(code) / "data.csv").write_text("a,b", encoding="utf-8")
    (ws.workspace_dir(code) / "sub").mkdir()
    ws.reset_workspace(code)
    assert ws.workspace_exists(code)
    assert ws.get_description(code) == "the good one"
    assert [p.name for p in ws.workspace_dir(code).iterdir()] == ["workspace.json"]


def test_renaming_a_workspace_stays_under_the_same_user(ws):
    ws.create_workspace("Ada", "old")
    assert ws.rename_workspace("Ada/old", "new") == "Ada/new"
    with pytest.raises(ValueError):
        ws.rename_workspace("Ada/new", "a/b")        # a slash would change the user
    ws.create_workspace("Ada", "other")
    with pytest.raises(ValueError):
        ws.rename_workspace("Ada/new", "other")      # destination exists


# --- the picker -----------------------------------------------------------------

def test_the_overview_carries_descriptions_and_hides_the_sort_key(ws):
    ws.create_workspace("Ada", "one")
    ws.set_description("Ada/one", "first")
    ws.create_workspace("Ada", "two")
    rows = ws.workspaces_overview("Ada")
    assert {r["code"] for r in rows} == {"Ada/one", "Ada/two"}
    assert next(r for r in rows if r["code"] == "Ada/one")["description"] == "first"
    assert next(r for r in rows if r["code"] == "Ada/two")["description"] == ""
    assert all(set(r) == {"code", "description", "last_modified"} for r in rows)


def test_an_unreadable_meta_file_reads_as_no_description(ws):
    code = ws.create_workspace("Ada", "one")
    (ws.workspace_dir(code) / "workspace.json").write_text("{not json", encoding="utf-8")
    assert ws.get_description(code) == ""


# --- download names -------------------------------------------------------------

def test_a_download_name_carries_prefix_workspace_and_stem_all_sanitised(ws):
    name = ws.download_filename("Ada/blue moon", "my results", "csv",
                                when="2026-03-04 05:06")
    assert name == "pbi_03-04-05-06_blue_moon_my_results.csv"


def test_an_unparseable_stamp_falls_back_to_now_rather_than_raising(ws):
    assert ws.download_filename("Ada/x", "s", "csv", when="not a date").endswith("_x_s.csv")
    assert ws.download_filename("Ada/x", "s", "csv", when=None).startswith("pbi_")


def test_extra_is_inserted_before_the_stem(ws):
    name = ws.download_filename("Ada/x", "stem", "tsv", extra="dataset A",
                                when="2026-03-04 05:06")
    assert name == "pbi_03-04-05-06_x_dataset_A_stem.tsv"


# --- per-user settings ----------------------------------------------------------

def test_settings_land_one_level_up_from_a_workspace(ws):
    settings = Settings(ws)
    ws.create_workspace("Ada", "run")
    settings.save_settings("Ada", {"density": "compact"})
    # The user's file, NOT the workspace's — nesting it per workspace would silently give
    # every workspace its own copy of the user's preferences.
    assert (ws.output_root() / "Ada" / "settings.json").exists()
    assert not (ws.workspace_dir("Ada/run") / "settings.json").exists()
    assert settings.load_settings("Ada") == {"density": "compact"}


def test_settings_without_a_user_are_a_no_op_not_a_crash(ws):
    settings = Settings(ws)
    settings.save_settings("", {"a": 1})
    settings.update_settings("", lambda d: d.update(a=1))
    assert settings.load_settings("") == {}


def test_a_torn_settings_file_reads_as_empty(ws):
    settings = Settings(ws)
    settings.save_settings("Ada", {"a": 1})
    (ws.output_root() / "Ada" / "settings.json").write_text("{half", encoding="utf-8")
    assert settings.load_settings("Ada") == {}


def test_update_settings_merges_rather_than_replacing(ws):
    settings = Settings(ws)
    settings.save_settings("Ada", {"density": "compact"})
    settings.update_settings("Ada", lambda d: d.__setitem__("theme", "dark"))
    assert settings.load_settings("Ada") == {"density": "compact", "theme": "dark"}


def test_a_saved_settings_file_stays_world_readable(ws):
    # mkstemp creates 0600; without the explicit chmod the atomic replace would silently
    # make a user's settings unreadable to a gunicorn worker running as someone else.
    settings = Settings(ws)
    settings.save_settings("Ada", {"a": 1})
    mode = (ws.output_root() / "Ada" / "settings.json").stat().st_mode & 0o777
    assert mode == 0o644
