"""A plausibly-buggy candidate: correct core with two realistic mistakes.

Both bugs are things real CHIP-8 implementations actually get wrong:

  (a) 8XY4 (ADD VX, VY) forgets to set the VF carry flag.
  (b) 8XY6 (SHR) uses the original COSMAC VIP semantics — "VX = VY >> 1" —
      instead of the modern in-place "VX = VX >> 1" this eval pins down.

The grader should give this a PARTIAL score and localize the damage to exactly
two ROMs: `add_carry_vf` (instruction category) and `quirk_shr` (quirk
category). Everything else still passes, demonstrating per-capability
attribution. The point of the eval is that black-box grading pinpoints *which*
behaviors broke without ever reading this source.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reference.chip8_ref import Chip8 as _RefChip8  # noqa: E402


class Chip8(_RefChip8):
    def _exec_8(self, op, x, y, n):
        V = self.V
        if n == 0x4:
            # BUG (a): add without computing the carry into VF.
            V[x] = (V[x] + V[y]) & 0xFF
            # (VF left untouched — should have been set to the carry bit)
            return
        if n == 0x6:
            # BUG (b): COSMAC "shift VY into VX" instead of in-place on VX.
            flag = V[y] & 1
            V[x] = V[y] >> 1
            V[0xF] = flag
            return
        # All other 8XYn opcodes use the correct reference behavior.
        super()._exec_8(op, x, y, n)
