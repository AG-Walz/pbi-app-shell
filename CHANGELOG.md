# Changelog

## 0.2.1 — 2026-09-09

- CI: the `pure-layer` job installed with `uv pip install --system`, which fails on
  ubuntu-latest (no system Python 3.11). It now installs into a uv venv. No package
  code changed; v0.2.0 and v0.2.1 are functionally identical.

## 0.2.0 — 2026-09-08

First release. Extracted from `immunoxplore`, `spectrum_visualizer`, `pbi_app_template`
and `infra/data_transfer`, admitting only code semantically identical in at least two.

- `pbi_app_shell` (no dependencies): `AppIdentity`, the pre-filled GitHub issue-URL
  builder (`build_issue_url`, `prefilled_url`, `build_issue_title`), and the on-disk
  user/workspace model (`storage.Settings`, `storage.Workspaces`).
- `pbi_app_shell.ui` (`[dash]` extra): the 32-glyph house icon set (`IconSet`, seeded by
  glyph name, so no longer append-only), header pieces (`resmon_now`, `host_badge`,
  `report_menu`, `register_*`), the docs drawer, and `assets.mount()` for the shared
  stylesheet.
- Reference copies of `bug_report.yml` / `feature_request.yml` in `.github/ISSUE_TEMPLATE/`.
