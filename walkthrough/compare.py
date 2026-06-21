"""See what the grader sees: reference vs candidate, side by side.

For each ROM, run it on BOTH the trusted reference and a candidate emulator,
then render their screens next to each other plus a DIFF panel marking every
pixel they disagree on. This is the grader's PASS/FAIL made visual — a FAIL is
literally the moment the two pictures stop matching.

Usage:
    python3 walkthrough/compare.py candidates/buggy_solution.py
        -> shows only the ROMs that DIFFER (the failures), with a summary

    python3 walkthrough/compare.py candidates/buggy_solution.py quirk_shr
        -> shows one specific ROM, even if it passes
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reference.chip8_ref import Chip8 as ReferenceChip8, WIDTH, HEIGHT
from roms import ROMS


def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate", os.path.abspath(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Chip8


def run(CPUClass, rom, cycles):
    cpu = CPUClass()
    cpu.load(rom)
    for _ in range(cycles):
        cpu.step()
    return cpu.framebuffer()


def bbox(fb_a, fb_b):
    """Smallest window containing any lit pixel or any difference, +1 padding."""
    rows, cols = [], []
    for r in range(HEIGHT):
        for c in range(WIDTH):
            i = r * WIDTH + c
            if fb_a[i] or fb_b[i]:
                rows.append(r); cols.append(c)
    if not rows:
        return 0, 6, 0, 16
    r0 = max(0, min(rows) - 1); r1 = min(HEIGHT - 1, max(rows) + 1)
    c0 = max(0, min(cols) - 1); c1 = min(WIDTH - 1, max(cols) + 1)
    return r0, r1, c0, c1


def panel(fb, r0, r1, c0, c1, on="█", off="·"):
    return [ "".join(on if fb[r * WIDTH + c] else off for c in range(c0, c1 + 1))
             for r in range(r0, r1 + 1) ]


def diff_panel(a, b, r0, r1, c0, c1):
    lines = []
    for r in range(r0, r1 + 1):
        line = []
        for c in range(c0, c1 + 1):
            i = r * WIDTH + c
            line.append("X" if a[i] != b[i] else ("·" if not a[i] else " "))
        lines.append("".join(line))
    return lines


def show(name, category, ref_fb, cand_fb):
    r0, r1, c0, c1 = bbox(ref_fb, cand_fb)
    ref = panel(ref_fb, r0, r1, c0, c1)
    cand = panel(cand_fb, r0, r1, c0, c1)
    diff = diff_panel(ref_fb, cand_fb, r0, r1, c0, c1)
    w = c1 - c0 + 1
    passed = ref_fb == cand_fb

    print(f"=== {name}  ({category})  ->  {'PASS' if passed else 'FAIL'} ===")
    print(f"  {'reference'.ljust(w)}   {'candidate'.ljust(w)}   {'diff (X=mismatch)'}")
    for rl, cl, dl in zip(ref, cand, diff):
        print(f"  {rl}   {cl}   {dl}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cand_path = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    Candidate = load_candidate(cand_path)

    print(f"Comparing reference  vs  {cand_path}\n")
    fails = []
    for name, (rom, cycles, category, weight) in ROMS.items():
        if only and name != only:
            continue
        ref_fb = run(ReferenceChip8, rom, cycles)
        try:
            cand_fb = run(Candidate, rom, cycles)
        except Exception as e:
            print(f"=== {name}  ({category})  ->  FAIL (crashed: {type(e).__name__}) ===\n")
            fails.append(name)
            continue
        passed = ref_fb == cand_fb
        if not passed:
            fails.append(name)
        if only or not passed:          # show specific ROM, or all failures
            show(name, category, ref_fb, cand_fb)

    if not only:
        total = len(ROMS)
        print(f"Summary: {total - len(fails)}/{total} ROMs match the reference.")
        if fails:
            print(f"Diverged (the grader fails these): {', '.join(fails)}")
        else:
            print("Every screen matches — this candidate would score 100.")


if __name__ == "__main__":
    main()
