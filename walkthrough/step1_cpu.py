"""STEP 1 — The smallest possible CPU.

Goal: understand the heartbeat of every emulator — the fetch/decode/execute
loop. We implement EXACTLY ONE instruction and run a one-instruction program.

A CHIP-8 program is just bytes sitting in memory. Instructions are 16 bits
(two bytes) each. The "program counter" (PC) is an index into memory pointing
at the next instruction. To run one step you:

    1. FETCH   : read 2 bytes at PC, glue them into a 16-bit number `op`
    2. (advance PC by 2 so next step reads the next instruction)
    3. DECODE  : look at `op` and figure out what it means
    4. EXECUTE : do it

That's the entire job. Everything else is just more cases in the decode.

The one opcode we implement:

    6XNN  ->  "set register VX to the value NN"
              X is one hex digit (which register, 0..F)
              NN is one byte    (the value)

    Example: 0x6A2C  means  "V[0xA] = 0x2C"  (set register A to 44)
"""

PROGRAM_ADDR = 0x200  # CHIP-8 programs are loaded starting here, by convention


class CPU:
    def __init__(self):
        self.mem = bytearray(4096)   # 4 KB of memory — the whole world
        self.V = bytearray(16)       # 16 registers, V0..VF, each one byte
        self.pc = PROGRAM_ADDR       # points at the next instruction

    def load(self, program):
        # Copy the program bytes into memory at 0x200.
        for i, b in enumerate(program):
            self.mem[PROGRAM_ADDR + i] = b

    def step(self):
        # 1. FETCH: two bytes -> one 16-bit instruction (big-endian).
        high = self.mem[self.pc]
        low = self.mem[self.pc + 1]
        op = (high << 8) | low

        # 2. ADVANCE the program counter past this instruction.
        self.pc += 2

        # 3+4. DECODE + EXECUTE.
        # Pull apart the nibbles (4-bit pieces) we care about.
        opcode_family = op & 0xF000     # top nibble tells us which instruction
        x = (op & 0x0F00) >> 8          # second nibble = register index
        nn = op & 0x00FF                # bottom byte = immediate value

        if opcode_family == 0x6000:     # 6XNN
            self.V[x] = nn
        else:
            raise ValueError(f"Unknown opcode {op:#06x} — we haven't built it yet")


if __name__ == "__main__":
    # Hand-assemble a tiny program. Two instructions:
    #   6A2C  ->  V[A] = 0x2C  (44)
    #   6105  ->  V[1] = 0x05  (5)
    program = bytes([0x6A, 0x2C, 0x61, 0x05])

    cpu = CPU()
    cpu.load(program)

    print(f"Before:  V[A]={cpu.V[0xA]}  V[1]={cpu.V[1]}  PC={cpu.pc:#05x}")
    cpu.step()
    print(f"Step 1:  V[A]={cpu.V[0xA]}  V[1]={cpu.V[1]}  PC={cpu.pc:#05x}")
    cpu.step()
    print(f"Step 2:  V[A]={cpu.V[0xA]}  V[1]={cpu.V[1]}  PC={cpu.pc:#05x}")
