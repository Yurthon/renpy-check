#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
renpy-check — static checks for Ren'Py projects that `renpy lint` does not do.
renpy-check — 给 Ren'Py 项目做的静态检查，专抓 `renpy lint` 抓不到、真机才崩的坑。

Usage / 用法:
    python renpy_check.py path/to/your/game            # scan a game/ folder
    python renpy_check.py path/to/project              # a project root containing game/ also works
    python renpy_check.py game --lang en               # messages in English only (zh / both)
    python renpy_check.py game --only C08,C11          # run a subset
    python renpy_check.py game --skip C06              # skip a check
    python renpy_check.py game --label-keys label,loop # extra dict keys whose string values name labels
    python renpy_check.py game --with C17            # also report label fall-through (opt-in)

Exit code 0 = clean, 1 = problems found.  Zero dependencies, Python 3.8+.
Every check below exists because a real game crashed on a real machine once.
下面每一条检查都对应一次真实的崩溃。

Author: yurthon · License: MIT · https://github.com/yurthon/renpy-check
"""
import argparse
import os
import re
import sys

__version__ = "0.2.0"

# ────────────────────────────────────────────────────────────────────────────
# messages / 报错文案
# ────────────────────────────────────────────────────────────────────────────
MSG = {
    "C01": ("file is truncated or not valid UTF-8 (or contains NUL bytes)",
            "文件截断／坏编码（或含 NUL 字节）"),
    "C02": ("empty block: a line ending with ':' is not followed by a deeper-indented line",
            "空块：冒号结尾的那一行下面没有更深缩进的内容"),
    "C03": ("jump/call target does not exist",
            "jump/call 的目标 label 不存在"),
    "C03s": ("`call screen` target screen does not exist",
             "`call screen` 的目标 screen 不存在"),
    "C03t": ("label named in a data table (string) does not exist",
             "表里点名的 label（字符串）不存在"),
    "C04": ("bare % in a say line — Ren'Py treats % as a format code (write %% for a literal percent)",
            "台词里有裸 %——Ren'Py 会当格式化符处理，字面的百分号要写成 %%"),
    "C05": ("screen indentation: line is indented deeper than the previous one, but the previous line does not open a block",
            "screen 缩进：上一行不是冒号结尾却多缩进了（Ren'Py 报 “does not expect a block”）"),
    "C06": ("init python (priority <= 0) uses a define/default from ANOTHER file at module level — same-priority init blocks run in file-name order, so this may run before that define exists (NameError)",
            "init python（优先级 <=0）在模块级用了【别的文件】的 define/default——同优先级按文件名顺序跑，可能抢在 define 前面（NameError）"),
    "C07": ("speaker is not a defined Character (typo?)",
            "说话人不是已定义的 Character（多半是打错名字）"),
    "C08": ("top-level define/default expression does not compile",
            "顶层 define/default 的表达式语法错（通常是逗号掉进注释里）"),
    "C09": ("backslash line-continuation inside screen properties — screen property values are simple expressions and cannot be continued with \\",
            "screen 属性行用了反斜杠续行——属性值走 simple_expression，不认反斜杠（会崩）"),
    "C10": ("conflicting position properties on one line (xalign vs xpos etc.) — “keyword argument 'xpos' is incompatible with 'xalign'”",
            "同一句里位置属性打架（xalign 和 xpos 之类）——要「右对齐到某个 x」写 xanchor 1.0 xpos …"),
    "C11": ("duplicate definition — Ren'Py silently keeps the LAST define; a duplicate default crashes with “is being given a default a second time”",
            "重名——define 重复会静悄悄地被后面那个盖掉；default 重复开机就崩"),
    "C12": ("a function defined in init python has the same name as a default/define variable — the store is one namespace, the value overwrites the function (“'str' object is not callable”)",
            "init python 里的函数名撞上 default/define 的变量名——store 是同一个命名空间，开局函数就被值盖掉"),
    "C13": ("screen property appears inside an unclosed parenthesis / bracket (usually a property appended to a multi-line expression)",
            "screen 属性被塞进没闭合的括号里（多半是往多行表达式的第一行后面追了属性）"),
    "C14": ("init -N block uses a define/default that has no priority — plain define/default runs at init 0, i.e. AFTER every init -N (NameError)",
            "init -N 用了不带优先级的 define/default——不写数字的 define 跑在 init 0，比所有 init -N 都晚（NameError）"),
    "C15": ("module-level assignment to a Ren'Py reserved name inside init python — this overwrites the engine's global",
            "init python 的模块级把 Ren'Py 保留名当变量用了——会盖掉引擎的全局对象"),
    "C17": ("label falls through into the next label (no jump/return/call screen at the end) — legal, but inserting any label in between later will silently reroute it [opt-in: --with C17]",
            "label 末尾没有 jump/return/call screen，靠「掉下去」进下一个 label——合法，但以后往中间插一个 label 它就会悄悄走错 [选开：--with C17]"),
    "C17i": ("label ends inside an `if` branch with no `else` — when the condition is false it falls through into the next label",
             "label 末尾的 jump/return 在一个没有 else 的 if 里——条件不成立时照样掉进下一个 label"),
    "C16": ("`$ statement` inside a `python:` block — `$` is Ren'Py's marker for 'the rest of this line is Python'; inside a python block you are already in Python, so `$` is a syntax error there",
            "`python:` 块里写了 `$ 语句`——`$` 只能在 Ren'Py 语句层用，块里面是语法错误"),
}

# Ren'Py names that must never be rebound at module level of an init python block
RESERVED = set("""
_ _p _n _m _preferences _window _game_menu_screen _history _history_list
_last_say_who _last_say_what _rollback _skipping _dismiss_pause _confirm_quit
_autosave _version _menu _side_image _in_replay _quit_slot _return _args _kwargs
_tooltip _ignore_action _screenshot_pattern _console
config store renpy persistent preferences gui style layout theme build
achievement updater iap director mouse_visible suppress_overlay
adv nvl narrator name_only centered vcentered extend menu
""".split())

# words that can start a line with a string after them but are NOT speakers
SAY_KEYWORDS = set(("text textbutton add use jump call label scene show hide play stop queue window "
    "nvl pause voice image return extend python init default define screen style transform "
    "vbox hbox frame button imagebutton bar vbar viewport grid side fixed null timer key has "
    "on if elif else while for menu input block parallel contains hotspot hotbar "
    "imagemap drag draggroup mousearea vpgrid at with as expression translate old new "
    "variant background foreground thumb child font sound hover_background idle_background "
    "selected_idle_background insensitive_background left_bar right_bar top_bar bottom_bar "
    "thumb_shadow properties action hovered unhovered alternate tooltip caption").split())

SCREEN_PROPS = ("activate_sound", "hover_sound", "action", "xpos", "ypos", "xalign", "yalign",
                "text_size", "text_color", "background", "sensitive", "style", "tooltip", "xysize",
                "xsize", "ysize", "spacing", "padding")


# ────────────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────────────
def walk_rpy(root):
    """Ren'Py loads game/ recursively, skipping only directories that start with '.'"""
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        out.extend(os.path.join(dp, f) for f in fns if f.endswith(".rpy"))
    return sorted(out)


