---
name: renpy-check
description: Run renpy-check (static checks that `renpy lint` misses) on a Ren'Py project after editing .rpy files and before reporting a change as done; also run it first when the user pastes a Ren'Py traceback mentioning labels, init order, % in dialogue, or "not callable".
---

# renpy-check

`renpy_check.py` is a single-file, zero-dependency static checker for Ren'Py `.rpy` scripts.
It catches the class of bugs that `renpy lint` accepts but that crash at runtime:
missing jump/call targets (including label names stored as strings in dicts), init-order
NameErrors across files, bare `%` in dialogue, duplicate define/default, screen indentation
and paren problems, `$` inside `python:` blocks, and more (codes C01–C16, plus opt-in C17 for label fall-through; see README).

This file is written for any AI coding agent (Claude Code, Codex, Cursor, Copilot, Gemini CLI, …).
Nothing in it depends on a particular tool: you only need a shell and Python 3.

## When to run it

* After every batch of edits to `.rpy` files, before telling the user the change is ready.
* When the user pastes a Ren'Py traceback — run it first; the offending line is often one of C03/C06/C11/C12/C14.
* Before a build or release.

## How to run

```
python renpy_check.py <game-folder-or-project-root> --lang en --quiet
```

* Locate the script: usually the project root, or wherever the repo keeps its tools. If it is absent, download the single file from https://github.com/yurthon/renpy-check (MIT) into the project root.
* Exit code 0 = clean, 1 = problems, 2 = bad arguments.
* If the project keeps label names inside dict tables under keys other than `label`/`loop`, pass `--label-keys label,loop,next`.
* `--only C03,C11` / `--skip C06` narrow the run; `--lang zh` or `both` for Chinese messages.
* `--with C17` also reports labels that fall through into the next label (off by default because it is legal Ren'Py; turn it on before inserting new labels into an old file).
* `python renpy_codemap.py <game> -o codemap.html` writes a searchable HTML map of every file, label (with callers and orphans) and screen — useful before a refactor or when asked "where is X".

## Reading the output

Each hit is `[X] Cxx file:line  message` followed by the offending source line (and, for C11, where the other definition lives).
Fix in source order and re-run until it prints "OK — all green". Do not silence a check with `--skip` unless you have confirmed the report is a false positive — and then say so to the user.

## Limits

Text-level heuristics, not a full parser: it complements `renpy lint`, it does not replace it. Also run `renpy lint` when the SDK is available:
`<sdk>/renpy.sh <project> lint` (Windows: `renpy.exe <project> lint`).
