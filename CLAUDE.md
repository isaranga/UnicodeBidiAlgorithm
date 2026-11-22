# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A pure-Python implementation of the Unicode Bidirectional Algorithm (UAX #9), targeting Unicode 17.0. The entire algorithm lives in a single file: [bidi.py](bidi.py). The tables printed in verbose mode are formatted by [verbose_table.py](verbose_table.py), which holds no algorithm logic. The algorithm uses lookup tables built from two Unicode Character Database files, kept unchanged in [ucd/](ucd/): `BidiBrackets.txt` and `BidiMirroring.txt` (currently Unicode 17.0.0). They are read by [ucd_data.py](ucd_data.py), which also holds no algorithm logic. To update the data, replace these files; do not hand-copy their contents into code.

No external dependencies — only Python stdlib (`unicodedata`, `dataclasses`, `pathlib`).

## Design philosophy

This project is **educational**. The primary goal is to make the algorithm easy to read, understand, and trace — not to be fast or concise.

- Prefer explicit loops over complex list comprehensions when the loop body has logic.
- Avoid "clever" or compact expressions; spell out what is happening.
- Each UAX #9 rule gets its own function, named after the rule, so the code can be read alongside the spec.
- Verbose mode exists specifically to let readers trace every rule application step by step.

When modifying code, keep this priority order: **clarity > correctness > performance**.

## Conformance testing

The test files and their runners are verification tools used to check the correctness of `bidi.py` against the official Unicode test suite. They are **not** part of the educational project — readers do not need to read, run, or even know about them in order to understand the Unicode Bidirectional Algorithm.

`tests/BidiCharacterTest.txt` (Unicode 17.0.0) tests the algorithm against real Unicode codepoints:
```bash
python tests/run_bidi_tests.py [--max-failures N] [--lines START-END] [--fail-fast]
```

`tests/BidiTest.txt` (Unicode 17.0.0) tests the algorithm against abstract bidi type sequences. The runner synthesizes representative Unicode characters for each bidi type, then verifies both embedding levels and visual reordering:
```bash
python tests/run_bidi_type_tests.py [--max-failures N] [--lines START-END] [--fail-fast]
```

## Commands

**Run the built-in demo** (six example strings with verbose output):
```bash
python bidi.py
```

**Use as a library:**
```python
from bidi import apply_bidi_algorithm
levels, reordered, para_level, visual_order = apply_bidi_algorithm("Hello שלום", verbose=False)
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

The W and N phases each delegate to private per-rule helpers (`_apply_w1`…`_apply_w7`, `_apply_n0`, `_apply_n1`, `_apply_n2`). The L phase similarly delegates to `_apply_l1`…`_apply_l4`.

Bracket pair detection for N0 is handled by `_find_bracket_pairs`, using `OPEN_BRACKET_TO_CLOSE` / `CLOSE_BRACKET_TO_OPEN` tables. L4 mirroring uses `BIDI_MIRROR_TABLE`. All three tables are imported from `ucd_data.py`, which builds them at import time: `load_bracket_pairs` reads `ucd/BidiBrackets.txt` and `load_mirror_pairs` reads `ucd/BidiMirroring.txt`, both through `read_ucd_file`. A comment above the import in `bidi.py` describes the tables and the rules that use them.

### Verbose mode

Every phase function (and `_apply_i1`/`_apply_i2`) accepts `verbose=True`; the per-rule W, N and L helpers do not, and their phase function prints on their behalf. When enabled, `print_table` (in `verbose_table.py`, together with the helpers below) prints a before/after table for each rule application, with rows for character index, code point, the character itself, the type (or level, or position) before and after the rule, and embedding level. Columns are always in logical order, including the L2 and L4 tables, where Before/After give each character's position before and after reordering.

Characters in table cells go through `format_char_for_table`: controls and whitespace are left blank, combining marks are shown on a dotted circle, and each R/AL character is followed by an invisible LEFT-TO-RIGHT MARK so that bidi-aware viewers (Markdown previews, GitHub) don't reverse runs of the row. Cells are sized and centered by `display_width`/`center_in_column`, not `len()`, because those marks take no column on screen. The tracing example in README.md is copied from real output (LRMs included); update it whenever the table format changes.

### Return value

`apply_bidi_algorithm` returns `(logical_levels, reordered_text, paragraph_level, visual_order)`:
- `logical_levels` — embedding levels captured after L1 resets (before L2–L4 reordering)
- `reordered_text` — visually reordered string after all L rules, including L4 mirroring
- `paragraph_level` — resolved paragraph embedding level (0 = LTR, 1 = RTL)
- `visual_order` — logical index of the character at each visual position (`reordered_text[k]` comes from `text[visual_order[k]]`); the conformance runners compare this, not characters, so mirroring and duplicate characters don't affect the order check
