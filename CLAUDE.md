# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A pure-Python implementation of the Unicode Bidirectional Algorithm (UAX #9), targeting Unicode 15.1. The entire implementation lives in a single file: [bidi.py](bidi.py).

No external dependencies — only Python stdlib (`unicodedata`, `dataclasses`).

## Design philosophy

This project is **educational**. The primary goal is to make the algorithm easy to read, understand, and trace — not to be fast or concise.

- Prefer explicit loops over complex list comprehensions when the loop body has logic.
- Avoid "clever" or compact expressions; spell out what is happening.
- Each UAX #9 rule gets its own function, named after the rule, so the code can be read alongside the spec.
- Verbose mode exists specifically to let readers trace every rule application step by step.

When modifying code, keep this priority order: **clarity > correctness > performance**.

## Conformance testing

`BidiCharacterTest.txt` (Unicode 15.1) and `run_bidi_tests.py` are verification tools used to check the correctness of `bidi.py` against the official Unicode test suite. They are **not** part of the educational project — readers do not need to read, run, or even know about them in order to understand the Unicode Bidirectional Algorithm.

```bash
python run_bidi_tests.py [--max-failures N] [--lines START-END] [--fail-fast]
```

## Commands

**Run the built-in demo** (five example strings with verbose output):
```bash
python bidi.py
```

**Use as a library:**
```python
from bidi import apply_bidi_algorithm
levels, reordered = apply_bidi_algorithm("Hello שלום", verbose=False)
```

## Architecture

### Data model

`CharacterInfo` is the central dataclass passed through every phase. It has two type fields:
- `original_type` — set once from `unicodedata.bidirectional()`, never mutated
- `character_type` — working copy mutated in-place by each phase

### Algorithm phases

`apply_bidi_algorithm` orchestrates six phases in order, each corresponding to a section of UAX #9:

| Phase | Function | UAX #9 rules |
|-------|----------|--------------|
| P | `determine_paragraph_embedding_level` | P2–P3 |
| X | `apply_explicit_levels` | X1–X9 |
| W | `apply_weak_rules` | W1–W7 |
| N | `apply_neutral_rules` | N0–N2 |
| I | `apply_implicit_rules` | I1–I2 |
| L | `apply_reorder_rules` | L1–L4 |

Phases W and N operate on **isolating run sequences** (BD13), computed by `get_isolating_run_sequences`. Each IRS chains contiguous level runs that are linked by isolate initiators (LRI/RLI/FSI) to their matching PDI, and carries `sos`/`eos` context types.

The W and N phases each delegate to private per-rule helpers (`_apply_w1`…`_apply_w7`, `_apply_n0`, `_apply_n1_n2`). The L phase similarly delegates to `_apply_l1`…`_apply_l4`.

Bracket pair detection for N0 is handled by `_find_bracket_pairs`, using `OPEN_BRACKET_TO_CLOSE` / `CLOSE_BRACKET_TO_OPEN` tables derived from BidiBrackets.txt (Unicode 15.1).

### Verbose mode

Every phase and rule function accepts `verbose=True`. When enabled, `print_table` prints a before/after table for each rule application, showing character index, character, type transition, and embedding level.

### Return value

`apply_bidi_algorithm` returns `(logical_levels, reordered_text)`:
- `logical_levels` — embedding levels captured after phase I (before L1 resets)
- `reordered_text` — visually reordered string after all L rules
