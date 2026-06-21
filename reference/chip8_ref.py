"""Reference CHIP-8 core — the ground truth for CHIP-8 Eval.

This is the analogue of Mesen2 in the GBA Eval: a known-correct, fully
DETERMINISTIC implementation that we trust. Golden framebuffers are generated
by running test ROMs on this core, and candidate emulators are graded by
comparing their framebuffers against those goldens.

The quirks this core commits to (and that the grader therefore enforces) are
documented in TASK.md. The important ones:

  * 8XY6 / 8XYE shift IN-PLACE: VX = VX >> 1 / VX << 1, VY is ignored,
    VF receives the bit shifted out.
  * FX55 / FX65 do NOT modify I.
  * DXYN: starting coordinates wrap (x % 64, y % 32), but the sprite is then
    CLIPPED at the screen edges — it does not wrap around to the far side.

The harness provides no input: EX9E / EXA1 always see every key released, and
no ROM uses FX0A. CXNN uses a fixed-seed RNG so the core is reproducible (the
test ROMs avoid CXNN, so the seed never affects goldens).
"""

WIDTH = 64
HEIGHT = 32
FB_SIZE = WIDTH * HEIGHT  # 2048

FONT_ADDR = 0x50
PROGRAM_ADDR = 0x200

# Standard hex-digit font, 5 bytes per glyph, digits 0-F.
FONT = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
]

RNG_SEED = 0x13371337


