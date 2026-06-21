# CHIP-8 Eval

A self-contained environment + automated grader for evaluating AI coding agents,
modeled on Mechanize's **GBA Eval** (where agents get 24h to write a Game Boy
Advance emulator, then are graded black-box against the Mesen2 reference
emulator). This is the same idea scaled down to a **CHIP-8 emulator** — small
enough to read in one sitting, so the focus is on the **eval design**, not the
emulator.

The thesis is the same as GBA Eval's: don't grade an agent by reading its code or
matching against a rubric. Grade it by **running its artifact and checking real
observable behavior** against a trusted reference.

## How it works

1. A **reference core** ([reference/chip8_ref.py](reference/chip8_ref.py)) is the
   ground truth — a correct, fully deterministic CHIP-8 implementation.
2. **Hand-authored test ROMs** ([roms.py](roms.py)) each compute something and
   draw the result to the 64×32 screen, so a wrong opcode yields a wrong picture.
3. [gen_golden.py](gen_golden.py) runs every ROM on the reference and records the
   SHA-256 of the final framebuffer into `golden.json` — the answer key.
4. [grader.py](grader.py) loads a candidate's `Chip8` **by file path**, runs each
   ROM for a fixed cycle budget, hashes the framebuffer, and compares to the
   golden. It never reads candidate source and treats candidate exceptions as a
   failed ROM, not a grader crash.

The agent-facing spec and the interface contract live in [TASK.md](TASK.md).

## Mapping to GBA Eval

| CHIP-8 Eval component | GBA Eval equivalent |
| --- | --- |
| [TASK.md](TASK.md) — interface contract + pinned quirks | The task brief: "write a GBA emulator with this API" |
| `Chip8` interface (`load`/`step`/`framebuffer`) | The emulator API the agent must implement |
| [reference/chip8_ref.py](reference/chip8_ref.py) | **Mesen2** — the trusted reference emulator |
| [roms.py](roms.py) — deterministic test ROMs | Curated test ROMs / game scenarios |
| `golden.json` (framebuffer hashes) | Reference traces captured from Mesen2 |
| [grader.py](grader.py) — black-box, hash-compare | The black-box behavioral grader |
| framebuffer SHA-256 comparison | Frame / memory-state comparison vs reference |
| gameplay / instruction / quirk categories + weights | Weighted test tiers (gameplay weighted highest) |
| [candidates/reference_solution.py](candidates/reference_solution.py) | Sanity check: a correct submission scores 100 |
| [candidates/buggy_solution.py](candidates/buggy_solution.py) | A flawed submission earns a localized partial score |

## Design choices worth noting

- **Behavioral, not structural.** Each ROM ends by *drawing* its computed result.
  A correct value produces the right glyphs; a wrong opcode produces a different
  framebuffer and a different hash. We never inspect registers or source.
- **Deterministic by construction.** Fixed cycle budgets, a no-input harness
  (`EX9E`/`EXA1` see all keys released, no `FX0A`), a seeded RNG, and ROMs that
  halt in a jump-to-self loop make overshooting the cycle budget harmless. Same
  input → same hash, every run.
- **Pinned quirks.** CHIP-8 opcodes with multiple historical interpretations
  (in-place shifts, `FX55`/`FX65` and `I`, `DXYN` clip-vs-wrap) are fixed in
  TASK.md and enforced by dedicated quirk ROMs — so "it works on my favorite
  ROM set" isn't enough.
- **Weighted categories** let the score reflect priorities: broad multi-opcode
  *gameplay* programs count for more than single-opcode checks.
- **Failure localization.** Because each ROM targets a capability, the per-ROM
  and per-category breakdown tells you *what* broke, not just *that* something
  did — see the buggy candidate below.

## Running it

```sh
# 1. Generate the golden answer key from the reference core.
python3 gen_golden.py

# 2. Grade a correct candidate -> 100/100.
python3 grader.py candidates/reference_solution.py

# 3. Grade a buggy candidate -> partial score, with the broken ROMs named.
python3 grader.py candidates/buggy_solution.py

# 4. Debug: render any ROM's framebuffer as ASCII.
python3 grader.py candidates/reference_solution.py --ascii bcd_draw
```

### Expected results

`reference_solution.py` scores **100.0/100**.

`buggy_solution.py` injects two realistic mistakes — `8XY4` drops the `VF` carry,
and `8XY6` uses COSMAC "shift VY into VX" instead of in-place — and scores
**85.2/100**, failing exactly the two ROMs that isolate those behaviors:

```
add_carry_vf       instruction   2  FAIL      <- bug (a): 8XY4 carry
quirk_shr          quirk         2  FAIL      <- bug (b): 8XY6 in-place shift
```

The `--ascii bcd_draw` view shows the emulator actually drawing `137`:

```
··█··████·████··
·██·····█····█··
··█··████···█···
··█·····█··█····
·███·████··█····
```

## Files

```
TASK.md                          agent-facing task spec + interface contract
reference/chip8_ref.py           correct CHIP-8 core = ground truth
roms.py                          hand-authored deterministic test ROMs + assembler
gen_golden.py                    runs ROMs on reference -> golden.json
grader.py                        black-box behavioral grader (+ ascii_fb helper)
golden.json                      generated answer key (hashes per ROM)
candidates/reference_solution.py a correct candidate (scores 100)
candidates/buggy_solution.py     a plausibly-buggy candidate (partial score)
```