def strip_strings_comments(s):
    s = re.sub(r'(u|b|r)?"""(?:(?!""").)*"""', "", s)
    s = re.sub(r'(u|b|r)?"(?:[^"\\]|\\.)*"', "", s)
    s = re.sub(r"(u|b|r)?'(?:[^'\\]|\\.)*'", "", s)
    s = re.sub(r"#.*", "", s)
    return s


def paren_depth_map(lines):
    """bracket depth at the START of each line (strings and comments ignored)"""
    out, d = [], 0
    for l in lines:
        out.append(d)
        s = strip_strings_comments(l)
        d += s.count("(") + s.count("[") + s.count("{") - s.count(")") - s.count("]") - s.count("}")
        if d < 0:
            d = 0
    return out


def strip_trailing_comment(s):
    for k, ch in enumerate(s):
        if ch == "#" and s[:k].count('"') % 2 == 0 and s[:k].count("'") % 2 == 0:
            return s[:k]
    return s


class Report:
    def __init__(self, lang):
        self.lang = lang
        self.bad = 0
        self.stats = []

    def hit(self, code, path, line, detail=""):
        self.bad += 1
        en, zh = MSG[code]
        if self.lang == "en":
            msg = en
        elif self.lang == "zh":
            msg = zh
        else:
            msg = en + "  ｜ " + zh
        where = "%s:%d" % (path, line) if line else path
        print("[X] %s %s  %s%s" % (code[:3], where, msg, ("\n      " + detail) if detail else ""))

    def stat(self, s):
        self.stats.append(s)


