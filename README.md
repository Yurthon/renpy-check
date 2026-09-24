# renpy-check

[![tests](https://github.com/yurthon/renpy-check/actions/workflows/test.yml/badge.svg)](https://github.com/yurthon/renpy-check/actions/workflows/test.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) ![python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue) ![no dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

Static checks for [Ren'Py](https://www.renpy.org/) projects that `renpy lint` does not do.
One file, zero dependencies, Python 3.8+. Messages in English and 中文.

给 Ren'Py 项目做的静态检查，专抓 `renpy lint` 抓不到、真机才崩的坑。单文件、零依赖。[中文说明在下面](#中文说明)。

```
python renpy_check.py path/to/your/game
```

```
[X] C04 script.rpy:12  bare % in a say line — Ren'Py treats % as a format code (write %% for a literal percent)
      e "I am 100% sure this crashes."
[X] C11 vars.rpy:3  duplicate definition — Ren'Py silently keeps the LAST define; a duplicate default crashes with “is being given a default a second time”
      also defined at vars.rpy:1
================================================
renpy-check 0.1.0 · 41 files · 16 checks
2 problem(s)
```

Exit code `0` = clean, `1` = problems found, `2` = bad arguments.

## Why

Every check here exists because a real game crashed on a real machine after `renpy lint` said everything was fine.
Most of them are about things Ren'Py resolves *at runtime* (label names inside data tables, init ordering across files, `%` in dialogue) or things the parser accepts but the engine then misuses.

If you got here from a search for one of the error messages below — that is the point. Each check lists the runtime error it prevents.

## Install

There is nothing to install. Copy `renpy_check.py` anywhere (into your project root is convenient) and run it with Python 3.

```
python renpy_check.py game                 # scan a game/ folder
python renpy_check.py .                    # a project root that contains game/ also works
python renpy_check.py game --lang en       # en | zh | both (default: both)
python renpy_check.py game --only C08,C11  # run a subset
python renpy_check.py game --skip C06      # skip a check
python renpy_check.py game --quiet         # print problems only
python renpy_check.py game --label-keys label,loop,next   # dict keys whose string values name labels (C03)
```

It does **not** import Ren'Py and does not need the SDK, so it is fast (a 160-file project takes ~3 s) and safe to run from a pre-commit hook or CI.

## The checks

| id | catches | the error you would otherwise see at runtime |
|----|---------|----------------------------------------------|
| C01 | truncated file / not valid UTF-8 / NUL bytes | `UnicodeDecodeError: 'utf-8' codec can't decode byte …` |
| C02 | a line ending in `:` with no indented body | `expected a non-empty block` |
| C03 | `jump` / `call` / `Jump()` / `Call()` target label does not exist; `call screen` target does not exist; **label names stored as strings inside dicts** (`{"label": "ev_x"}`) that point nowhere | `The label ev_x does not exist.` / `Screen … is not known.` — but only when that branch is finally reached |
| C04 | a bare `%` in a say line | `ValueError: unsupported format character` / `incomplete format` — dialogue text goes through `%` substitution |
| C05 | screen-language indentation: a line indented deeper than the previous, but the previous line does not open a block | `Line is indented, but the preceding statement does not expect a block.` |
| C06 | `init python` (priority ≤ 0) that uses a `define`/`default` from **another file** at module level | `NameError: name 'X' is not defined` — same-priority init blocks run in file-name order |
| C07 | speaker in a say line is not a defined `Character` (typo) | `Sayer 'ee' is not a function or string.` |
| C08 | top-level `define`/`default` expression that does not compile | `SyntaxError` inside the define |
| C09 | backslash line-continuation inside screen properties | `expected statement` / `end of line expected` |
| C10 | `xalign` + `xpos` (or `yalign` + `ypos`, `align` + `pos`) on the same line | `keyword argument 'xpos' is incompatible with 'xalign'` |
| C11 | duplicate `label`, `screen`, `define`, `default`, `image`, `transform` | duplicate `default` → `is being given a default a second time`; duplicate `define` silently keeps the last one |
| C12 | a function defined in `init python` shares its name with a `default`/`define` variable | `TypeError: 'str' object is not callable` (the store is one namespace) |
| C13 | a screen property that landed inside an unclosed `(`/`[` (usually appended after a multi-line expression) | `expected statement` at a line that looks fine |
| C14 | `init -N` block uses a `define`/`default` that has no priority | `NameError` — plain `define` runs at init 0, i.e. **after** every `init -N` |
| C15 | module-level assignment to a reserved Ren'Py name (`config`, `renpy`, `store`, `persistent`, …) inside `init python` | anything from silent breakage to `AttributeError` far away from the cause |
| C16 | `$ x = 1` inside a `python:` block | `SyntaxError: invalid syntax` — `$` is statement sugar, not Python |

### Notes on a few of them

**C03 with data tables.** Many games keep an event table like `EVENTS = {"day3": {"label": "ev_day3"}}` and later do `renpy.jump(ev["label"])`. `renpy lint` cannot see those strings. `renpy-check` scans dict literals for keys named `label` / `loop` (configurable with `--label-keys`) and checks that every string value is a real label.

**C06 and C14 (init order).** Ren'Py runs all `init` blocks sorted by priority, and for equal priority, by file name. A `define X = 1` with no explicit priority is `init 0`, so `init -5 python:` that reads `X` fails on a clean start even though it works after a reload. These two checks are the reason this tool exists.

**C11.** Ren'Py does not complain about two `define e = …` in different files: the last one loaded wins, and you spend an afternoon wondering why your Character's colour is wrong. It *does* complain about two `default`s.

## Use it from CI / pre-commit

```yaml
# .github/workflows/renpy-check.yml
- run: python renpy_check.py game --lang en
```

```sh
# .git/hooks/pre-commit
python renpy_check.py game --quiet || exit 1
```

## Use it with an AI coding agent

`skills/renpy-check/SKILL.md` is a short, tool-neutral instruction file (the open [Agent Skills](https://agentskills.io) format: YAML front matter + Markdown) that tells any AI coding agent when to run this checker on a Ren'Py project and how to read its output. It works with whatever agent you use:

| agent | where to put it |
|-------|-----------------|
| Claude Code / Cowork | copy `skills/renpy-check/` into `.claude/skills/` (project) or `~/.claude/skills/` (global) |
| OpenAI Codex CLI | copy it into `.codex/skills/` (project) or `~/.codex/skills/` (global), or paste the body into `AGENTS.md` |
| Cursor | paste the body into a rule under `.cursor/rules/renpy-check.mdc` |
| GitHub Copilot | paste the body into `.github/copilot-instructions.md` |
| Gemini CLI / others | paste the body into `GEMINI.md` / the agent's project instruction file |

The one-line version, if you just want it in an `AGENTS.md`: *"After editing `.rpy` files, run `python renpy_check.py game --lang en --quiet` and fix every `[X]` line before reporting done."*

## Tests

```
python tests/run_tests.py
```

`tests/samples/` holds one deliberately broken `.rpy` file per check plus one clean file; the runner asserts that each sample triggers exactly its own check.

## Scope and honesty

* This is a **text-level** checker. It does not parse Ren'Py fully, so it can miss things and, rarely, flag something legitimate. Use `--skip` for a check that gets in your way, and please open an issue with a snippet so the pattern can be fixed.
* It complements `renpy lint`; it does not replace it. Run both.
* Tested against Ren'Py 8.x projects (Python 3). Older 7.x projects should mostly work.

## Contributing

Found a crash that lint did not catch? Open an issue with the traceback and the minimal `.rpy` that reproduces it. New checks follow the pattern of the existing ones: one function, one message in `MSG`, one `bad_Cxx_*.rpy` sample.

## License

MIT © yurthon

---

## 中文说明

`renpy-check` 是一个给 Ren'Py 项目用的静态检查脚本。**它抓的都是 `renpy lint` 不报、但真机运行到那一行就崩的错。** 这里的每一条检查都对应一次真实发生过的崩溃。

单文件、零依赖、Python 3.8 以上就能跑，不需要装 Ren'Py SDK。把 `renpy_check.py` 丢进项目根目录：

```
python renpy_check.py game            # 扫 game/ 文件夹
python renpy_check.py . --lang zh     # 只显示中文报错
python renpy_check.py game --only C08,C11
python renpy_check.py game --skip C06
```

退出码 0＝全绿，1＝有问题。

### 检查项一览

| 编号 | 抓什么 | 不抓的话真机会报 |
|------|--------|------------------|
| C01 | 文件截断／坏编码／含 NUL 字节 | `UnicodeDecodeError` |
| C02 | 冒号结尾的行下面没有缩进内容（空块） | `expected a non-empty block` |
| C03 | `jump`/`call`/`Jump()`/`call screen` 的目标不存在；**写在字典里的 label 字符串**（`{"label": "ev_x"}`）指向不存在的 label | `The label ev_x does not exist.`——而且要到真正走到那个分支才报 |
| C04 | 台词里的单个 `%` | `ValueError: unsupported format character`（台词会过一遍 `%` 替换） |
| C05 | screen 语言缩进错位：上一行没开块，这一行却缩进更深 | `Line is indented, but the preceding statement does not expect a block.` |
| C06 | `init python`（优先级 ≤ 0）在模块层直接用了**另一个文件**里的 `define`/`default` | `NameError`——同优先级 init 块按文件名顺序执行 |
| C07 | 说话人不是已定义的 Character（打错名字） | `Sayer 'ee' is not a function or string.` |
| C08 | 顶层 `define`/`default` 的表达式编译不过 | `SyntaxError` |
| C09 | screen 属性里用反斜杠续行 | `expected statement` |
| C10 | 同一行同时写 `xalign` 和 `xpos`（或 y／align+pos） | `keyword argument 'xpos' is incompatible with 'xalign'` |
| C11 | 重复的 `label`/`screen`/`define`/`default`/`image`/`transform` | 重复 `default` 报 `is being given a default a second time`；重复 `define` 不报错、静默取最后一个 |
| C12 | `init python` 里定义的函数和某个 `default`/`define` 变量同名 | `'str' object is not callable`（store 是同一个命名空间） |
| C13 | screen 属性掉进了没闭合的括号里（多行表达式后面接属性最常见） | 在看起来没问题的一行报 `expected statement` |
| C14 | `init -N` 块里用了没写优先级的 `define`/`default` | `NameError`——普通 `define` 是 init 0，在所有 `init -N` **之后**才执行 |
| C15 | `init python` 里在模块层给 `config`/`renpy`/`store`/`persistent` 这类保留名赋值 | 各种离原因很远的诡异报错 |
| C16 | `python:` 块里面写 `$ x = 1` | `SyntaxError: invalid syntax`——`$` 是 Ren'Py 语句糖，不是 Python |

### 几条值得多说两句

**C03 与数据表。** 很多养成／事件驱动的游戏会把事件写成表：`EVENTS = {"day3": {"label": "ev_day3"}}`，之后 `renpy.jump(ev["label"])`。lint 看不见这些字符串。本工具会扫字典字面量里 key 为 `label`/`loop`（可用 `--label-keys` 加）的字符串值，逐个核对 label 是否真的存在。

**C06 / C14（init 顺序）。** Ren'Py 把所有 `init` 块按优先级排序，同优先级按文件名。没写优先级的 `define X = 1` 是 `init 0`，所以 `init -5 python:` 里读 `X` 会在冷启动时炸——但 reload 之后又好了，特别迷惑。这两条是这个工具诞生的原因。

**C11。** 两个文件里各写一个 `define e = …`，Ren'Py 不会报错，后加载的赢；然后你会花一下午纳闷角色颜色为什么不对。`default` 重复它倒是会报。

### 配合 AI 编程助手

`skills/renpy-check/SKILL.md` 是一份不绑定任何家的说明文件（开放的 [Agent Skills](https://agentskills.io) 格式：YAML 头＋Markdown），告诉 AI 编程助手什么时候跑这个检查、怎么读输出。用哪个都行：Claude Code 放 `.claude/skills/`，Codex 放 `.codex/skills/` 或贴进 `AGENTS.md`，Cursor 贴进 `.cursor/rules/`，Copilot 贴进 `.github/copilot-instructions.md`。懒人版一句话写进 `AGENTS.md`：「改完 .rpy 文件后跑 `python renpy_check.py game --quiet`，把每条 `[X]` 修掉再说做完了。」

### 范围说明

纯文本级检查，没有完整解析 Ren'Py 语法，所以会漏、偶尔也会误报。误报请用 `--skip`，并欢迎开 issue 贴片段。它是 `renpy lint` 的补充，不是替代，两个都跑。
