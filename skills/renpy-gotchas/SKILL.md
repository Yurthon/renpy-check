---
name: renpy-gotchas
description: Ren'Py (8.x, Python 3) behaviours that are not obvious from the docs and that crash or silently misbehave at runtime — read before writing or editing .rpy code (screens, Character(), init blocks, jumps, python blocks) and when debugging "it works after reload but not on a cold start", "no crash but nothing happens", or "'str' object is not callable".
---

# renpy-gotchas

A field guide to Ren'Py behaviours that bit a real project. Each item: the rule, why it happens, what to do.
Written for any AI coding agent (Claude Code, Codex, Cursor, Copilot, Gemini CLI, …) and for humans.
Companion checker: `renpy_check.py` in this repo catches the mechanical ones (marked **[Cxx]**); the rest need judgement.

## 1. `Return()` with no value returns `True`, not `None`  ｜ `Return(None)` 返回的是 True

`Return(value=None)` is the standard "close this screen" action. When `value` is None, Ren'Py ends the interaction by returning **`True`**. So a caller written as

```renpy
call screen shop
if _return is None:
    return          # never taken
```

falls through into the branch below, which typically does `_return["item"]` → `TypeError: 'bool' object is not subscriptable`, or jumps back into the same loop forever ("I can't close this screen").

**Do:** close buttons return an explicit sentinel — `Return("close")` — and callers test for it. If you must accept both: `if _return is None or _return is True:`.
**Also:** when you find this bug once, grep the whole project for `Return(None)` / bare `Return()` in `call screen` targets. It is never in only one place.

## 2. `Character(slow_cps=30)` styles the *name*, not the dialogue  ｜ 不带前缀的属性是给名牌的

`Character()` sorts keyword arguments by prefix: `what_` (dialogue text), `who_` (name label), `window_` (the box), `show_`, `cb_`. **Anything with no prefix goes to `who_`** — i.e. the speaker's name. `Character("Eve", slow_cps=30)` sets the typing speed of the name (which does not type), and the dialogue speed silently stays at `preferences.text_cps` — which in a fresh project's `options.rpy` is often `0` (instant). Nothing crashes; the feature just never worked.

**Do:** dialogue properties always carry `what_`: `what_slow_cps`, `what_size`, `what_color`, `what_font`, `what_outlines`. Name: `who_`. Box: `window_`.

## 3. A `define` without a priority runs at `init 0` — *after* every `init -N`  ｜ **[C14]**

`define X = 1` and `default X = 1` with no number run at init priority **0**. `init -5 python:` that reads `X` raises `NameError` on a cold start — and then works after a reload (because the store already has it), which makes it look intermittent. Order inside a file is irrelevant; priority and file name decide.

**Do:** constants used by early init get an explicit lower priority: `define -10 X = 1`, with the number smaller than any block that reads it. Same-priority blocks run in **file-name order**, so an `init python` at priority 0 in `b.rpy` cannot rely on a plain `define` in `c.rpy` **[C06]**.

## 4. The store is one namespace: a `def` and a `default` with the same name collide  ｜ **[C12]**

`init python: def rank(x): …` plus `default rank = "none"` anywhere → when the game starts, `default` assigns the string over the function → `TypeError: 'str' object is not callable` at the first call, far from either definition.

**Do:** never share a name between a function and a variable. Prefix helpers (`_rank_of`) or namespace them in a module-level object.

## 5. Module-level names in `init python` are globals — you can overwrite Ren'Py's own  ｜ **[C15]**

`init python:` bodies execute in the store. A throwaway `_p = os.path.join(...)` at module level overwrites `_p`, Ren'Py's paragraph-translation function, and `options.rpy`'s `define gui.about = _p("""…""")` dies with `'str' object is not callable` **on boot**. Same for `_`, `config`, `store`, `renpy`, `persistent`, `preferences`, `style`, `gui`, `adv`, `nvl`, `narrator`, `centered`, `extend`, `menu`, `_window`, `_history`, …

**Do:** in debug/probe snippets, prefix every module-level name (`_dbg_path`), or put the code in a function. Never `for _ in range(…)` at module level in an init block.

## 6. Silent `except: pass` around a hook install hides the failure for weeks