class Source:
    """all files loaded once"""
    def __init__(self, root):
        self.root = root
        self.files = walk_rpy(root)
        self.text = {}
        self.lines = {}
        for f in self.files:
            try:
                t = open(f, "rb").read().decode("utf-8")
            except UnicodeDecodeError:
                t = open(f, "rb").read().decode("utf-8", errors="replace")
            self.text[f] = t
            self.lines[f] = t.split("\n")

    def rel(self, f):
        return os.path.relpath(f, self.root)


# ────────────────────────────────────────────────────────────────────────────
# checks — each takes (src, rep, opts) and reports through rep.hit()
# ────────────────────────────────────────────────────────────────────────────
def c01_encoding(src, rep, opts):
    for f in src.files:
        raw = open(f, "rb").read()
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            rep.hit("C01", src.rel(f), 0, str(e)); continue
        if "\x00" in t:
            rep.hit("C01", src.rel(f), 0, "NUL byte")


def c02_empty_block(src, rep, opts):
    for f in src.files:
        L = src.lines[f]; dep = paren_depth_map(L)
        for i, ln in enumerate(L):
            st = ln.strip()
            if not st or st.startswith("#") or dep[i] > 0:
                continue
            if st.endswith(":") and not st.startswith('"'):
                ind = len(ln) - len(ln.lstrip())
                for j in range(i + 1, len(L)):
                    nx = L[j]
                    if not nx.strip() or nx.strip().startswith("#"):
                        continue
                    if len(nx) - len(nx.lstrip()) <= ind:
                        rep.hit("C02", src.rel(f), i + 1, st[:80])
                    break


def collect_labels_screens(src):
    labels, screens = set(), set()
    for f in src.files:
        last_top = None
        for ln in src.lines[f]:
            if ln.strip().startswith("#"):
                continue
            m = re.match(r"\s*label\s+([A-Za-z_.]\w*)", ln)
            if m:
                nm = m.group(1)
                if nm.startswith("."):
                    labels.add((last_top or "") + nm)
                else:
                    last_top = nm
                labels.add(nm)
            m = re.match(r"\s*screen\s+([A-Za-z_]\w*)", ln)
            if m:
                screens.add(m.group(1))
    return labels, screens


def c03_jump_targets(src, rep, opts):
    labels, screens = collect_labels_screens(src)
    keys = [k.strip() for k in (opts.label_keys or "").split(",") if k.strip()]
    for f in src.files:
        for i, ln in enumerate(src.lines[f]):
            if ln.strip().startswith("#"):
                continue
            for m in re.finditer(r"\b(?:jump|call)\s+(?!expression\b)(?!screen\b)([A-Za-z_.]\w*)", ln):
                nm = m.group(1)
                if nm.startswith("."):
                    continue          # local label jump — resolved at runtime relative to the enclosing label
                if nm not in labels:
                    rep.hit("C03", src.rel(f), i + 1, "-> " + nm)
            for m in re.finditer(r'\bJump\("([A-Za-z_]\w*)"\)', ln):
                if m.group(1) not in labels:
                    rep.hit("C03", src.rel(f), i + 1, 'Jump("%s")' % m.group(1))
            for m in re.finditer(r"call\s+screen\s+([A-Za-z_]\w*)", ln):
                if m.group(1) not in screens:
                    rep.hit("C03s", src.rel(f), i + 1, "-> " + m.group(1))
            if keys:
                for m in re.finditer(r'"(%s)"\s*:\s*"([A-Za-z_]\w*)"' % "|".join(map(re.escape, keys)), ln):
                    if m.group(2) not in labels:
                        rep.hit("C03t", src.rel(f), i + 1, '"%s": "%s"' % (m.group(1), m.group(2)))
                for m in re.finditer(r'\b(%s)\s*=\s*"([A-Za-z_]\w*)"' % "|".join(map(re.escape, keys)), ln):
                    if m.group(2) not in labels:
                        rep.hit("C03t", src.rel(f), i + 1, '%s="%s"' % (m.group(1), m.group(2)))


