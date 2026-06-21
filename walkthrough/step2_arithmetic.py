"""STEP 2 — Arithmetic, the carry flag, and jumps.

Step 1 gave us the fetch/decode/execute loop with ONE opcode (6XNN). Now we add
four more so the CPU can actually compute and control its own flow:

    6XNN  LD   VX, NN     VX = NN                     (from step 1)
    7XNN  ADD  VX, NN     VX = (VX + NN) & 0xFF       add a constant, NO carry
    8XY4  ADD  VX, VY     VX = VX + VY, set VF=carry  add two registers, WITH carry
    1NNN  JP   NNN        PC = NNN                     jump (overwrite the PC)

Two big new ideas live here:

(1) THE CARRY FLAG. Registers are 8-bit, so they hold 0..255. 0xFF + 1 can't fit
    in 8 bits — it overflows to 0. CHIP-8's rule: the special register VF
    (that's V[15]) is set to 1 when an add overflows, else 0. VF is the CPU's
    "did it carry?" answer. Programs read it to do multi-byte math. This single
    flag is the entire subject of one of our buggy-candidate's bugs.

    NOTE the asymmetry: 7XNN (add a constant) does NOT touch VF. 8XY4 (add two
    registers) DOES. Same word "add", different flag behavior. Easy to get wrong.

(2) JUMPS. Until now PC only marched forward (+2 each step). 1NNN *overwrites*
    PC. That's how loops exist. A jump to a program's OWN address is an infinite
    "do nothing" loop — which is how every test ROM HALTS: it parks the PC so
    running extra steps changes nothing.
"""

PROGRAM_ADDR = 0x200


class CPU:
    def __init__(self):
        self.mem = bytearray(4096)
        self.V = bytearray(16)       # V[0xF] is the flag register
        self.pc = PROGRAM_ADDR

    def load(self, program):
        for i, b in enumerate(program):
            self.mem[PROGRAM_ADDR + i] = b

    def step(self):
        # FETCH + ADVANCE
        op = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.pc += 2

        # DECODE: carve out every field; each opcode uses a subset.
        family = op & 0xF000
        x = (op & 0x0F00) >> 8
        y = (op & 0x00F0) >> 4
        nn = op & 0x00FF
        nnn = op & 0x0FFF

        # EXECUTE
        if family == 0x6000:                    # 6XNN  LD VX, NN
            self.V[x] = nn

        elif family == 0x7000:                  # 7XNN  ADD VX, NN  (no carry)
            self.V[x] = (self.V[x] + nn) & 0xFF

        elif family == 0x8000 and (op & 0xF) == 0x4:   # 8XY4  ADD VX, VY (carry)
            total = self.V[x] + self.V[y]
            self.V[x] = total & 0xFF            # keep low 8 bits
            self.V[0xF] = 1 if total > 0xFF else 0     # VF = did it overflow?

        elif family == 0x1000:                  # 1NNN  JP NNN
            self.pc = nnn                       # overwrite PC instead of advancing

        else:
            raise ValueError(f"Unknown opcode {op:#06x}")


def show(cpu, label):
    print(f"{label:9s} V0={cpu.V[0]:3d}  V1={cpu.V[1]:3d}  "
          f"VF={cpu.V[0xF]}  PC={cpu.pc:#05x}")


if __name__ == "__main__":
    # Program that demonstrates overflow + a halt loop:
    #
    #   0x200  60 FF   LD  V0, 0xFF     V0 = 255
    #   0x202  61 01   LD  V1, 0x01     V1 = 1
    #   0x204  80 14   ADD V0, V1       V0 = 255+1 = 256 -> 0, and VF = 1 (carry!)
    #   0x206  12 06   JP  0x206        jump to SELF -> halt (PC stops moving)
    program = bytes([
        0x60, 0xFF,
        0x61, 0x01,
        0x80, 0x14,
        0x12, 0x06,
    ])

    cpu = CPU()
    cpu.load(program)

    show(cpu, "start")
    cpu.step(); show(cpu, "LD V0")
    cpu.step(); show(cpu, "LD V1")
    cpu.step(); show(cpu, "ADD")      # watch V0 wrap to 0 and VF become 1
    cpu.step(); show(cpu, "JP self")
    cpu.step(); show(cpu, "JP again") # PC does NOT move — the halt loop in action
    cpu.step(); show(cpu, "JP again")
