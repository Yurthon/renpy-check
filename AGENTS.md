# Instructions for AI coding agents working in this repository

* This is a single-file Python tool (`renpy_check.py`) plus tests. No dependencies; Python 3.8+.
* Before reporting any change as done, run `python tests/run_tests.py` — it must print `ALL OK`.
* A new check = one function in `renpy_check.py`, one `MSG` entry (English + 中文), one `tests/samples/bad_Cxx_*.rpy` sample that triggers only that check, and one row in the README table (both languages).
* Keep messages searchable: quote the runtime error text Ren'Py would print.
* See `skills/renpy-check/SKILL.md` for how to use the checker on a Ren'Py project.