def collect_characters(src):
    chars = set()
    for f in src.files:
        for ln in src.lines[f]:
            m = re.match(r'\s*(?:define|default)\s+(?:-?\d+\s+)?([A-Za-z_]\w*)\s*=\s*(?:Character|DynamicCharacter)\b', ln)
            if m:
                chars.add(m.group(1))
    return chars


def c04_bare_percent(src, rep, opts):
    chars = collect_characters(src) | {"narrator", "extend", "centered", "vcentered", "nvl_narrator"}
    say_re = re.compile(r'^\s*(' + "|".join(sorted(map(re.escape, chars))) + r')\s+"')
    for f in src.files:
        for i, ln in enumerate(src.lines[f]):
            if say_re.match(ln) and re.search(r"(?<!%)%(?!%)", ln.split('"', 1)[1]):
                rep.hit("C04", src.rel(f), i + 1, ln.strip()[:80])


def c05_screen_indent(src, rep, opts):
    for f in src.files:
        L = src.lines[f]; dep = paren_depth_map(L)
        inscr, sind, prev = False, -1, None
        for i, raw in enumerate(L):
            st = raw.strip()
            if not st or st.startswith("#"):
                continue
            ind = len(raw) - len(raw.lstrip())
            if re.match(r"^screen\s+\w+.*:", st):
                inscr, sind, prev = True, ind, (i + 1, ind, st); continue
            if inscr and ind <= sind:
                inscr = False
            if not inscr:
                prev = (i + 1, ind, st); continue
            if prev is not None:
                pln, pind, ptxt = prev
                pt2 = strip_trailing_comment(ptxt).rstrip()
                cont = pt2.endswith((",", "(", "[", "{", "\\", "+", "and", "or"))
                isc = dep[i] > 0 or (i > 0 and dep[i - 1] > 0)
                if not isc and ind > pind and not pt2.endswith(":") and not cont:
                    rep.hit("C05", src.rel(f), i + 1, "previous line: " + ptxt[:70])
            prev = (i + 1, ind, st)


def c06_init_order(src, rep, opts):
    defs = {}
    for f in src.files:
        for ln in src.lines[f]:
            m = re.match(r'\s*(?:define|default)\s+(?:-?\d+\s+)?([A-Z]\w*)\s*=', ln)
            if m:
                defs[m.group(1)] = f
    for f in src.files:
        L = src.lines[f]; i = 0
        while i < len(L):
            m = re.match(r'^(\s*)init(\s+(-?\d+))?\s+python\s*:', L[i])
            if not m:
                i += 1; continue
            prio = int(m.group(3)) if m.group(3) else 0
            base = len(m.group(1)); body = None; indef = False; dind = None; j = i + 1
            while j < len(L):
                raw = L[j]
                if not raw.strip() or raw.strip().startswith("#"):
                    j += 1; continue
                ind = len(raw) - len(raw.lstrip())
                if ind <= base:
                    break
                if body is None:
                    body = ind
                st = raw.strip()
                if ind == body and st.startswith(("def ", "class ")):
                    indef = True; dind = ind; j += 1; continue
                if indef and ind <= dind and not st.startswith(("def ", "class ")):
                    indef = False
                if ind == body and prio <= 0 and not st.startswith(("def ", "class ")):
                    for nm in re.findall(r'\b([A-Z]\w*)\b', strip_strings_comments(st)):
                        if nm in defs and defs[nm] != f:
                            rep.hit("C06", src.rel(f), j + 1,
                                    "init %d uses %s (defined in %s)" % (prio, nm, src.rel(defs[nm])))
                j += 1
            i = j


