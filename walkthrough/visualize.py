"""A step-by-step CHIP-8 visualizer — SEE the emulator think.

Runs a real test ROM on the real reference core and, for every instruction,
shows:
    * the program counter and the raw opcode
    * a human-readable disassembly of what it does
    * which registers changed (old -> new)
    * the 64x32 screen, redrawn whenever it changes

Usage:
    python3 walkthrough/visualize.py                 # default ROM (bcd_draw)
    python3 walkthrough/visualize.py loop_sum        # any ROM name from roms.py
    python3 walkthrough/visualize.py bcd_draw --animate   # live animation
    python3 walkthrough/visualize.py --list          # list available ROMs

It stops as soon as the program reaches its jump-to-self halt, so you see
exactly the instructions that matter and nothing more.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reference.chip8_ref import Chip8, WIDTH, HEIGHT
from roms import ROMS


def disasm(op):
    """Turn a 16-bit opcode into readable assembly + a plain-English note."""
    x = (op & 0x0F00) >> 8
    y = (op & 0x00F0) >> 4
    n = op & 0x000F
    nn = op & 0x00FF
    nnn = op & 0x0FFF
    f = op & 0xF000
    if op == 0x00E0:           return "CLS",            "clear the screen"
    if op == 0x00EE:           return "RET",            "return from subroutine"
    if f == 0x1000:            return f"JP {nnn:#05x}", "jump"
    if f == 0x2000:            return f"CALL {nnn:#05x}","call subroutine"
    if f == 0x3000:            return f"SE V{x:X},{nn}", f"skip next if V{x:X}=={nn}"
    if f == 0x4000:            return f"SNE V{x:X},{nn}",f"skip next if V{x:X}!={nn}"
    if f == 0x5000:            return f"SE V{x:X},V{y:X}",f"skip if V{x:X}==V{y:X}"
    if f == 0x6000:            return f"LD V{x:X},{nn}",  f"V{x:X} = {nn}"
    if f == 0x7000:            return f"ADD V{x:X},{nn}", f"V{x:X} += {nn} (no carry)"
    if f == 0x8000:
        return {
            0x0: (f"LD V{x:X},V{y:X}",  f"V{x:X} = V{y:X}"),
            0x1: (f"OR V{x:X},V{y:X}",  f"V{x:X} |= V{y:X}"),
            0x2: (f"AND V{x:X},V{y:X}", f"V{x:X} &= V{y:X}"),
            0x3: (f"XOR V{x:X},V{y:X}", f"V{x:X} ^= V{y:X}"),
            0x4: (f"ADD V{x:X},V{y:X}", f"V{x:X} += V{y:X}, VF=carry"),
            0x5: (f"SUB V{x:X},V{y:X}", f"V{x:X} -= V{y:X}, VF=!borrow"),
            0x6: (f"SHR V{x:X}",        f"V{x:X} >>= 1 (in-place), VF=lost bit"),
            0x7: (f"SUBN V{x:X},V{y:X}",f"V{x:X} = V{y:X}-V{x:X}, VF=!borrow"),
            0xE: (f"SHL V{x:X}",        f"V{x:X} <<= 1 (in-place), VF=lost bit"),
        }.get(n, (f"{op:#06x}", "?"))
    if f == 0x9000:            return f"SNE V{x:X},V{y:X}",f"skip if V{x:X}!=V{y:X}"
    if f == 0xA000:            return f"LD I,{nnn:#05x}", f"I = {nnn:#05x}"
    if f == 0xB000:            return f"JP V0,{nnn:#05x}", f"jump to {nnn:#05x}+V0"
    if f == 0xC000:            return f"RND V{x:X},{nn}",  f"V{x:X} = rand & {nn}"
    if f == 0xD000:            return f"DRW V{x:X},V{y:X},{n}", f"draw {n}-row sprite at (V{x:X},V{y:X})"
    if f == 0xE000 and nn == 0x9E: return f"SKP V{x:X}",  "skip if key down"
    if f == 0xE000 and nn == 0xA1: return f"SKNP V{x:X}", "skip if key up"
    if f == 0xF000:
        return {
            0x07: (f"LD V{x:X},DT", f"V{x:X} = delay timer"),
            0x15: (f"LD DT,V{x:X}", f"delay = V{x:X}"),
            0x18: (f"LD ST,V{x:X}", f"sound = V{x:X}"),
            0x1E: (f"ADD I,V{x:X}",  f"I += V{x:X}"),
            0x29: (f"LD F,V{x:X}",   f"I = font glyph for V{x:X}"),
            0x33: (f"BCD V{x:X}",    f"store decimal digits of V{x:X} at I"),
            0x55: (f"LD [I],V0..V{x:X}", "store registers to memory (I unchanged)"),
            0x65: (f"LD V0..V{x:X},[I]", "load registers from memory (I unchanged)"),
        }.get(nn, (f"{op:#06x}", "?"))
    return f"{op:#06x}", "?"


def render_screen(fb):
    out = []
    for row in range(HEIGHT):
        out.append("".join("█" if fb[row * WIDTH + c] else "·" for c in range(WIDTH)))
    return "\n".join(out)


def regs_changed(before, after):
    parts = []
    for i in range(16):
        if before[i] != after[i]:
            parts.append(f"V{i:X}:{before[i]}→{after[i]}")
    return parts


def main():
    args = [a for a in sys.argv[1:]]
    animate = "--animate" in args
    args = [a for a in args if not a.startswith("--")]

    if "--list" in sys.argv:
        for name, (_, _, cat, w) in ROMS.items():
            print(f"  {name:18s} {cat:12s} weight={w}")
        return

    rom_name = args[0] if args else "bcd_draw"
    if rom_name not in ROMS:
        print(f"Unknown ROM '{rom_name}'. Try --list.")
        return

    rom, cycles, category, weight = ROMS[rom_name]
    cpu = Chip8()
    cpu.load(rom)

    print(f"ROM: {rom_name}  ({category}, weight {weight})  —  {len(rom)} bytes\n")

    last_screen = None
    for stepno in range(1, cycles + 1):
        pc_before = cpu.pc
        op = (cpu.mem[pc_before] << 8) | cpu.mem[pc_before + 1]

        # Detect the jump-to-self halt: stop once we'd spin forever.
        if op == (0x1000 | pc_before):
            print(f"\n— halted at {pc_before:#05x} (jump-to-self) after {stepno-1} steps —")
            break

        v_before = bytes(cpu.V)
        i_before = cpu.I
        cpu.step()

        asm, note = disasm(op)
        changes = regs_changed(v_before, cpu.V)
        if cpu.I != i_before:
            changes.append(f"I:{i_before:#05x}→{cpu.I:#05x}")
        change_str = "  ".join(changes) if changes else "—"

        line = (f"step {stepno:>3}  PC={pc_before:#05x}  {op:04X}  "
                f"{asm:14s} ; {note}")
        screen = render_screen(cpu.framebuffer())
        screen_changed = screen != last_screen

        if animate:
            os.system("clear")
            print(f"ROM: {rom_name}\n")
            print(line)
            print(f"  changed: {change_str}\n")
            print(screen)
            time.sleep(0.18)
        else:
            print(line)
            print(f"            changed: {change_str}")
            if screen_changed:
                print(screen)
        last_screen = screen

    if not animate:
        print("\nFinal screen:")
        print(render_screen(cpu.framebuffer()))


if __name__ == "__main__":
    main()
