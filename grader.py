"""Black-box behavioral grader for CHIP-8 Eval.

Usage:
    python3 grader.py candidates/reference_solution.py
    python3 grader.py candidates/buggy_solution.py [--ascii ROM_NAME]

The grader NEVER reads candidate source. It importlib-loads the candidate's
Chip8 class, runs each test ROM for its fixed cycle budget, hashes the resulting
framebuffer, and compares against golden.json. This mirrors GBA Eval's black-box
grading against a reference emulator: we judge observable behavior only.

A candidate exception on any ROM is recorded as a FAIL for that ROM, not a
grader crash — a broken emulator should score low, not abort the run.

Output: per-ROM PASS/FAIL, per-category subtotals, and a final weighted
SCORE/100.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys

from roms import ROMS

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_PATH = os.path.join(HERE, "golden.json")

WIDTH, HEIGHT = 64, 32


def load_candidate(path):
    """Import a candidate module by file path and return its Chip8 class."""
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "Chip8"):
        raise AttributeError(f"{path} does not define a Chip8 class")
    return module.Chip8


def ascii_fb(fb):
    """Render a 2048-byte framebuffer as ASCII for debugging."""
    lines = []
    for row in range(HEIGHT):
        cells = fb[row * WIDTH:(row + 1) * WIDTH]
        lines.append("".join("█" if px else "·" for px in cells))
    return "\n".join(lines)


def run_candidate(Chip8, rom, cycles):
    """Run a candidate for `cycles` steps; return (framebuffer_or_None, error)."""
    try:
        c = Chip8()
        c.load(rom)
        for _ in range(cycles):
            c.step()
        fb = c.framebuffer()
        if not isinstance(fb, (bytes, bytearray)) or len(fb) != 2048:
            return None, f"framebuffer() returned {type(fb).__name__} of bad size"
        return bytes(fb), None
    except Exception as e:  # candidate bug -> failed test, not grader crash
        return None, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser(description="CHIP-8 Eval grader")
    ap.add_argument("candidate", help="path to candidate .py defining class Chip8")
    ap.add_argument("--ascii", metavar="ROM",
                    help="also render this ROM's framebuffer as ASCII")
    args = ap.parse_args()

    with open(GOLDEN_PATH) as f:
        golden = json.load(f)

    Chip8 = load_candidate(args.candidate)

    # category -> [earned_weight, total_weight, passed, total]
    cats = {}
    total_earned = total_weight = 0
    print(f"Grading {args.candidate}\n")
    print(f"{'ROM':18s} {'CATEGORY':12s} {'W':>2s}  RESULT")
    print("-" * 48)

    for name, (rom, cycles, category, weight) in ROMS.items():
        g = golden.get(name)
        if g is None:
            print(f"{name:18s} {category:12s} {weight:>2d}  SKIP (no golden)")
            continue

        fb, err = run_candidate(Chip8, rom, cycles)
        passed = fb is not None and hashlib.sha256(fb).hexdigest() == g["hash"]

        c = cats.setdefault(category, [0, 0, 0, 0])
        c[1] += weight
        c[3] += 1
        total_weight += weight
        if passed:
            c[0] += weight
            c[2] += 1
            total_earned += weight
            status = "PASS"
        else:
            status = "FAIL" + (f"  [{err}]" if err else "")
        print(f"{name:18s} {category:12s} {weight:>2d}  {status}")

    print("-" * 48)
    print("Category subtotals:")
    for category in sorted(cats):
        earned, wt, passed, total = cats[category]
        pct = 100.0 * earned / wt if wt else 0.0
        print(f"  {category:12s} {passed}/{total} ROMs  "
              f"{earned}/{wt} weight  ({pct:5.1f}%)")

    score = 100.0 * total_earned / total_weight if total_weight else 0.0
    print("-" * 48)
    print(f"SCORE: {score:.1f}/100  ({total_earned}/{total_weight} weight)")

    if args.ascii:
        name = args.ascii
        if name not in ROMS:
            print(f"\n[--ascii] unknown ROM '{name}'", file=sys.stderr)
        else:
            rom, cycles, _, _ = ROMS[name]
            fb, err = run_candidate(Chip8, rom, cycles)
            print(f"\nFramebuffer for '{name}':")
            if fb is None:
                print(f"  (candidate errored: {err})")
            else:
                print(ascii_fb(fb))


if __name__ == "__main__":
    main()