def c07_speaker(src, rep, opts):
    chars = collect_characters(src) | {"narrator", "extend", "centered", "vcentered"}
    say_used = re.compile(r'^(\s*)([a-z]\w*)\s+"')
    for f in src.files:
        inscr, sind = False, -1
        for i, raw in enumerate(src.lines[f]):
            st = raw.strip()
            if not st or st.startswith("#"):
                continue
            ind = len(raw) - len(raw.lstrip())
            if re.match(r"^(?:screen|style|transform|translate)\s+\w+.*:", st):
                inscr, sind = True, ind; continue
            if inscr and ind <= sind:
                inscr = False
            if inscr:
                continue
            m = say_used.match(raw)
            if m:
                w = m.group(2)
                if w not in chars and w not in SAY_KEYWORDS:
                    rep.hit("C07", src.rel(f), i + 1, "-> " + w)


_DHEAD = re.compile(r"^(define|default)\s+(?:-?\d+\s+)?([A-Za-z_][\w.]*)\s*(?:\[[^\]]*\])?\s*\+?=\s*(.*)$")


def _dcnt(s):
    s = strip_strings_comments(s)
    return s.count("(") + s.count("[") + s.count("{") - s.count(")") - s.count("]") - s.count("}")


def c08_define_expr(src, rep, opts):
    tot = 0
    for f in src.files:
        L = src.lines[f]; i = 0
        while i < len(L):
            m = _DHEAD.match(L[i])
            if not m:
                i += 1; continue
            expr = [m.group(3)]; d = _dcnt(m.group(3)); j = i
            while d > 0 and j + 1 < len(L):
                j += 1; expr.append(L[j]); d += _dcnt(L[j])
            tot += 1
            try:
                compile("\n".join(expr), "<define>", "eval")
            except SyntaxError as e:
                rep.hit("C08", src.rel(f), i + 1, "%s: %s  %s" % (m.group(2), e.msg, (e.text or "").strip()[:80]))
            i = j + 1
    rep.stat("C08 compiled %d top-level define/default expressions" % tot)


def c09_screen_backslash(src, rep, opts):
    ok = re.compile(r"^\s*(\$|python\b|if\b|elif\b|while\b|for\b|#)")
    for f in src.files:
        inscr = False
        for i, l in enumerate(src.lines[f]):
            st = l.strip()
            if re.match(r"^screen\s+\w+", l):
                inscr = True; continue
            if l and not l[0].isspace() and not st.startswith("#"):
                inscr = False
            if not inscr or not st:
                continue
            if l.rstrip().endswith("\\") and not ok.match(l):
                rep.hit("C09", src.rel(f), i + 1, st[:90])


def c10_pos_conflict(src, rep, opts):
    pairs = [("xalign", "xpos"), ("yalign", "ypos"), ("xalign", "xanchor"), ("yalign", "yanchor")]
    for f in src.files:
        for i, ln in enumerate(src.lines[f]):
            st = ln.strip()
            if not st or st.startswith("#") or st.startswith("$"):
                continue
            toks = set(re.findall(r"(?<![\w.])(x?y?align|xpos|ypos|xanchor|yanchor)(?=\s)", strip_trailing_comment(st)))
            for a, b in pairs:
                if a in toks and b in toks:
                    rep.hit("C10", src.rel(f), i + 1, "%s + %s" % (a, b))
            if "align" in toks and ("xpos" in toks or "ypos" in toks):
                rep.hit("C10", src.rel(f), i + 1, "align + xpos/ypos")