class Chip8:
    def __init__(self):
        self.mem = bytearray(4096)
        self.V = bytearray(16)            # V0..VF
        self.I = 0
        self.pc = PROGRAM_ADDR
        self.stack = []
        self.delay = 0
        self.sound = 0
        self.display = bytearray(FB_SIZE)  # row-major, one byte per pixel (0/1)
        # Deterministic RNG for CXNN. A tiny LCG keeps us free of any global
        # random state and identical across Python versions.
        self._rng = RNG_SEED
        # Keys: all released, always. Exposed for clarity; the harness never
        # presses anything.
        self.keys = [False] * 16
        for i, b in enumerate(FONT):
            self.mem[FONT_ADDR + i] = b

    # ------------------------------------------------------------------ API
    def load(self, rom):
        """Load a program at 0x200."""
        for i, b in enumerate(rom):
            self.mem[PROGRAM_ADDR + i] = b

    def framebuffer(self):
        """Return 2048 bytes, 64x32 row-major, each 0 or 1."""
        return bytes(self.display)

    def step(self):
        """Fetch, decode, and execute exactly one instruction."""
        op = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.pc = (self.pc + 2) & 0xFFF
        self._exec(op)
        # Timers tick once per step. No graded ROM observes timer values, so
        # the exact cadence is irrelevant to scoring; we only need determinism.
        if self.delay > 0:
            self.delay -= 1
        if self.sound > 0:
            self.sound -= 1

    # ------------------------------------------------------------- internals
    def _rand_byte(self):
        # 32-bit LCG (numerical recipes constants); take the high byte.
        self._rng = (self._rng * 1664525 + 1013904223) & 0xFFFFFFFF
        return (self._rng >> 16) & 0xFF

    def _exec(self, op):
        nnn = op & 0x0FFF
        nn = op & 0x00FF
        n = op & 0x000F
        x = (op & 0x0F00) >> 8
        y = (op & 0x00F0) >> 4
        V = self.V
        head = op & 0xF000

        if op == 0x00E0:                                  # CLS
            for i in range(FB_SIZE):
                self.display[i] = 0
        elif op == 0x00EE:                                # RET
            self.pc = self.stack.pop()
        elif head == 0x1000:                              # 1NNN JP
            self.pc = nnn
        elif head == 0x2000:                              # 2NNN CALL
            self.stack.append(self.pc)
            self.pc = nnn
        elif head == 0x3000:                              # 3XNN SE VX, NN
            if V[x] == nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif head == 0x4000:                              # 4XNN SNE VX, NN
            if V[x] != nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif head == 0x5000 and n == 0:                   # 5XY0 SE VX, VY
            if V[x] == V[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif head == 0x6000:                              # 6XNN LD VX, NN
            V[x] = nn
        elif head == 0x7000:                              # 7XNN ADD VX, NN
            V[x] = (V[x] + nn) & 0xFF
        elif head == 0x8000:
            self._exec_8(op, x, y, n)
        elif head == 0x9000 and n == 0:                   # 9XY0 SNE VX, VY
            if V[x] != V[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif head == 0xA000:                              # ANNN LD I, NNN
            self.I = nnn
        elif head == 0xB000:                              # BNNN JP V0, NNN
            self.pc = (nnn + V[0]) & 0xFFF
        elif head == 0xC000:                              # CXNN RND VX, NN
            V[x] = self._rand_byte() & nn
        elif head == 0xD000:                              # DXYN DRW
            self._draw(V[x], V[y], n)
        elif head == 0xE000:
            if nn == 0x9E:                                # EX9E skip if key down
                if self.keys[V[x] & 0xF]:
                    self.pc = (self.pc + 2) & 0xFFF
            elif nn == 0xA1:                              # EXA1 skip if key up
                if not self.keys[V[x] & 0xF]:
                    self.pc = (self.pc + 2) & 0xFFF
        elif head == 0xF000:
            self._exec_f(op, x, nn)
        # Unknown opcodes are treated as no-ops; the reference never emits any.

    def _exec_8(self, op, x, y, n):
        V = self.V
        if n == 0x0:                                      # 8XY0 LD VX, VY
            V[x] = V[y]
        elif n == 0x1:                                    # 8XY1 OR
            V[x] = V[x] | V[y]
        elif n == 0x2:                                    # 8XY2 AND
            V[x] = V[x] & V[y]
        elif n == 0x3:                                    # 8XY3 XOR
            V[x] = V[x] ^ V[y]
        elif n == 0x4:                                    # 8XY4 ADD (carry)
            s = V[x] + V[y]
            V[x] = s & 0xFF
            V[0xF] = 1 if s > 0xFF else 0
        elif n == 0x5:                                    # 8XY5 SUB (borrow)
            flag = 1 if V[x] >= V[y] else 0
            V[x] = (V[x] - V[y]) & 0xFF
            V[0xF] = flag
        elif n == 0x6:                                    # 8XY6 SHR (in-place)
            flag = V[x] & 1
            V[x] = V[x] >> 1
            V[0xF] = flag
        elif n == 0x7:                                    # 8XY7 SUBN (borrow)
            flag = 1 if V[y] >= V[x] else 0
            V[x] = (V[y] - V[x]) & 0xFF
            V[0xF] = flag
        elif n == 0xE:                                    # 8XYE SHL (in-place)
            flag = (V[x] >> 7) & 1
            V[x] = (V[x] << 1) & 0xFF
            V[0xF] = flag

    def _exec_f(self, op, x, nn):
        V = self.V
        if nn == 0x07:                                    # FX07 LD VX, DT
            V[x] = self.delay
        elif nn == 0x15:                                  # FX15 LD DT, VX
            self.delay = V[x]
        elif nn == 0x18:                                  # FX18 LD ST, VX
            self.sound = V[x]
        elif nn == 0x1E:                                  # FX1E ADD I, VX
            self.I = (self.I + V[x]) & 0xFFFF
        elif nn == 0x29:                                  # FX29 LD F, VX
            self.I = FONT_ADDR + (V[x] & 0xF) * 5
        elif nn == 0x33:                                  # FX33 BCD
            self.mem[self.I] = V[x] // 100
            self.mem[self.I + 1] = (V[x] // 10) % 10
            self.mem[self.I + 2] = V[x] % 10
        elif nn == 0x55:                                  # FX55 store V0..VX
            for i in range(x + 1):
                self.mem[self.I + i] = V[i]
            # I is NOT modified (documented quirk).
        elif nn == 0x65:                                  # FX65 load V0..VX
            for i in range(x + 1):
                V[i] = self.mem[self.I + i]
            # I is NOT modified (documented quirk).

    def _draw(self, vx, vy, n):
        V = self.V
        # Starting coordinate wraps; the sprite itself is clipped at the edges.
        x0 = vx % WIDTH
        y0 = vy % HEIGHT
        V[0xF] = 0
        for row in range(n):
            py = y0 + row
            if py >= HEIGHT:
                break  # clipped at bottom edge (no wrap)
            sprite = self.mem[(self.I + row) & 0xFFF]
            for col in range(8):
                px = x0 + col
                if px >= WIDTH:
                    break  # clipped at right edge (no wrap)
                if (sprite >> (7 - col)) & 1:
                    idx = py * WIDTH + px
                    if self.display[idx]:
                        V[0xF] = 1
                    self.display[idx] ^= 1
