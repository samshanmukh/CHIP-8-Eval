"""Generate golden.json from the reference core.

For each test ROM: load it on the reference CHIP-8, run its cycle budget, hash
the final framebuffer, and record {hash, cycles, category, weight}. This is the
analogue of capturing reference traces from Mesen2 in the GBA Eval — the goldens
are the trusted answer key the grader compares against.
"""
import hashlib
import json
import os

from reference.chip8_ref import Chip8
from roms import ROMS

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_PATH = os.path.join(HERE, "golden.json")


def run_and_hash(rom, cycles):
    c = Chip8()
    c.load(rom)
    for _ in range(cycles):
        c.step()
    fb = c.framebuffer()
    assert len(fb) == 2048, f"framebuffer must be 2048 bytes, got {len(fb)}"
    return hashlib.sha256(fb).hexdigest()


def main():
    golden = {}
    for name, (rom, cycles, category, weight) in ROMS.items():
        h = run_and_hash(rom, cycles)
        golden[name] = {
            "hash": h,
            "cycles": cycles,
            "category": category,
            "weight": weight,
        }
        print(f"{name:18s} {category:12s} w={weight} -> {h[:16]}…")
    with open(GOLDEN_PATH, "w") as f:
        json.dump(golden, f, indent=2, sort_keys=True)
    print(f"\nWrote {len(golden)} goldens to {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
