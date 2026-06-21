"""STEP 4 — From emulator to EVAL: golden answers + a black-box grader.

We now have everything an emulator needs. This step builds the thing that makes
this a *grading harness* rather than just an emulator:

    1. A TEST ROM that computes something and DRAWS the answer.
    2. A GOLDEN: run that ROM on the trusted reference, hash the screen, save it.
    3. A GRADER: run a CANDIDATE on the same ROM, hash its screen, compare.
       It never reads the candidate's source — only the 2048-byte framebuffer.

To prove it works we grade two candidates:
    * ReferenceCPU  — correct  -> should PASS
    * BuggyCPU      — the carry-flag bug from Step 2 -> should FAIL

THE TEST ROM is designed so the bug becomes visible:

    LD  V0, 0xFF      V0 = 255
    LD  V1, 0x01      V1 = 1
    ADD V0, V1        V0 = 0, and VF = carry (1 if implemented correctly)
    FX29 VF           point I at the font glyph for VF's value
    LD  V2, 1         x = 1
    LD  V3, 1         y = 1
    DRW V2, V3, 5     draw it
    JP  self          halt

    Correct CPU: VF=1 -> draws the digit "1".
    Buggy CPU:   VF=0 -> draws the digit "0".
    Two different pictures -> two different hashes -> the grader catches it.
"""
import hashlib

PROGRAM_ADDR = 0x200
FONT_ADDR = 0x50
WIDTH, HEIGHT = 64, 32

FONT = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    # (only 0 and 1 are needed for this ROM, but a couple more for safety)
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
]


class ReferenceCPU:
    """The trusted, correct core — our 'Mesen2'."""

    def __init__(self):
        self.mem = bytearray(4096)
        self.V = bytearray(16)
        self.I = 0
        self.pc = PROGRAM_ADDR
        self.display = bytearray(WIDTH * HEIGHT)
        for i, b in enumerate(FONT):
            self.mem[FONT_ADDR + i] = b

    def load(self, rom):
        for i, b in enumerate(rom):
            self.mem[PROGRAM_ADDR + i] = b

    def framebuffer(self):
        return bytes(self.display)

    def step(self):
        op = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.pc += 2
        family = op & 0xF000
        x = (op & 0x0F00) >> 8
        y = (op & 0x00F0) >> 4
        n = op & 0x000F
        nn = op & 0x00FF
        nnn = op & 0x0FFF

        if family == 0x6000:
            self.V[x] = nn
        elif family == 0x8000 and n == 0x4:
            self._add_with_carry(x, y)          # <-- the bit the buggy CPU breaks
        elif family == 0xA000:
            self.I = nnn
        elif family == 0xF000 and nn == 0x29:
            self.I = FONT_ADDR + self.V[x] * 5
        elif family == 0xD000:
            self._draw(self.V[x], self.V[y], n)
        elif family == 0x1000:
            self.pc = nnn
        else:
            raise ValueError(f"Unknown opcode {op:#06x}")

    def _add_with_carry(self, x, y):
        total = self.V[x] + self.V[y]
        self.V[x] = total & 0xFF
        self.V[0xF] = 1 if total > 0xFF else 0   # correct: set the carry flag

    def _draw(self, px, py, n):
        self.V[0xF] = 0
        for row in range(n):
            sprite = self.mem[self.I + row]
            for col in range(8):
                if (sprite >> (7 - col)) & 1:
                    idx = (py + row) * WIDTH + (px + col)
                    if self.display[idx]:
                        self.V[0xF] = 1
                    self.display[idx] ^= 1


class BuggyCPU(ReferenceCPU):
    """A candidate with the realistic carry-flag bug. Same code, one override."""

    def _add_with_carry(self, x, y):
        self.V[x] = (self.V[x] + self.V[y]) & 0xFF
        # BUG: forgot to set VF. Carry is silently lost.


# The test ROM (hand-assembled, as in Steps 2-3).
TEST_ROM = bytes([
    0x60, 0xFF,   # LD V0, 0xFF
    0x61, 0x01,   # LD V1, 0x01
    0x80, 0x14,   # ADD V0, V1   (VF = carry, if correct)
    0xFF, 0x29,   # LD F, VF     (point I at font(VF))
    0x62, 0x01,   # LD V2, 1     x
    0x63, 0x01,   # LD V3, 1     y
    0xD2, 0x35,   # DRW V2, V3, 5
    0x12, 0x0E,   # JP 0x20E (self) -> halt
])
CYCLES = 20


def run_and_hash(CPUClass, rom, cycles):
    """Run a CPU for fixed cycles, return (framebuffer, sha256-hash)."""
    cpu = CPUClass()
    cpu.load(rom)
    for _ in range(cycles):
        cpu.step()
    fb = cpu.framebuffer()
    return fb, hashlib.sha256(fb).hexdigest()


def ascii_fb(fb, w=10, h=6):
    out = []
    for row in range(h):
        out.append("".join("#" if fb[row * WIDTH + c] else "." for c in range(w)))
    return "\n".join(out)


if __name__ == "__main__":
    # ---- gen_golden: capture the trusted answer from the reference ----------
    golden_fb, golden_hash = run_and_hash(ReferenceCPU, TEST_ROM, CYCLES)
    print("GOLDEN (from reference) — it drew:")
    print(ascii_fb(golden_fb))
    print(f"golden hash = {golden_hash[:16]}…\n")

    # ---- grader: run each candidate, compare hashes, NEVER read source ------
    print(f"{'candidate':14s} result   hash")
    print("-" * 44)
    for name, CPUClass in [("ReferenceCPU", ReferenceCPU), ("BuggyCPU", BuggyCPU)]:
        try:
            fb, h = run_and_hash(CPUClass, TEST_ROM, CYCLES)
            passed = (h == golden_hash)
            print(f"{name:14s} {'PASS' if passed else 'FAIL'}     {h[:16]}…")
        except Exception as e:
            print(f"{name:14s} FAIL     (crashed: {type(e).__name__})")

    print("\nWhat the BUGGY candidate actually drew (a '0' — no carry):")
    print(ascii_fb(run_and_hash(BuggyCPU, TEST_ROM, CYCLES)[0]))
