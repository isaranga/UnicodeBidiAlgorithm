# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A pure-Python implementation of the Unicode Bidirectional Algorithm (UAX #9), targeting Unicode 17.0. The entire algorithm lives in a single file: [bidi.py](bidi.py). The tables printed in verbose mode are formatted by [verbose_table.py](verbose_table.py), which holds no algorithm logic. The algorithm uses lookup tables built from two Unicode Character Database files, kept unchanged in [ucd/](ucd/): `BidiBrackets.txt` and `BidiMirroring.txt` (currently Unicode 17.0.0). They are read by [ucd_data.py](ucd_data.py), which also holds no algorithm logic. The command-line demo lives in [demo.py](demo.py), again with no algorithm logic; the `__main__` block of `bidi.py` only calls `demo.main()`. To update the data, replace these files; do not hand-copy their contents into code.

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

**Run the demo** (`demo.py`, reached through `bidi.py`):
```bash
python bidi.py                     # list the nine built-in examples and usage hints
python bidi.py --all               # run every example with verbose output
python bidi.py --example N         # run one example
python bidi.py "text"              # run your own text
python bidi.py --file PATH         # run the text in a UTF-8 file
```
Every mode accepts `--brief` (results only, no tables) and `--direction {auto,ltr,rtl}` (passed as `paragraph_embedding_level`). User text (argument or file) and the built-in `EXAMPLES` may contain `[LRI]`-style tags for the bidi controls and `\uXXXX` / `\UXXXXXXXX` escapes; `expand_escapes_and_tags` turns them into characters before the text is run. Write controls in `EXAMPLES` as tags, not escapes. `show_controls_as_tags` does the reverse for the printed Input and Reordered text lines. `run_text` splits every text (user text and built-in examples alike) with `split_into_paragraphs` from `bidi.py` (rule P1) and runs each paragraph separately through `run_paragraph`. Each built-in example in `EXAMPLES` carries a "Watch for" note; if you change an example, check that its note still matches the verbose output. `main()` calls `sys.stdout.reconfigure(encoding="utf-8")` so Hebrew/Arabic output works in Windows consoles.

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

Rule P1 is `split_into_paragraphs`, which works on the raw string and runs before everything else: it splits after each type-B character (CR LF counts as one), keeping the separator at the end of its paragraph. `apply_bidi_algorithm` handles **one paragraph** (a B may only be its last character); callers with longer text call it once per paragraph. The conformance files contain no B except at the end, so P1 is not covered by them.

`apply_bidi_algorithm` orchestrates these steps in order, each corresponding to a section of UAX #9:

| Phase | Function | UAX #9 rules |
|-------|----------|--------------|
| P | `determine_paragraph_embedding_level` | P2–P3 (P1 is applied beforehand) |
| X | `apply_explicit_levels` | X1–X9 |
| X10 | `get_isolating_run_sequences` | X10 (BD13) |
| W | `apply_weak_rules` | W1–W7 |
| N | `apply_neutral_rules` | N0–N2 |
| I | `apply_implicit_rules` | I1–I2 |
| L | `apply_reorder_rules` | L1–L4 |

Phases W and N operate on **isolating run sequences** (BD13), computed by `get_isolating_run_sequences`. Each IRS chains contiguous level runs that are linked by isolate initiators (LRI/RLI/FSI) to their matching PDI, and carries `sos`/`eos` context types. `apply_bidi_algorithm` computes the list once (rule X10), right after phase X, and passes it to `apply_weak_rules` and `apply_neutral_rules`. The spec takes each IRS through W, N and I in turn, but the code runs each phase across all sequences. This is equivalent because no rule reads outside its own IRS (except through `sos`/`eos`). Phase I is not given the sequences: I1/I2 depend only on each character's own type and level, so `apply_implicit_rules` runs over the whole paragraph. Comments in `apply_bidi_algorithm` and `apply_implicit_rules` explain both points.

The W and N phases each delegate to private per-rule helpers (`_apply_w1`…`_apply_w7`, `_apply_n0`, `_apply_n1`, `_apply_n2`). The L phase similarly delegates to `_apply_l1`…`_apply_l4`.

Bracket pair detection for N0 is handled by `_find_bracket_pairs`, using `OPEN_BRACKET_TO_CLOSE` / `CLOSE_BRACKET_TO_OPEN` tables. L4 mirroring uses `BIDI_MIRROR_TABLE`. All three tables are imported from `ucd_data.py`, which builds them at import time: `load_bracket_pairs` reads `ucd/BidiBrackets.txt` and `load_mirror_pairs` reads `ucd/BidiMirroring.txt`, both through `read_ucd_file`. A comment above the import in `bidi.py` describes the tables and the rules that use them.

### Verbose mode

Every phase function (and `_apply_i1`/`_apply_i2`) accepts `verbose=True`; the per-rule W, N and L helpers do not, and their phase function prints on their behalf. When enabled, `print_table` (in `verbose_table.py`, together with the helpers below) prints a before/after table for each rule application, with rows for character index, code point, the character itself, the type (or level, or position) before and after the rule, and embedding level. `print_table` decides "(no changes)" by comparing only the Before/After rows, so Phase X prints two tables: "X1-X8 (levels)" (Before is the paragraph level from X1) and "X1-X9 (types)" (overrides, FSI resolution, X9's BN). Without the levels table, an isolate or embedding with no override would show as "(no changes)". After phase X, `apply_bidi_algorithm` calls `print_isolating_run_sequences` (also in `verbose_table.py`), which prints the X10 sequences one line each: level, character indices as ranges, `sos`/`eos`. Columns are always in logical order, including the L2 and L4 tables, where Before/After give each character's position before and after reordering.

Characters in table cells go through `format_char_for_table`: controls and whitespace are left blank, combining marks are shown on a dotted circle, and each R/AL character is followed by an invisible LEFT-TO-RIGHT MARK so that bidi-aware viewers (Markdown previews, GitHub) don't reverse runs of the row. Cells are sized and centered by `display_width`/`center_in_column`, not `len()`, because those marks take no column on screen. The tracing example in README.md is copied from real output (LRMs included); update it whenever the table format changes.

### Return value

`apply_bidi_algorithm` returns `(logical_levels, reordered_text, paragraph_level, visual_order)`:
- `logical_levels` — embedding levels captured after L1 resets (before L2–L4 reordering)
- `reordered_text` — visually reordered string after all L rules, including L4 mirroring
- `paragraph_level` — resolved paragraph embedding level (0 = LTR, 1 = RTL)
- `visual_order` — logical index of the character at each visual position (`reordered_text[k]` comes from `text[visual_order[k]]`); the conformance runners compare this, not characters, so mirroring and duplicate characters don't affect the order check
