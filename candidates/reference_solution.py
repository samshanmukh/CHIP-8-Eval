"""A correct candidate: re-export the reference core verbatim.

This is the "known-good submission" — it should score 100. It exists to prove
the grader gives a perfect score to a correct emulator (the analogue of running
Mesen2 against its own goldens in GBA Eval).
"""
import os
import sys

# The grader loads this file by path, so make the repo root importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reference.chip8_ref import Chip8  # noqa: E402,F401  (re-exported)
