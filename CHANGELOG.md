# Changelog

## Unreleased
- `pyproject.toml`: `pip install git+https://github.com/yurthon/renpy-check` gives `renpy-check` and `renpy-codemap` commands.
- `.pre-commit-hooks.yaml`: use it as a pre-commit hook.
- README: codemap screenshot.
- C04 now also checks menu captions and choices (a real `[var]%）` in a menu got past 0.2.0).

## 0.2.0 — 2026-09-24
- New tool `renpy_codemap.py`: one searchable HTML page of every file, label (with callers, fall-through, orphans) and screen.
- New opt-in check C17 (`--with C17`): label fall-through, including the `if`-without-`else` form.
- New skill `skills/renpy-gotchas/SKILL.md`: 20 runtime gotchas with rule / why / what-to-do.
- Plain-language wording for C16.

## 0.1.0 — 2026-09-24
First public release. 16 checks (C01–C16), bilingual messages, sample-based tests, agent skill file (SKILL.md) for AI coding assistants.
