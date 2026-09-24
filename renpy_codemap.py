#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
renpy-codemap — scan a Ren'Py project and write one searchable HTML page: "where is everything".
renpy-codemap — 扫一遍 Ren'Py 项目，生成一张可搜索的 HTML「东西都在哪」。

Usage / 用法:
    python renpy_codemap.py path/to/game                 # writes codemap.html next to game/
    python renpy_codemap.py path/to/project -o map.html  # choose the output file
    python renpy_codemap.py game --lang zh               # page text in Chinese (en / zh)
    python renpy_codemap.py game --title "My VN"

What the page shows:
    · every .rpy file: line count, its first comment line, labels, screens, define/default names
    · every label: where it is, who jumps/calls it, and whether it is only reached by falling through
    · labels nobody references  (candidates for dead code — or for a typo somewhere else)
    · every screen: where it is, who shows/calls/uses it
    · one search box that filters all of the above at once

Tip: a comment line  `# keywords: shop haggle bargain`  (or `# 关键词：讨价 还价`) near the top of a file
adds those words to that file's search text without showing them on the page.

Zero dependencies, Python 3.8+.  Author: yurthon · License: MIT · https://github.com/yurthon/renpy-check
"""
import argparse
import datetime
import html
import os
import re
import sys

__version__ = "0.2.0"

UI = {
    "en": dict(title="Code map", sub="{files} files · {lines:,} lines · {labels} labels · {screens} screens · generated {date}",
               search="search anything: file, label, screen, constant, keyword…",
               files="Files", labels="Labels", orphans="Labels nobody references", screens="Screens",
               lines="lines", callers="reached from", none="nobody", fall="fall-through from", big="big",
               orphan_note="Not jumped to, called, or named as a string anywhere. Either dead code or a typo in the caller. `start`, engine labels, and labels that look like they are built from a string prefix (\"ev_day_\" + key) are excluded.",
               shown="shown / used by", consts="define/default", nothing="nothing matches", count="{n} shown", dyn="probably built from"),
    "zh": dict(title="代码地图", sub="{files} 个文件 · {lines:,} 行 · {labels} 个 label · {screens} 个 screen · 生成于 {date}",
               search="搜什么都行：文件名、label、screen、常量、关键词…",
               files="全部文件", labels="全部 label", orphans="没人引用的 label", screens="全部 screen",
               lines="行", callers="从哪进来", none="没人", fall="落穿自", big="大文件",
               orphan_note="全库没有任何 jump／call／字符串提到它。要么是死代码，要么是调用它的地方写错了名字。`start`、引擎自己用的 label、以及看起来是用字符串前缀拼出来的（\"ev_day_\" + key）不算。",
               shown="谁显示／调用", consts="define/default", nothing="没有匹配", count="显示 {n} 条", dyn="大概是拼出来的："),
}
ENGINE_LABELS = {"start", "splashscreen", "before_main_menu", "main_menu", "after_load", "quit", "_start",
                 "hide_windows", "main_menu_screen", "after_warp"}


def walk_rpy(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        out.extend(os.path.join(dp, f) for f in fns if f.endswith(".rpy"))
    return sorted(out)


def esc(s):
    return html.escape(s, quote=True)


def strip_comment(s):
    out, q = [], None
    for ch in s:
        if q:
            if ch == q:
                q = None
            out.append(ch)
        elif ch in "\"'":
            q = ch; out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


class File:
    def __init__(self, path, root):
        self.path = path
        self.rel = os.path.relpath(path, root).replace(os.sep, "/")
        raw = open(path, "rb").read().decode("utf-8", errors="replace")
        self.lines = raw.split("\n")
        self.n = len(self.lines)
        self.labels, self.screens, self.consts = [], [], []
        self.header, self.keywords = "", ""
        for i, ln in enumerate(self.lines):
            if ln[:1] in (" ", "\t") or ln.lstrip().startswith("#"):
                continue
            m = re.match(r"^label\s+([\w.]+)", ln)
            if m:
                self.labels.append((m.group(1), i + 1)); continue
            m = re.match(r"^screen\s+(\w+)", ln)
            if m:
                self.screens.append((m.group(1), i + 1)); continue
            m = re.match(r"^(?:define|default)\s+(?:-?\d+\s+)?([\w.]+)", ln)
            if m:
                self.consts.append(m.group(1))
        for ln in self.lines[:15]:
            s = ln.strip()
            if s.startswith("#"):
                s = s.lstrip("#").strip()
                if s and not set(s) <= set("=-*~ "):
                    self.header = s; break
            elif s:
                break
        for ln in self.lines[:40]:
            s = ln.lstrip("#").strip()
            m = re.match(r"^(?:keywords?|关键词)\s*[:：]\s*(.+)$", s, re.I)
            if m:
                self.keywords = m.group(1).strip(); break


def scan(root):
    files = [File(p, root) for p in walk_rpy(root)]
    where_label, where_screen = {}, {}
    for f in files:
        for name, ln in f.labels:
            if name.startswith("."):
                continue
            where_label.setdefault(name, (f.rel, ln))
        for name, ln in f.screens:
            where_screen.setdefault(name, (f.rel, ln))
    callers = {k: [] for k in where_label}
    fall = {}
    shown = {k: [] for k in where_screen}
    strings = {}
    for f in files:
        prev_label, prev_terminated = None, True
        for i, ln in enumerate(f.lines):
            code = strip_comment(ln)
            st = code.strip()
            m = re.match(r"^label\s+([\w.]+)", ln)
            if m and not m.group(1).startswith("."):
                if prev_label and not prev_terminated:
                    fall[m.group(1)] = prev_label
                prev_label, prev_terminated = m.group(1), False
            elif st and ln[:1] not in (" ", "\t"):
                prev_label = None
            if st and ln[:1] in (" ", "\t") and prev_label:
                prev_terminated = bool(re.match(r"^(return\b|jump\b|call\s+screen\b|\$\s*renpy\.(jump|full_restart)\b)", st))
            for m in re.finditer(r"\b(?:jump|call)\s+([A-Za-z_]\w*)", code):
                t = m.group(1)
                if t in callers and t != "screen" and t != "expression":
                    callers[t].append((f.rel, i + 1))
            for m in re.finditer(r"\b(?:Jump|Call|renpy\.jump|renpy\.call)\(\s*['\"]([\w.]+)['\"]", code):
                if m.group(1) in callers:
                    callers[m.group(1)].append((f.rel, i + 1))
            for m in re.finditer(r"\b(?:show|call|hide)\s+screen\s+(\w+)|\buse\s+(\w+)|\b(?:Show|ShowMenu|Hide|ShowTransient|ToggleScreen|renpy\.show_screen|renpy\.call_screen)\(\s*['\"](\w+)['\"]", code):
                t = m.group(1) or m.group(2) or m.group(3)
                if t in shown:
                    shown[t].append((f.rel, i + 1))
            for m in re.finditer(r"['\"]([A-Za-z_]\w*)['\"]", code):
                strings.setdefault(m.group(1), 0)
                strings[m.group(1)] += 1
    # a string literal like "ev_day_" suggests labels are built by concatenation: don't call those orphans
    prefixes = tuple(p for p in strings if p.endswith("_") and len(p) > 3)
    dynamic = {}
    orphans = []
    for k in where_label:
        if callers[k] or k in fall or k in ENGINE_LABELS or strings.get(k):
            continue
        hit = [p for p in prefixes if k.startswith(p)]
        if hit:
            dynamic[k] = max(hit, key=len)
        else:
            orphans.append(k)
    return files, where_label, callers, fall, orphans, where_screen, shown, dynamic


CSS = """
:root{--bg:#f7f5f0;--fg:#1d1a16;--mut:#6b6459;--card:#fff;--line:#e3ded5;--acc:#b6772a;--hit:#fff3d6}
@media(prefers-color-scheme:dark){:root{--bg:#17150f;--fg:#efe9dd;--mut:#9a9184;--card:#211e17;--line:#3a3529;--acc:#e0a75a;--hit:#3a2f18}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,"Segoe UI","PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 80px}h1{font-size:26px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 16px}
#q{width:100%;padding:12px 14px;font-size:16px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--fg);position:sticky;top:8px;z-index:2}
#cnt{color:var(--mut);font-size:13px;margin:6px 2px 18px}
h2{font-size:18px;margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.note{color:var(--mut);font-size:13px;margin:-4px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:6px 0}
summary{cursor:pointer;display:flex;gap:10px;flex-wrap:wrap;align-items:baseline}
.fn{font-weight:600}.ln{color:var(--mut);font-size:13px}.hd{color:var(--mut);font-size:13px;flex:1 1 100%}
.tag{font-size:11px;padding:1px 6px;border:1px solid var(--acc);color:var(--acc);border-radius:99px}
.body{margin-top:8px;font-size:14px}.body b{color:var(--acc);margin-right:6px}
.row{display:grid;grid-template-columns:minmax(160px,1fr) minmax(140px,1fr) 2fr;gap:12px;padding:6px 12px;border-bottom:1px solid var(--line);font-size:14px}
.row:last-child{border-bottom:0}.row .k{font-weight:600}.row .f{color:var(--mut)}.row .c{color:var(--mut)}
code{font:13px ui-monospace,Menlo,Consolas,monospace;background:var(--hit);padding:1px 4px;border-radius:4px}
.hide{display:none}.empty{color:var(--mut);padding:8px 12px}
@media(max-width:640px){.row{grid-template-columns:1fr}}
"""
JS = """
const q=document.getElementById('q'),items=[...document.querySelectorAll('[data-s]')],cnt=document.getElementById('cnt');
function run(){const v=q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);let n=0;
for(const el of items){const s=el.dataset.s;const ok=v.every(w=>s.includes(w));el.classList.toggle('hide',!ok);if(ok)n++;
if(ok&&v.length&&el.tagName==='DETAILS')el.open=true;}
cnt.textContent=COUNT.replace('{n}',n);
for(const sec of document.querySelectorAll('section')){const any=[...sec.querySelectorAll('[data-s]')].some(e=>!e.classList.contains('hide'));sec.querySelector('.empty').classList.toggle('hide',any);}}
q.addEventListener('input',run);run();
try{const h=location.hash.slice(1);if(h){q.value=decodeURIComponent(h);run();}}catch(e){}
"""


def render(root, files, where_label, callers, fall, orphans, where_screen, shown, dynamic, lang, title):
    T = UI[lang]
    tot_lines = sum(f.n for f in files)
    out = ["<!doctype html><html lang=%s><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           % ("zh" if lang == "zh" else "en"),
           "<title>%s · %s</title><style>%s</style></head><body><main>" % (esc(title), esc(T["title"]), CSS),
           "<h1>%s · %s</h1><p class=sub>%s</p>" % (esc(title), esc(T["title"]),
                                                   esc(T["sub"].format(files=len(files), lines=tot_lines, labels=len(where_label),
                                                                       screens=len(where_screen), date=datetime.date.today().isoformat()))),
           "<input id=q placeholder='%s' autofocus><div id=cnt></div>" % esc(T["search"])]

    def link(f, ln):
        return "<span class=f>%s:%d</span>" % (esc(f), ln)

    # files
    out.append("<section><h2>%s</h2>" % esc(T["files"]))
    for f in sorted(files, key=lambda x: -x.n):
        labs = [n for n, _ in f.labels]
        scrs = [n for n, _ in f.screens]
        search = " ".join([f.rel, f.header, f.keywords] + labs + scrs + f.consts).lower()
        parts = []
        if labs:
            parts.append("<b>label</b>" + esc(", ".join(labs)))
        if scrs:
            parts.append("<b>screen</b>" + esc(", ".join(scrs)))
        if f.consts:
            more = " … (%d)" % len(f.consts) if len(f.consts) > 80 else ""
            parts.append("<b>%s</b>%s%s" % (esc(T["consts"]), esc(", ".join(f.consts[:80])), more))
        big = " <span class=tag>%s</span>" % esc(T["big"]) if f.n >= 1000 else ""
        out.append("<details class=card data-s=\"%s\"><summary><span class=fn>%s</span><span class=ln>%d %s</span>%s"
                   "<span class=hd>%s</span></summary><div class=body>%s</div></details>"
                   % (esc(search), esc(f.rel), f.n, esc(T["lines"]), big, esc(f.header), "<br>".join(parts) or "—"))
    out.append("<div class='empty hide'>%s</div></section>" % esc(T["nothing"]))

    # orphans
    out.append("<section><h2>%s</h2><p class=note>%s</p><div class=card>" % (esc(T["orphans"]), esc(T["orphan_note"])))
    for k in sorted(orphans):
        f, ln = where_label[k]
        out.append("<div class=row data-s=\"%s\"><span class=k>%s</span>%s<span class=c></span></div>"
                   % (esc((k + " " + f).lower()), esc(k), link(f, ln)))
    out.append("<div class='empty hide'>%s</div></div></section>" % esc(T["nothing"]))

    # labels
    out.append("<section><h2>%s</h2><div class=card>" % esc(T["labels"]))
    for k in sorted(where_label):
        f, ln = where_label[k]
        cs = callers[k]
        c = ", ".join("%s:%d" % (a, b) for a, b in cs[:8]) + (" … (%d)" % len(cs) if len(cs) > 8 else "")
        bits = []
        if cs:
            bits.append("%s %s" % (esc(T["callers"]), esc(c)))
        if k in fall:
            bits.append("<span class=tag>%s %s</span>" % (esc(T["fall"]), esc(fall[k])))
        if k in dynamic:
            bits.append("<span class=tag>%s \"%s\" + …</span>" % (esc(T["dyn"]), esc(dynamic[k])))
        if not bits:
            bits.append(esc(T["callers"]) + " " + esc(T["none"]))
        out.append("<div class=row data-s=\"%s\"><span class=k>%s</span>%s<span class=c>%s</span></div>"
                   % (esc((k + " " + f + " " + " ".join(a for a, _ in cs)).lower()), esc(k), link(f, ln), " · ".join(bits)))
    out.append("<div class='empty hide'>%s</div></div></section>" % esc(T["nothing"]))

    # screens
    out.append("<section><h2>%s</h2><div class=card>" % esc(T["screens"]))
    for k in sorted(where_screen):
        f, ln = where_screen[k]
        ss = shown[k]
        c = ", ".join("%s:%d" % (a, b) for a, b in ss[:8]) + (" … (%d)" % len(ss) if len(ss) > 8 else "")
        out.append("<div class=row data-s=\"%s\"><span class=k>%s</span>%s<span class=c>%s %s</span></div>"
                   % (esc((k + " " + f + " " + " ".join(a for a, _ in ss)).lower()), esc(k), link(f, ln),
                      esc(T["shown"]), esc(c) if ss else esc(T["none"])))
    out.append("<div class='empty hide'>%s</div></div></section>" % esc(T["nothing"]))

    out.append("<script>const COUNT=%r;%s</script></main></body></html>" % (T["count"], JS))
    return "\n".join(out)


def find_game_dir(path):
    path = os.path.abspath(path)
    if os.path.isdir(os.path.join(path, "game")) and os.path.basename(path) != "game":
        if not [f for f in os.listdir(path) if f.endswith(".rpy")]:
            return os.path.join(path, "game")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="scan a Ren'Py project into one searchable HTML code map")
    ap.add_argument("path", nargs="?", default=".", help="game/ folder or project root")
    ap.add_argument("-o", "--out", default="", help="output .html (default: codemap.html next to game/)")
    ap.add_argument("--lang", choices=["en", "zh"], default="en")
    ap.add_argument("--title", default="", help="page title (default: project folder name)")
    ap.add_argument("--version", action="version", version="renpy-codemap " + __version__)
    opts = ap.parse_args(argv)
    root = find_game_dir(opts.path)
    files, where_label, callers, fall, orphans, where_screen, shown, dynamic = scan(root)
    if not files:
        print("no .rpy files under", root); return 2
    proj = os.path.dirname(root) if os.path.basename(root) == "game" else root
    title = opts.title or os.path.basename(proj.rstrip(os.sep)) or "project"
    out = opts.out or os.path.join(proj, "codemap.html")
    page = render(root, files, where_label, callers, fall, orphans, where_screen, shown, dynamic, opts.lang, title)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("wrote %s  (%d files · %d labels · %d screens · %d labels nobody references)"
          % (out, len(files), len(where_label), len(where_screen), len(orphans)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
