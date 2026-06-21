"""Hand-authored, deterministic CHIP-8 test ROMs.

Every ROM is built with the tiny assembler below (one helper per opcode plus an
`Asm` builder that tracks addresses so we can write loops and jump-to-self
halts). Each ROM COMPUTES something and then DRAWS the result to the 64x32
screen, so a wrong opcode produces a wrong framebuffer. After drawing, every ROM
spins in a `JP self` loop, so it is safe to run for more cycles than it needs.

ROMs are grouped into three weighted categories, mirroring GBA Eval's tiers:

  * "gameplay"    — multi-opcode programs (highest weight). Exercising many
                    instructions together, the way a real game would.
  * "instruction" — targeted single-opcode checks. Each draws a glyph that
                    differs if the opcode is implemented wrong.
  * "quirk"       — behaviors with multiple plausible interpretations, pinned
                    to the choices documented in TASK.md.

Export: ROMS = { name: (rom_bytes, cycles_to_run, category, weight) }.
"""

PROGRAM_ADDR = 0x200
SCRATCH = 0x300  # safe RAM region for BCD / load-store scratch (well above code)

# --------------------------------------------------------------------------
# Opcode emitters: each returns a 16-bit instruction word.
# --------------------------------------------------------------------------
def CLS():            return 0x00E0
def RET():            return 0x00EE
def JP(nnn):          return 0x1000 | (nnn & 0xFFF)
def CALL(nnn):        return 0x2000 | (nnn & 0xFFF)
def SE(x, nn):        return 0x3000 | (x << 8) | (nn & 0xFF)   # skip if VX == NN
def SNE(x, nn):       return 0x4000 | (x << 8) | (nn & 0xFF)   # skip if VX != NN
def SE_R(x, y):       return 0x5000 | (x << 8) | (y << 4)      # skip if VX == VY
def LD(x, nn):        return 0x6000 | (x << 8) | (nn & 0xFF)   # VX = NN
def ADD(x, nn):       return 0x7000 | (x << 8) | (nn & 0xFF)   # VX += NN (no carry)
def LD_R(x, y):       return 0x8000 | (x << 8) | (y << 4)      # VX = VY
def OR(x, y):         return 0x8001 | (x << 8) | (y << 4)
def AND(x, y):        return 0x8002 | (x << 8) | (y << 4)
def XOR(x, y):        return 0x8003 | (x << 8) | (y << 4)
def ADD_R(x, y):      return 0x8004 | (x << 8) | (y << 4)      # VX += VY (carry->VF)
def SUB(x, y):        return 0x8005 | (x << 8) | (y << 4)      # VX -= VY (borrow->VF)
def SHR(x, y):        return 0x8006 | (x << 8) | (y << 4)
def SUBN(x, y):       return 0x8007 | (x << 8) | (y << 4)
def SHL(x, y):        return 0x800E | (x << 8) | (y << 4)
def SNE_R(x, y):      return 0x9000 | (x << 8) | (y << 4)      # skip if VX != VY
def LDI(nnn):         return 0xA000 | (nnn & 0xFFF)            # I = NNN
def JP0(nnn):         return 0xB000 | (nnn & 0xFFF)            # PC = NNN + V0
def RND(x, nn):       return 0xC000 | (x << 8) | (nn & 0xFF)
def DRW(x, y, n):     return 0xD000 | (x << 8) | (y << 4) | (n & 0xF)
def SKP(x):           return 0xE09E | (x << 8)
def SKNP(x):          return 0xE0A1 | (x << 8)
def LD_DT(x):         return 0xF007 | (x << 8)                 # VX = DT
def SET_DT(x):        return 0xF015 | (x << 8)                 # DT = VX
def SET_ST(x):        return 0xF018 | (x << 8)                 # ST = VX
def ADD_I(x):         return 0xF01E | (x << 8)                 # I += VX
def LD_F(x):          return 0xF029 | (x << 8)                 # I = font(VX)
def BCD(x):           return 0xF033 | (x << 8)
def STORE(x):         return 0xF055 | (x << 8)                 # mem[I..] = V0..VX
def LOAD(x):          return 0xF065 | (x << 8)                 # V0..VX = mem[I..]


class Asm:
    """Minimal assembler that tracks the current address for labels/loops."""

    def __init__(self):
        self.words = []

    def emit(self, *ws):
        for w in ws:
            self.words.append(w & 0xFFFF)
        return self

    def here(self):
        """Address of the next instruction to be emitted."""
        return PROGRAM_ADDR + len(self.words) * 2

    def halt(self):
        """Emit a jump-to-self so the program stops advancing."""
        self.words.append(JP(self.here()))
        return self

    def bytes(self):
        out = bytearray()
        for w in self.words:
            out.append((w >> 8) & 0xFF)
            out.append(w & 0xFF)
        return bytes(out)