def c11_duplicates(src, rep, opts):
    seen = {}
    for f in src.files:
        L = src.lines[f]; last_top = None
        for i, ln in enumerate(L):
            m = re.match(r"^(screen|label|default|define)\s+([\w\.]+)", ln)
            if not m:
                continue
            kind, nm = m.group(1), m.group(2)
            if kind in ("define", "default") and re.match(r"^(define|default)\s+-?\d", ln):
                continue          # `define 100 gui.x = ...` is the official override idiom
            if kind == "label":
                if nm.startswith("."):
                    nm = (last_top or "") + nm
                else:
                    last_top = nm
            if kind == "screen":
                nxt = "\n".join(L[i + 1:i + 4])
                if re.search(r'^\s+variant\s+"', nxt, re.M):
                    continue      # same screen name with different `variant` is legal
            key = (kind, nm)
            if key in seen:
                rep.hit("C11", src.rel(f), i + 1, "%s %s already defined at %s" % (kind, nm, seen[key]))
            else:
                seen[key] = "%s:%d" % (src.rel(f), i + 1)
    rep.stat("C11 saw %d screen/label/default/define names" % len(seen))


def c12_func_vs_var(src, rep, opts):
    fn, var = {}, {}
    for f in src.files:
        for i, l in enumerate(src.lines[f], 1):
            m = re.match(r"\s+def\s+([A-Za-z_]\w*)\s*\(", l)
            if m:
                fn.setdefault(m.group(1), []).append("%s:%d" % (src.rel(f), i))
            m2 = re.match(r"(?:default|define)\s+(?:-?\d+\s+)?([A-Za-z_]\w*)\s*=", l)
            if m2:
                var.setdefault(m2.group(1), []).append("%s:%d" % (src.rel(f), i))
    for k in sorted(set(fn) & set(var)):
        rep.hit("C12", var[k][0].rsplit(":", 1)[0], int(var[k][0].rsplit(":", 1)[1]),
                "%s: function at %s, variable at %s" % (k, fn[k][0], var[k][0]))


def _props_in_open_parens(line):
    hit, d, i, n, q = [], 0, 0, len(line), None
    while i < n:
        c = line[i]
        if q:
            if c == "\\":
                i += 2; continue
            if c == q:
                q = None
            i += 1; continue
        if c in "\"'":
            q = c; i += 1; continue
        if c == "#":
            break
        if c in "([{":
            d += 1
        elif c in ")]}":
            d -= 1
        elif d > 0 and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_")):
            for p in SCREEN_PROPS:
                if line.startswith(p, i):
                    nxt = line[i + len(p):i + len(p) + 1]
                    if nxt == " " and line[i + len(p):].lstrip()[:1] not in ("=", ".", "(", ",", ")", "]", "}", ":"):
                        hit.append((p, d)); break
        i += 1
    return hit


def c13_prop_in_parens(src, rep, opts):
    for f in src.files:
        inscr = False
        for i, l in enumerate(src.lines[f]):
            st = l.strip()
            if re.match(r"^screen\s+\w+", l):
                inscr = True; continue
            if l and not l[0].isspace() and not st.startswith("#"):
                inscr = False
            if not inscr or not st or st.startswith("#") or st.startswith("$"):
                continue
            for p, d in _props_in_open_parens(l):
                rep.hit("C13", src.rel(f), i + 1, "%s at bracket depth %d: %s" % (p, d, st[:90]))


def c14_define_priority(src, rep, opts):
    prio = {}
    for f in src.files:
        for i, l in enumerate(src.lines[f], 1):
            m = re.match(r"^(define|default)(?:\s+(-?\d+))?\s+([A-Za-z_]\w*)\s*(\[|=)", l)
            if m and m.group(3) not in RESERVED:
                n = m.group(3); p = int(m.group(2)) if m.group(2) else 0
                if n not in prio or p < prio[n][0]:
                    prio[n] = (p, "%s:%d" % (src.rel(f), i))
    for f in src.files:
        L = src.lines[f]; i = 0
        while i < len(L):
            m = re.match(r"^init\s+(-\d+)\s+python.*:", L[i])
            if not m:
                i += 1; continue
            P = int(m.group(1)); j = i + 1; skip = None
            while j < len(L) and (not L[j].strip() or L[j].startswith((" ", "\t"))):
                s = L[j]
                if s.strip() and not s.strip().startswith("#"):
                    ind = len(s) - len(s.lstrip())
                    if skip is not None and ind > skip:
                        j += 1; continue
                    skip = None
                    if ind == 4:
                        if re.match(r"^\s*(def|class)\s", s):
                            skip = ind
                        else:
                            # only CONSTANT_STYLE names: lowercase words are too often locals / attributes
                            for nm in re.findall(r"(?<![\w.])[A-Z][A-Z_0-9]{2,}\b", strip_strings_comments(s)):
                                if nm in prio and prio[nm][0] > P:
                                    rep.hit("C14", src.rel(f), j + 1,
                                            "init %d uses %s, defined at priority %d (%s) — write `define %d %s = ...`"
                                            % (P, nm, prio[nm][0], prio[nm][1], P - 1, nm))
                j += 1
            i = j


