#!/usr/bin/env python3
"""Each bad_CXX_*.rpy sample must trigger check CXX (and only that check); good.rpy must be clean.
Run:  python tests/run_tests.py"""
import io, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
CHECKER = os.path.join(os.path.dirname(HERE), "renpy_check.py")


def run(files):
    tmp = tempfile.mkdtemp(prefix="rc_")
    game = os.path.join(tmp, "game"); os.makedirs(game)
    for f in files:
        shutil.copy(os.path.join(SAMPLES, f), game)
    p = subprocess.run([sys.executable, CHECKER, game, "--lang", "en", "--quiet"],
                       capture_output=True, text=True, encoding="utf-8")
    shutil.rmtree(tmp)
    return p.returncode, p.stdout + p.stderr


def main():
    fails = 0
    samples = sorted(os.listdir(SAMPLES))
    # 1) the clean file must be clean
    rc, out = run(["good.rpy"])
    if rc != 0:
        print("FAIL good.rpy should be clean:\n" + out); fails += 1
    else:
        print("ok   good.rpy is clean")
    # 2) each bad sample must fire its own check
    groups = {}
    for f in samples:
        m = re.match(r"bad_(C\d\d[a-z]?)_", f)
        if m:
            groups.setdefault(m.group(1), []).append(f)
    for code, files in sorted(groups.items()):
        rc, out = run(files + ["good.rpy"])
        codes = set(re.findall(r"^\[X\] (C\d\d)", out, re.M))
        want = code[:3]
        if rc != 1 or want not in codes:
            print("FAIL %s not caught by %s (got %s)\n%s" % (files, want, sorted(codes), out)); fails += 1
        elif codes != {want}:
            print("FAIL %s also triggered %s (expected only %s)\n%s" % (files, sorted(codes - {want}), want, out)); fails += 1
        else:
            print("ok   %-5s <- %s" % (want, ", ".join(files)))
    print("=" * 40)
    print("ALL OK" if not fails else "%d FAILURE(S)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