# Register conventions used by the helpers below:
#   V0, V1, V2 : digit / scratch values
#   VD (=0xD)  : draw x-coordinate
#   VE (=0xE)  : draw y-coordinate
VD, VE = 0xD, 0xE


def _draw_byte_value(a, reg, scratch=SCRATCH):
    """Emit code that BCD-decomposes VX=reg and draws its 3 digits left-to-right.

    Used by several ROMs so a numeric result becomes a distinctive picture.
    Leaves I clobbered (via LD_F). Uses V0..V2, VD, VE.
    """
    a.emit(LDI(scratch))
    a.emit(BCD(reg))          # scratch[0..2] = hundreds, tens, ones
    a.emit(LOAD(2))           # V0,V1,V2 = those three digits
    a.emit(LD(VD, 0))         # x = 0
    a.emit(LD(VE, 0))         # y = 0
    a.emit(LD_F(0)); a.emit(DRW(VD, VE, 5)); a.emit(ADD(VD, 5))
    a.emit(LD_F(1)); a.emit(DRW(VD, VE, 5)); a.emit(ADD(VD, 5))
    a.emit(LD_F(2)); a.emit(DRW(VD, VE, 5))


# ==========================================================================
# GAMEPLAY — multi-opcode programs (highest weight)
# ==========================================================================
def rom_draw_digit():
    """Load digit 5 and draw its font glyph at (1,1)."""
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 5))
    a.emit(LD_F(0))
    a.emit(LD(VD, 1))
    a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_bcd_draw():
    """BCD-decompose 137 and draw all three digits. Exercises FX33/FX65/FX29."""
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 137))
    _draw_byte_value(a, 0)
    a.halt()
    return a.bytes()


def rom_loop_sum():
    """Sum 1..5 in a loop (=15) then BCD-draw it. Exercises control flow.

    Loop shape:  count += 1; sum += count; if count == 5 skip the loop-back.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(1, 0))          # V1 sum   = 0
    a.emit(LD(2, 0))          # V2 count = 0
    loop = a.here()
    a.emit(ADD(2, 1))         # count += 1
    a.emit(ADD_R(1, 2))       # sum += count
    a.emit(SE(2, 5))          # if count == 5: skip the loop-back jump
    a.emit(JP(loop))          # else loop again
    _draw_byte_value(a, 1)    # draw sum (15 -> "015")
    a.halt()
    return a.bytes()


# ==========================================================================
# INSTRUCTION — targeted single-opcode checks
# ==========================================================================
def rom_add_carry_vf():
    """8XY4 must set VF=1 on overflow. 0xFF + 0x01 -> VF=1; draw VF (=digit 1).

    A core that forgets the carry leaves VF=0 and draws digit 0 instead.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 0xFF))
    a.emit(LD(1, 0x01))
    a.emit(ADD_R(0, 1))       # V0 = 0x00, VF = 1
    a.emit(LD_F(0xF))         # I = font(VF)
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_sub_borrow_vf():
    """8XY5 must set VF=1 when there is NO borrow. 5 - 3 -> VF=1; draw VF.

    An inverted-borrow core draws digit 0 instead of digit 1.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 5))
    a.emit(LD(1, 3))
    a.emit(SUB(0, 1))         # V0 = 2, VF = 1
    a.emit(LD_F(0xF))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_skip_3xnn():
    """3XNN must skip the next instruction when VX == NN.

    V2 starts at 1; if the skip works the "V2 = 7" is skipped and we draw 1.
    A broken skip draws 7.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 5))
    a.emit(LD(2, 1))          # correct-path marker
    a.emit(SE(0, 5))          # V0 == 5 -> skip next
    a.emit(LD(2, 7))          # (skipped when correct)
    a.emit(LD_F(2))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_logic_and():
    """8XY2 AND. 0b1100 & 0b1010 = 0b1000 = 8; draw digit 8."""
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 0x0C))
    a.emit(LD(1, 0x0A))
    a.emit(AND(0, 1))         # V0 = 0x08
    a.emit(LD_F(0))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_jp_v0_bnnn():
    """BNNN jumps to NNN + V0. Use it to land on code that draws digit 3.

    The jump target is computed at assembly time. If BNNN ignores V0 (or adds
    wrong), execution lands elsewhere and the picture changes.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 4))                 # V0 = 4 (the offset)
    # The next instruction is BNNN. After it we lay out two 1-instruction
    # "draw" blocks; V0=4 selects the second one (each block before target is
    # 2 bytes / 1 word). We jump to (base + V0) where base targets the WRONG
    # block and +4 lands on the RIGHT block.
    jp_index = len(a.words)
    a.emit(0)                        # placeholder for BNNN, patched below
    wrong_at = a.here()
    a.emit(LD(3, 6))                 # WRONG: would draw digit 6
    a.emit(JP(0))                    # placeholder jump to draw, patched
    right_at = a.here()
    a.emit(LD(3, 3))                 # RIGHT: draw digit 3
    draw_at = a.here()
    a.emit(LD_F(3))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    # Patch: BNNN target = wrong_at, so wrong_at + V0(4) == right_at.
    assert right_at == wrong_at + 4, (wrong_at, right_at)
    a.words[jp_index] = JP0(wrong_at)
    # Patch the wrong-block's jump so that if a broken BNNN lands there, it
    # still terminates (drawing the wrong digit) rather than running off.
    a.words[jp_index + 2] = JP(draw_at)
    return a.bytes()


# ==========================================================================
# QUIRK — pinned interpretations (see TASK.md)
# ==========================================================================
def rom_quirk_shr():
    """8XY6 shifts IN-PLACE: V0 = V0 >> 1, VY ignored.

    V0 = 8, V1 = 3. In-place -> V0 = 4 (draw digit 4).
    COSMAC "VX = VY >> 1" -> V0 = 1 (draw digit 1). Different picture.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 8))
    a.emit(LD(1, 3))
    a.emit(SHR(0, 1))         # in-place: V0 = 8>>1 = 4
    a.emit(LD_F(0))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_quirk_shl():
    """8XYE shifts IN-PLACE: V0 = V0 << 1, VY ignored.

    V0 = 4, V1 = 9. In-place -> V0 = 8 (draw digit 8).
    COSMAC "VX = VY << 1" -> V0 = 18 = 0x12; low nibble 2 -> draws digit 2.
    We AND with 0x0F before drawing so the font index is always valid.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 4))
    a.emit(LD(1, 9))
    a.emit(SHL(0, 1))         # in-place: V0 = 4<<1 = 8
    a.emit(LD(2, 0x0F))
    a.emit(AND(0, 2))         # keep low nibble (font-safe)
    a.emit(LD_F(0))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_quirk_fx55_i():
    """FX55/FX65 must leave I unchanged.

    Set I=scratch, store V0=7, clear V0, then load V0 back from the SAME I.
    If FX55 left I alone, FX65 reads scratch[0]=7 -> draw digit 7.
    If FX55 advanced I (old behavior), FX65 reads scratch[1]=0 -> draw digit 0.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LDI(SCRATCH))
    a.emit(LD(0, 7))
    a.emit(STORE(0))          # mem[scratch] = 7 ; I must stay = scratch
    a.emit(LD(0, 0))          # clobber V0
    a.emit(LOAD(0))           # V0 = mem[I]; quirk-correct -> 7
    a.emit(LD_F(0))
    a.emit(LD(VD, 1)); a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