def c15_reserved(src, rep, opts):
    for f in src.files:
        L = src.lines[f]; i = 0
        while i < len(L):
            if not re.match(r"^init(\s+-?\d+)?\s+python.*:", L[i]):
                i += 1; continue
            j = i + 1; skip = None
            while j < len(L) and (not L[j].strip() or L[j].startswith((" ", "\t"))):
                s = L[j]
                if s.strip() and not s.strip().startswith("#"):
                    ind = len(s) - len(s.lstrip())
                    if skip is not None and ind > skip:
                        j += 1; continue
                    skip = None
                    if ind == 4:
                        if re.match(r"^\s*(def|class)\s", s):
                            skip = ind
                        else:
                            m1 = re.match(r"^\s{4}([A-Za-z_]\w*)\s*(?:=[^=]|,\s*[A-Za-z_]\w*\s*=)", s)
                            m2 = re.match(r"^\s{4}for\s+([A-Za-z_]\w*)\s+in\s", s)
                            for mm in (m1, m2):
                                if mm and mm.group(1) in RESERVED:
                                    rep.hit("C15", src.rel(f), j + 1, s.strip()[:90])
                j += 1
            i = j


def c16_dollar_in_python(src, rep, opts):
    for f in src.files:
        stk = []
        for n, ln in enumerate(src.lines[f]):
            st = ln.strip()
            if not st or st.startswith("#"):
                continue
            ind = len(ln) - len(ln.lstrip())
            while stk and ind <= stk[-1][0]:
                stk.pop()
            if any(k == "py" for _, k in stk) and (st.startswith("$ ") or st == "$"):
                rep.hit("C16", src.rel(f), n + 1, st[:90])
            if re.match(r"^(init(\s+-?\d+)?\s+)?python\s*(early\s*)?(hide\s*)?(in\s+\w+\s*)?:\s*(#.*)?$", st):
                stk.append((ind, "py"))
            elif st.endswith(":"):
                stk.append((ind, "other"))


_TERM = re.compile(r"^\s*(return\b|jump\b|call\s+screen\b|\$\s*renpy\.(jump|call_screen|full_restart|quit)\b|pass\b)")


def c17_fallthrough(src, rep, opts):
    """opt-in: label whose body does not end in a terminating statement, immediately followed by another label.
    Local labels (`label .x:`) are skipped as targets: they are meant to be reached by falling through."""
    for f in src.files:
        lines = src.lines[f]
        labs = [(i, m.group(1)) for i, ln in enumerate(lines)
                for m in [re.match(r"^label\s+([\w.]+)", ln)] if m]
        for i, name in labs:
            end = len(lines)
            for j in range(i + 1, len(lines)):
                ln = lines[j]
                if ln.strip() and ln[0] not in " \t" and not ln.lstrip().startswith("#"):
                    end = j; break
            body = [l for l in lines[i + 1:end] if l.strip() and not l.lstrip().startswith("#")]
            if not body:
                continue
            nxt = None
            for j in range(end, len(lines)):
                ln = lines[j]
                m = re.match(r"^label\s+([\w.]+)", ln)
                if m:
                    nxt = m.group(1); break
                if ln.strip() and ln[0] not in " \t" and not ln.lstrip().startswith("#"):
                    break
            if not nxt or nxt.startswith("."):
                continue
            last = body[-1]
            if not _TERM.match(last):
                rep.hit("C17", src.rel(f), i + 1, "%s -> %s   (last line: %s)" % (name, nxt, last.strip()[:60]))
                continue
            base = len(body[0]) - len(body[0].lstrip())
            if len(last) - len(last.lstrip()) > base:
                gov = None
                for l in reversed(body[:-1]):
                    if len(l) - len(l.lstrip()) == base:
                        gov = l.strip(); break
                if gov and re.match(r"(if|elif)\b", gov):
                    has_else = any(len(l) - len(l.lstrip()) == base and l.strip().startswith("else")
                                   for l in body)
                    if not has_else:
                        rep.hit("C17i", src.rel(f), i + 1, "%s -> %s   (guard: %s)" % (name, nxt, gov[:60]))


