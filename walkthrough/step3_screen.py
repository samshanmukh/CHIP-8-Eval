"""STEP 3 — The screen: making a computed value VISIBLE.

This is the conceptual heart of the eval. So far the CPU can compute, but every
result is trapped inside a register where a black-box grader can't see it. To
grade behavior we need the program to DRAW its result. Here's how CHIP-8 draws.

THE DISPLAY is 64x32 = 2048 pixels, each just on (1) or off (0). We store it as
a flat bytearray, row-major: pixel (x, y) lives at index  y*64 + x.

SPRITES. CHIP-8 has no "draw text" or "draw shape". You draw a SPRITE: 1..15
bytes of memory, each byte a row of 8 pixels (the 8 bits = 8 pixels, MSB on the
left). The I register says WHERE in memory the sprite's bytes start.

THE FONT. The interpreter pre-loads a built-in font: the hex digits 0-F, each a
5-byte sprite, stored at address 0x50. Opcode FX29 sets I to the font glyph for
the digit in VX. So "draw the digit in V0" is just: FX29 V0 (point I at it),
then DXYN (draw it). THIS is how a number becomes a picture.

XOR DRAWING + COLLISION. DXYN doesn't overwrite pixels — it XORs them. A set
sprite bit flips the pixel underneath. Drawing the same sprite twice erases it
(that's how games animate). And if drawing ever turns an already-on pixel OFF,
the CPU sets VF=1 — the "collision" flag games use for hit detection.

New opcodes this step:
    ANNN  LD I, NNN      I = NNN                  (set the draw pointer directly)
    FX29  LD F, VX       I = address of font(VX)  (point I at a digit glyph)
    DXYN  DRW VX, VY, N  draw N-byte sprite at (VX,VY), XOR, set VF on collision
"""

PROGRAM_ADDR = 0x200
FONT_ADDR = 0x50
WIDTH, HEIGHT = 64, 32

# Built-in hex font: 5 bytes per digit. Look at '3' in binary to SEE the glyph:
#   0xF0 = 1111 0000   ████
#   0x10 = 0001 0000      █
#   0xF0 = 1111 0000   ████
#   0x10 = 0001 0000      █
#   0xF0 = 1111 0000   ████      <- that's a "3" drawn in pixels
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
]


class CPU:
    def __init__(self):
        self.mem = bytearray(4096)
        self.V = bytearray(16)
        self.I = 0                       # the draw pointer
        self.pc = PROGRAM_ADDR
        self.display = bytearray(WIDTH * HEIGHT)   # our 2048-pixel screen
        for i, b in enumerate(FONT):     # load the font at 0x50
            self.mem[FONT_ADDR + i] = b

    def load(self, program):
        for i, b in enumerate(program):
            self.mem[PROGRAM_ADDR + i] = b

    def framebuffer(self):
        return bytes(self.display)       # the ONLY thing a grader gets to see

    def step(self):
        op = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.pc += 2
        family = op & 0xF000
        x = (op & 0x0F00) >> 8
        y = (op & 0x00F0) >> 4
        n = op & 0x000F
        nn = op & 0x00FF
        nnn = op & 0x0FFF

        if family == 0x6000:                         # 6XNN  LD VX, NN
            self.V[x] = nn
        elif family == 0xA000:                       # ANNN  LD I, NNN
            self.I = nnn
        elif family == 0xF000 and nn == 0x29:        # FX29  point I at font(VX)
            self.I = FONT_ADDR + self.V[x] * 5
        elif family == 0xD000:                        # DXYN  draw sprite
            self._draw(self.V[x], self.V[y], n)
        elif family == 0x1000:                        # 1NNN  JP
            self.pc = nnn
        else:
            raise ValueError(f"Unknown opcode {op:#06x}")

    def _draw(self, px, py, n):
        self.V[0xF] = 0                              # clear collision flag
        for row in range(n):                         # each byte = one row
            sprite_byte = self.mem[self.I + row]
            for col in range(8):                     # each bit = one pixel
                bit = (sprite_byte >> (7 - col)) & 1  # MSB is leftmost pixel
                if bit:
                    sx, sy = px + col, py + row
                    idx = sy * WIDTH + sx
                    if self.display[idx] == 1:        # turning an ON pixel off?
                        self.V[0xF] = 1               # -> collision!
                    self.display[idx] ^= 1            # XOR it


def ascii_fb(fb, w=18, h=7):
    """Render the top-left corner of the framebuffer so we can SEE it."""
    out = []
    for row in range(h):
        line = "".join("#" if fb[row * WIDTH + col] else "." for col in range(w))
        out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    # Program: draw the digit 3 at screen position (1, 1), then halt.
    #   0x200  60 03   LD  V0, 3       V0 = 3 (the digit we want)
    #   0x202  F0 29   LD  F, V0       I = address of the '3' glyph
    #   0x204  61 01   LD  V1, 1       V1 = 1  (x coordinate)
    #   0x206  62 01   LD  V2, 1       V2 = 1  (y coordinate)
    #   0x208  D1 25   DRW V1, V2, 5   draw 5-byte sprite at (V1,V2)
    #   0x20A  12 0A   JP  0x20A       halt
    program = bytes([
        0x60, 0x03,
        0xF0, 0x29,
        0x61, 0x01,
        0x62, 0x01,
        0xD1, 0x25,
        0x12, 0x0A,
    ])

    cpu = CPU()
    cpu.load(program)
    for _ in range(20):       # run more steps than needed — halt makes it safe
        cpu.step()

    print("The CPU computed the number 3 and DREW it:\n")
    print(ascii_fb(cpu.framebuffer()))
    print(f"\nVF (collision) = {cpu.V[0xF]}")