Wrapping `store.adv = MyADV(...)` (or `config.notify = …`, `config.all_character_callbacks.append(…)`, `renpy.add_layer(…)`) in `try: … except Exception: pass` means a `NameError` inside (see #3) is swallowed and the hook is **never installed**. The game runs; the feature is just absent; nobody notices because "self-check is green".

**Do:** hooks log on failure (`print` + `traceback.print_exc()`, which goes to `log.txt`) — never `pass`. After shipping a hook, verify on a real run that it fired (a log line, a visible effect). Static checks prove syntax, not that a hook took.

## 7. `Character(callback=…)` may never fire; `config.all_character_callbacks` always does

On at least some 8.5.x installs a per-character `callback=` never ran (verified with a probe that logged every event), while a function appended to `config.all_character_callbacks` received `begin`/`show`/`end` for every line with full kwargs. One global function that looks at `renpy.get_say_image_tag()` or an attribute you set on the Character is also simpler than N closures.

**Do:** prefer the global list for per-line hooks (voice blips, text rhythm, dimming others). Keep the per-character one, if any, inert.

## 8. In character callbacks, `what` has `{w}`/`{p}` already stripped — use `start`/`end`

The `what` passed to a callback is the text **after** dialogue-tag parsing: `{w}`, `{p}`, `{nw}`, `{fast}` are gone. The `"show"` event fires **once per pause segment** with kwargs `start`, `end` (indices into `what`), `delay`, `last_segment`. Splitting `what` on `{w}` yourself therefore always yields one segment; the first gets everything, the rest get `""`.

**Do:** segment text = `what[start:end]`, fall back to the whole string when the kwargs are absent (`config.character_callback_compat` must be `None`, the default, for them to be passed). Return early when `renpy.is_skipping()` — no sound during skip is what players expect.

## 9. Screen-language property values are *simple expressions*  ｜ **[C09] [C13]**

A property value in screen language is parsed with `simple_expression()`, not full Python. So a backslash line-continuation inside a property, or a property appended after a multi-line `(a if b else c)` that is not closed on that line, gives `expected statement` / `end of line expected` / `SyntaxError: expected 'else' after 'if'` — at a line that looks fine in isolation.

**Do:** compute the value in a `$ x = …` line (or a `python:` block in the screen) and reference `x`. When a patch script appends a property to an existing line, assert that the line is a complete statement first.

## 10. `xalign` + `xpos` on the same line is an error  ｜ **[C10]**

`keyword argument 'xpos' is incompatible with 'xalign'` (same for `yalign`/`ypos`, `align`/`pos`, `anchor`+`align`). Common after merging two people's edits to one `text` line.

## 11. Two `define`s of the same name: no error, the last file wins  ｜ **[C11]**

Ren'Py does not complain about `define e = Character("Eve", color="#f00")` in `a.rpy` and `define e = Character("Eve", color="#0f0")` in `z.rpy`; you get green Eve and an afternoon of confusion. Duplicate `default` *does* crash (`is being given a default a second time`). Duplicate `label`/`screen` crash too.

## 12. `$` inside a `python:` block is a syntax error  ｜ **[C16]**

`$` is Ren'Py statement sugar for one-line Python. Inside `python:` / `init python:` you are already in Python; `$ x = 1` there is `SyntaxError: invalid syntax`.

## 13. Bare `%` in dialogue is a format code  ｜ **[C04]**

Say text goes through `%`-substitution when `config.interpolate` is on (default). `e "100% sure"` → `ValueError: unsupported format character` / `incomplete format`. Write `100%%` (or `100 percent`).

## 14. Label names stored as strings in tables are invisible to `renpy lint`  ｜ **[C03]**

Event-driven games keep `EVENTS = {"day3": {"label": "ev_day3"}}` and later `renpy.jump(ev["label"])`. A typo there is found only when that branch is reached on a real run, days later. `renpy lint` checks `jump`/`call` statements only.

**Do:** run `renpy_check.py --label-keys label,loop,next` (whatever keys your tables use). Or route every table jump through one function that asserts `renpy.has_label(name)` at init.

## 15. Fall-through between labels is legal — and fragile

```renpy
label smithy:
    "You enter the smithy."
label smithy_menu:
    menu: …
```

`smithy` reaches `smithy_menu` by falling off its end. Insert any new label between them and `smithy` now silently lands somewhere else — no error, "the smithy can't be entered" is reported a week later. The same trap hides at the end of an `if` branch that jumps with no `else`.

**Do:** end every label with an explicit `jump`/`return`/`call … return`, especially the label right above a `menu:`. Before inserting a label into an existing file, look at what the previous label's last statement is.

## 16. Ren'Py loads `.rpy` files recursively — make your own tools do so too

Anything under `game/` in any subfolder is loaded. A home-made checker (or a one-off `grep *.rpy`) that only looks at the top level misses whole directories and reports "all green". Use `os.walk` / `grep -r --include="*.rpy"`.

## 17. `{}` and `[]` in `.rpy` code are `RevertableDict`/`RevertableList`

Containers created from Ren'Py script (including `init python`) participate in rollback: PageUp reverts their contents. Fine for game state; wrong for tooling state (an editor's live values, caches, registries), where rollback "un-saves" what the user just did.

**Do:** for non-game state build plain containers — `json.loads("{}")`, `dict()` called from a plain Python module, or store them outside the store.

## 18. `config.keymap` is rebuilt at a very negative init priority

`00keymap.rpy` builds `config.keymap` around priority -1600…-1100. Adding a key in `init -100 python` is silently overwritten. Register keys at `init` ≥ 0 (or in `init python` with no priority), and if a key must work under a modal screen, use `config.underlay.append(renpy.Keymap(...))` rather than a `key` statement in a screen.

## 19. Do not play audio during init

`renpy.music.play` / `renpy.sound.play` in an `init` block → `Exception: Can't play music during init phase.` Play from a label, a screen action, or `config.start_callbacks`.

## 20. Static checks do not prove a feature runs

"All green" from lint and checkers proves syntax and references. It does not prove a hook installed (#6), a callback fired (#7), a property landed on the right target (#2), or that a table jump is reachable (#14). After shipping something, look for evidence on a real run — a log line, a visible change — before calling it done.

---

Contributions: open an issue with the traceback and the minimal `.rpy` that reproduces it. Rule + why + what-to-do, in that order.