CHECKS = [
    ("C01", c01_encoding), ("C02", c02_empty_block), ("C03", c03_jump_targets),
    ("C04", c04_bare_percent), ("C05", c05_screen_indent), ("C06", c06_init_order),
    ("C07", c07_speaker), ("C08", c08_define_expr), ("C09", c09_screen_backslash),
    ("C10", c10_pos_conflict), ("C11", c11_duplicates), ("C12", c12_func_vs_var),
    ("C13", c13_prop_in_parens), ("C14", c14_define_priority), ("C15", c15_reserved),
    ("C16", c16_dollar_in_python),
    ("C17", c17_fallthrough),
]
OPT_IN = {"C17"}          # run only with --with C17 or --only C17


def find_game_dir(path):
    path = os.path.abspath(path)
    if os.path.isdir(os.path.join(path, "game")) and not walk_rpy(path):
        return os.path.join(path, "game")
    if os.path.isdir(os.path.join(path, "game")) and os.path.basename(path) != "game":
        # project root: prefer game/ unless the root itself has .rpy files
        if not [f for f in os.listdir(path) if f.endswith(".rpy")]:
            return os.path.join(path, "game")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="static checks for Ren'Py projects that `renpy lint` does not do")
    ap.add_argument("path", nargs="?", default=".", help="game/ folder or project root")
    ap.add_argument("--lang", choices=["en", "zh", "both"], default="both")
    ap.add_argument("--only", default="", help="comma-separated check ids to run, e.g. C08,C11")
    ap.add_argument("--skip", default="", help="comma-separated check ids to skip")
    ap.add_argument("--label-keys", default="label,loop",
                    help="dict keys whose string values name labels (checked by C03); '' to disable")
    ap.add_argument("--with", dest="with_", default="",
                    help="comma-separated opt-in checks to enable, e.g. C17 (label fall-through)")
    ap.add_argument("--quiet", action="store_true", help="only print problems")
    ap.add_argument("--version", action="version", version="renpy-check " + __version__)
    opts = ap.parse_args(argv)

    root = find_game_dir(opts.path)
    src = Source(root)
    if not src.files:
        print("no .rpy files under", root); return 2
    rep = Report(opts.lang)
    only = set(x.strip().upper() for x in opts.only.split(",") if x.strip())
    skip = set(x.strip().upper() for x in opts.skip.split(",") if x.strip())
    with_ = set(x.strip().upper() for x in opts.with_.split(",") if x.strip())
    ran = 0
    for code, fn in CHECKS:
        if (only and code not in only) or code in skip:
            continue
        if code in OPT_IN and not (code in with_ or code in only):
            continue
        fn(src, rep, opts); ran += 1
    if not opts.quiet:
        for s in rep.stats:
            print("    (" + s + ")")
        print("=" * 48)
        print("renpy-check %s · %d files · %d checks" % (__version__, len(src.files), ran))
    if rep.bad == 0:
        print("OK — all green / 全绿" if not opts.quiet else "OK")
        return 0
    print("%d problem(s) found / 共 %d 个问题" % (rep.bad, rep.bad))
    return 1


if __name__ == "__main__":
    sys.exit(main())
