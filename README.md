# Unicode Bidirectional Algorithm in Python

A readable, pure-Python implementation of the [Unicode Bidirectional Algorithm (UAX #9)](https://www.unicode.org/reports/tr9/), targeting Unicode 15.1.

The bidi algorithm decides how text that mixes left-to-right scripts (Latin, Cyrillic, …) with right-to-left scripts (Hebrew, Arabic, …) is laid out on screen. This project is meant for **learning how that algorithm works**. It favours clarity over speed or brevity:

- The whole algorithm is in one file, [bidi.py](bidi.py), with no dependencies beyond the Python standard library.
- Each UAX #9 rule has its own function, named after the rule (`_apply_w1`, `_apply_n0`, `_apply_l2`, …), so you can read the code next to the spec.
- A **verbose mode** prints a before/after table every time a rule is applied, so you can follow a string through the algorithm step by step.

## Quick start

Requires Python 3 (developed with 3.13). No installation is needed:

```bash
git clone <this repo>
cd UnicodeBidiAlgorithm
python bidi.py
```

This runs a set of example strings (pure LTR, pure RTL, mixed text with digits, explicit embeddings, isolates, and brackets) through the full algorithm with verbose output.

## Using it as a library

```python
from bidi import apply_bidi_algorithm

levels, reordered, para_level = apply_bidi_algorithm("Hello שלום")
```

`apply_bidi_algorithm(text, verbose=False, paragraph_embedding_level=None)` returns a tuple:

| Value | Meaning |
|-------|---------|
| `levels` | The resolved embedding level of each character, in logical (input) order |
| `reordered` | The text in visual (display) order |
| `para_level` | The paragraph embedding level: `0` = left-to-right, `1` = right-to-left |

By default the paragraph direction is detected from the first strong character (rules P2–P3). Pass `paragraph_embedding_level=0` or `1` to force it.

## Tracing the algorithm

Pass `verbose=True` to see every rule as it runs. Rules that change nothing print a single line; rules that do change something print a table showing each character's index, the character, its type (or level) before and after the rule, and its embedding level. Changed cells are highlighted in the terminal.

```python
apply_bidi_algorithm("שלום 123 Hi", verbose=True)
```

```text
=== Phase P: Paragraph Embedding Level = 1 ===
...
--- Rule N1 | IRS level=1 ---
Idx      |   0    |   1    |   2    |   3    |  4  |  5  |  6  |  7  |  8  |  9  | 10  |
Char     | U+05E9 | U+05DC | U+05D5 | U+05DD |     |  1  |  2  |  3  |     |  H  |  i  |
Before   |   R    |   R    |   R    |   R    | WS  | EN  | EN  | EN  | WS  |  L  |  L  |
After    |   R    |   R    |   R    |   R    |  R  | EN  | EN  | EN  | WS  |  L  |  L  |
Level    |   1    |   1    |   1    |   1    |  1  |  1  |  1  |  1  |  1  |  1  |  1  |
...
--- Rule I2 ---
Idx      |   0    |   1    |   2    |   3    |  4  |  5  |  6  |  7  |  8  |  9  | 10  |
Char     | U+05E9 | U+05DC | U+05D5 | U+05DD |     |  1  |  2  |  3  |     |  H  |  i  |
Before   |   1    |   1    |   1    |   1    |  1  |  1  |  1  |  1  |  1  |  1  |  1  |
After    |   1    |   1    |   1    |   1    |  1  |  2  |  2  |  2  |  1  |  2  |  2  |
Level    |   1    |   1    |   1    |   1    |  1  |  2  |  2  |  2  |  1  |  2  |  2  |
...
```

Here N1 turns the space between the Hebrew word and the digits into `R`, because it sits between two right-to-left contexts (numbers count as R for this rule). I2 then raises the digits and the Latin letters to level 2, so they display left-to-right inside the right-to-left paragraph.

## How the code is organised

`apply_bidi_algorithm` runs six phases in order. Each matches a section of UAX #9:

| Phase | Function | UAX #9 rules | What it does |
|-------|----------|--------------|--------------|
| P | `determine_paragraph_embedding_level` | P2–P3 | Picks the paragraph direction |
| X | `apply_explicit_levels` | X1–X9 | Applies explicit embeddings, overrides and isolates (LRE, RLO, LRI, PDF, PDI, …) |
| W | `apply_weak_rules` | W1–W7 | Resolves weak types such as numbers and separators |
| N | `apply_neutral_rules` | N0–N2 | Resolves neutrals: brackets first (N0), then spaces and punctuation |
| I | `apply_implicit_rules` | I1–I2 | Turns the resolved types into final embedding levels |
| L | `apply_reorder_rules` | L1–L4 | Resets trailing whitespace, then reverses runs into visual order |

Some things to know when reading the code:

- **`CharacterInfo`** is the record passed through every phase. `original_type` is the character's Unicode bidi class and never changes; `character_type` is a working copy that the rules update.
- **Isolating run sequences** (definition BD13) are what phases W and N work on. `get_isolating_run_sequences` builds them by linking runs of the same level across an isolate (LRI/RLI/FSI … PDI), and attaches the `sos`/`eos` types at each end.
- **Bracket pairs** for rule N0 are found by `_find_bracket_pairs`, using tables taken from [BidiBrackets.txt](https://www.unicode.org/Public/15.1.0/ucd/BidiBrackets.txt) (Unicode 15.1).

## Scope and caveats

- The input is treated as a single paragraph; the algorithm does not split text at paragraph separators (rule P1).
- Line breaking is not handled: the L rules treat the whole input as one line.
- Bidi classes come from Python's `unicodedata` module, so they follow the Unicode version built into your Python, which may be newer than 15.1.
- Rule L3 (combining marks) takes no action. The spec leaves this to the renderer.
- Rule L4 (mirroring, for example `(` → `)` in right-to-left text) runs after the reordered string is built, so the returned `reordered` text is not mirrored. Verbose mode still shows what L4 would change.

## Conformance tests

The implementation is checked against the official Unicode test files. You don't need these to understand the algorithm, but they're there if you want to change the code:

- [BidiCharacterTest.txt](https://www.unicode.org/Public/15.1.0/ucd/BidiCharacterTest.txt) (Unicode 15.1) tests real codepoints.
- [BidiTest.txt](https://www.unicode.org/Public/17.0.0/ucd/BidiTest.txt) (Unicode 17.0.0) tests abstract sequences of bidi types.

```bash
python tests/run_bidi_tests.py        # BidiCharacterTest.txt
python tests/run_bidi_type_tests.py   # BidiTest.txt
```

Both runners accept `--max-failures N`, `--lines START-END` and `--fail-fast`.
