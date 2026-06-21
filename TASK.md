# CHIP-8 Eval — Agent Task

Write a **CHIP-8 emulator core** in Python 3 (standard library only). You will be
graded **black-box**: an automated grader runs deterministic test ROMs on your
emulator, hashes the resulting display, and compares it against goldens captured
from a reference implementation. The grader never reads your source — only your
emulator's observable behavior counts.

## Deliverable

A single Python file defining a class named exactly `Chip8` with this interface:

```python
class Chip8:
    def __init__(self): ...
    def load(self, rom: bytes) -> None    # load program bytes at address 0x200
    def step(self) -> None                # fetch + execute exactly one instruction
    def framebuffer(self) -> bytes        # 2048 bytes, 64x32 row-major, each 0 or 1
```

- `framebuffer()` must return **exactly 2048 bytes**, row-major (index `y*64 + x`),
  each byte `0` (off) or `1` (on).
- `step()` executes **one** instruction per call.
- The grader calls `load(rom)` once, then `step()` a fixed number of times, then
  `framebuffer()`.

## Machine model

- **Memory**: 4096 bytes. Programs load at `0x200`.
- **Registers**: `V0`–`VF` (8-bit), `I` (address register), `PC` (starts `0x200`).
- **Stack**: for `CALL`/`RET`.
- **Timers**: `delay` and `sound`, both 8-bit. (No graded ROM reads them, but you
  must not crash on the timer opcodes.)
- **Display**: 64×32 monochrome. Sprites are XOR-drawn; `VF` is the collision flag.
- **Font**: standard hex-digit font, 5 bytes per glyph for `0`–`F`, loaded at
  `0x50`. `FX29` points `I` at the glyph for the digit in `VX`.

## Opcodes you must implement

```
00E0  00EE  1NNN  2NNN  3XNN  4XNN  5XY0  6XNN  7XNN
8XY0 8XY1 8XY2 8XY3 8XY4 8XY5 8XY6 8XY7 8XYE
9XY0  ANNN  BNNN  CXNN  DXYN  EX9E  EXA1
FX07  FX15  FX18  FX1E  FX29  FX33  FX55  FX65
```

## Quirks — pinned behavior (these are graded)

CHIP-8 has several opcodes with multiple historical interpretations. This eval
commits to the following choices. Getting them wrong will fail specific ROMs.

1. **Shifts are in-place.** `8XY6` does `VF = VX & 1; VX = VX >> 1`. `8XYE` does
   `VF = (VX >> 7) & 1; VX = (VX << 1) & 0xFF`. **`VY` is ignored** — do **not**
   use the COSMAC "shift `VY` into `VX`" behavior.

2. **`FX55` / `FX65` do not modify `I`.** After storing/loading `V0..VX`, `I` is
   left at its original value (no `I += X+1`).

3. **`DXYN` clips, with a wrapping start.** The starting coordinate wraps
   (`x % 64`, `y % 32`), but the sprite is then **clipped** at the right and
   bottom edges — pixels past the edge are **not** wrapped to the opposite side.

### Flag details

- `8XY4` (ADD): `VF = 1` if the sum exceeds `0xFF`, else `0`.
- `8XY5` (SUB): `VF = 1` if `VX >= VY` (no borrow), else `0`.
- `8XY7` (SUBN): `VF = 1` if `VY >= VX`, else `0`.
- `DXYN`: `VF = 1` if any set pixel was turned off (collision), else `0`.

## Input & RNG (no-input harness)

- The grader presses **no keys**. `EX9E` (skip if key down) never skips; `EXA1`
  (skip if key up) always skips. No ROM uses `FX0A`, so you need not implement
  blocking key waits.
- `CXNN` may use any RNG — graded ROMs never use it — but a deterministic,
  fixed-seed RNG is recommended for reproducibility.

## Scoring

ROMs are grouped into three weighted categories: **gameplay** (multi-opcode
programs, highest weight), **instruction** (targeted single-opcode checks), and
**quirk** (the behaviors above). Your score is the weighted fraction of ROMs
whose final framebuffer hash matches the golden, reported as `SCORE/100` with
per-category subtotals. An exception during a ROM counts as a failure of that
ROM only.