def rom_quirk_dxyn_clip():
    """DXYN clips at the right edge instead of wrapping.

    Draw digit 8 (8px wide glyph) at x=62. With clipping only columns 62,63
    appear. With wrapping, the overflow columns reappear at x=0,1. Different fb.
    """
    a = Asm()
    a.emit(CLS())
    a.emit(LD(0, 8))
    a.emit(LD_F(0))
    a.emit(LD(VD, 62))
    a.emit(LD(VE, 1))
    a.emit(DRW(VD, VE, 5))
    a.halt()
    return a.bytes()


# --------------------------------------------------------------------------
# Registry: name -> (rom_bytes, cycles_to_run, category, weight)
# Cycles are generous; the jump-to-self halt makes overshoot harmless.
# --------------------------------------------------------------------------
_GAMEPLAY_W = 3
_INSTR_W = 2
_QUIRK_W = 2

ROMS = {
    # gameplay
    "draw_digit":      (rom_draw_digit(),      50,  "gameplay",    _GAMEPLAY_W),
    "bcd_draw":        (rom_bcd_draw(),        100, "gameplay",    _GAMEPLAY_W),
    "loop_sum":        (rom_loop_sum(),        200, "gameplay",    _GAMEPLAY_W),
    # instruction
    "add_carry_vf":    (rom_add_carry_vf(),    50,  "instruction", _INSTR_W),
    "sub_borrow_vf":   (rom_sub_borrow_vf(),   50,  "instruction", _INSTR_W),
    "skip_3xnn":       (rom_skip_3xnn(),       50,  "instruction", _INSTR_W),
    "logic_and":       (rom_logic_and(),       50,  "instruction", _INSTR_W),
    "jp_v0_bnnn":      (rom_jp_v0_bnnn(),      50,  "instruction", _INSTR_W),
    # quirk
    "quirk_shr":       (rom_quirk_shr(),       50,  "quirk",       _QUIRK_W),
    "quirk_shl":       (rom_quirk_shl(),       50,  "quirk",       _QUIRK_W),
    "quirk_fx55_i":    (rom_quirk_fx55_i(),    50,  "quirk",       _QUIRK_W),
    "quirk_dxyn_clip": (rom_quirk_dxyn_clip(), 50,  "quirk",       _QUIRK_W),
}


if __name__ == "__main__":
    for name, (rom, cycles, cat, w) in ROMS.items():
        print(f"{name:18s} {cat:12s} w={w} bytes={len(rom):3d} cycles={cycles}")
