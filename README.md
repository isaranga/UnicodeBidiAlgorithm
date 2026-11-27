# Unicode Bidirectional Algorithm in Python

A readable, pure-Python implementation of the [Unicode Bidirectional Algorithm (UAX #9)](https://www.unicode.org/reports/tr9/), targeting Unicode 17.0.

The bidi algorithm decides how text that mixes left-to-right scripts (Latin, Cyrillic, …) with right-to-left scripts (Hebrew, Arabic, …) is laid out on screen. This project is meant for **learning how that algorithm works**. It favours clarity over speed or brevity:

- The whole algorithm is in one file, [bidi.py](bidi.py), with no dependencies beyond the Python standard library. The two Unicode data files it needs are kept, unchanged, in [ucd/](ucd/), and are read by [ucd_data.py](ucd_data.py). The tables printed in verbose mode are formatted separately, in [verbose_table.py](verbose_table.py), and the command-line demo lives in [demo.py](demo.py). None of these files holds any algorithm logic; they are kept apart so that file reading, formatting and command-line code don't clutter the algorithm.
- Each UAX #9 rule has its own function, named after the rule (`_apply_w1`, `_apply_n0`, `_apply_l2`, …), so you can read the code next to the spec.
- A **verbose mode** prints a before/after table every time a rule is applied, so you can follow a string through the algorithm step by step.

## Quick start

Requires Python 3.10+ (developed with 3.13). No installation is needed:

```bash
git clone <this repo>
cd UnicodeBidiAlgorithm
python bidi.py
```

This lists the built-in examples (pure LTR, pure RTL, mixed text with digits, Arabic text with a number, prices and percentages, explicit embeddings, isolates, brackets, and two paragraphs) and shows how to run them:

```bash
python bidi.py --example 3          # run one example, printing a table for every rule
python bidi.py --all                # run all the examples
python bidi.py "Hello שלום"         # run your own text
python bidi.py --file input.txt     # run the text in a UTF-8 file
```

Each example comes with a note on what to look for in its output. Two options work in every mode:

- `--brief` prints only the results (levels, visual order, reordered text) without the rule-by-rule tables.
- `--direction ltr` or `--direction rtl` sets the paragraph direction instead of detecting it. Running the same text both ways is a good way to see what the paragraph level changes.

Bidi control characters are invisible and hard to type, so your text can name them with tags: `[LRE]`, `[RLE]`, `[PDF]`, `[LRO]`, `[RLO]`, `[LRI]`, `[RLI]`, `[FSI]`, `[PDI]`, `[LRM]`, `[RLM]`, `[ALM]`. Any character can also be written as `\uXXXX`. The built-in examples are written the same way, and the demo prints control characters as tags in its input and output lines. For example:

```bash
python bidi.py "[RLI]Hello[PDI] שלום"
```

Text with several paragraphs (for example, several lines in a file) is split into paragraphs by rule P1 and run one paragraph at a time. The demo itself lives in [demo.py](demo.py), so that `bidi.py` holds only the algorithm.

## Using it as a library

```python
from bidi import apply_bidi_algorithm

levels, reordered, para_level, visual_order = apply_bidi_algorithm("Hello שלום")
```

`apply_bidi_algorithm(text, verbose=False, paragraph_embedding_level=None)` returns a tuple:

| Value | Meaning |
|-------|---------|
| `levels` | The resolved embedding level of each character, in logical (input) order |
| `reordered` | The text in visual (display) order, with mirroring (rule L4) applied |
| `para_level` | The paragraph embedding level: `0` = left-to-right, `1` = right-to-left |
| `visual_order` | For each visual position, the index of the input character shown there |

By default the paragraph direction is detected from the first strong character (rules P2–P3). Pass `paragraph_embedding_level=0` or `1` to force it.

`apply_bidi_algorithm` handles one paragraph. If your text may contain several (for example, several lines), split it first with `split_into_paragraphs` (rule P1) and run each part; each paragraph then gets its own direction:

```python
from bidi import apply_bidi_algorithm, split_into_paragraphs

for paragraph in split_into_paragraphs("שלום\nHello"):
    levels, reordered, para_level, visual_order = apply_bidi_algorithm(paragraph)
```

## Tracing the algorithm

Pass `verbose=True` to see every rule as it runs. Rules that change nothing print a single line; rules that do change something print a table showing each character's index, its code point, the character itself, its type (or level) before and after the rule, and its embedding level. Changed cells are highlighted in the terminal. Phase X prints two tables, one for the levels it assigns and one for the types it changes, so that an embedding or isolate shows up even when no type changes. Rule X10 then lists the isolating run sequences, one line each, with their level, characters and `sos`/`eos`, followed by the characters removed by X9, which belong to no sequence.

```python
apply_bidi_algorithm("שלום 123 Hi", verbose=True)
```

```text
=== Phase P: Paragraph Embedding Level = 1 ===
...
--- Rule N1 | IRS level=1 ---
Index     |  0   |  1   |  2   |  3   |  4   |  5   |  6   |  7   |  8   |  9   |  10  |
Codepoint | 05E9 | 05DC | 05D5 | 05DD | 0020 | 0031 | 0032 | 0033 | 0020 | 0048 | 0069 |
Character |  ש‎   |  ל‎   |  ו‎   |  ם‎   |      |  1   |  2   |  3   |      |  H   |  i   |
Before    |  R   |  R   |  R   |  R   |  WS  |  EN  |  EN  |  EN  |  WS  |  L   |  L   |
After     |  R   |  R   |  R   |  R   |  R   |  EN  |  EN  |  EN  |  WS  |  L   |  L   |
Level     |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |
...
--- Rule I2 ---
Index     |  0   |  1   |  2   |  3   |  4   |  5   |  6   |  7   |  8   |  9   |  10  |
Codepoint | 05E9 | 05DC | 05D5 | 05DD | 0020 | 0031 | 0032 | 0033 | 0020 | 0048 | 0069 |
Character |  ש‎   |  ל‎   |  ו‎   |  ם‎   |      |  1   |  2   |  3   |      |  H   |  i   |
Before    |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |  1   |
After     |  1   |  1   |  1   |  1   |  1   |  2   |  2   |  2   |  1   |  2   |  2   |
Level     |  1   |  1   |  1   |  1   |  1   |  2   |  2   |  2   |  1   |  2   |  2   |
...
```

Here N1 turns the space between the Hebrew word and the digits into `R`, because it sits between two right-to-left contexts (numbers count as R for this rule). I2 then raises the digits and the Latin letters to level 2, so they display left-to-right inside the right-to-left paragraph.

## How the code is organised

Rule P1 comes first: `split_into_paragraphs` cuts the text into paragraphs after each paragraph separator. `apply_bidi_algorithm` then runs these steps in order on one paragraph. Each matches a section of UAX #9:

| Phase | Function | UAX #9 rules | What it does |
|-------|----------|--------------|--------------|
| P | `determine_paragraph_embedding_level` | P2–P3 | Picks the paragraph direction |
| X | `apply_explicit_levels` | X1–X9 | Applies explicit embeddings, overrides and isolates (LRE, RLO, LRI, PDF, PDI, …) |
| X10 | `get_isolating_run_sequences` | X10 (BD13) | Splits the paragraph into isolating run sequences |
| W | `apply_weak_rules` | W1–W7 | Resolves weak types such as numbers and separators |
| N | `apply_neutral_rules` | N0–N2 | Resolves neutrals: brackets first (N0), then spaces and punctuation |
| I | `apply_implicit_rules` | I1–I2 | Turns the resolved types into final embedding levels |
| L | `apply_reorder_rules` | L1–L4 | Resets trailing whitespace, then reverses runs into visual order |

Some things to know when reading the code:

- **`CharacterInfo`** is the record passed through every phase. `original_type` is the character's Unicode bidi class and never changes; `character_type` is a working copy that the rules update.
- **Isolating run sequences** (definition BD13) are what phases W and N work on. Rule X10 finds them: `get_isolating_run_sequences` builds them by linking runs of the same level across an isolate (LRI/RLI/FSI … PDI), and attaches the `sos`/`eos` types at each end. `apply_bidi_algorithm` computes them once and passes them to both phases; verbose mode lists them. Characters removed by rule X9 (embedding controls such as LRE and PDF, and type BN) are kept in the text, but they belong to no sequence, so the W and N rules never see them, just as if they had been removed. UAX #9 also applies rules I1–I2 per sequence, but they look only at each character's own type and level, so `apply_implicit_rules` applies them to the whole paragraph at once, with the same result.
- UAX #9 takes each sequence through W, N and I before moving to the next one. The code instead runs phase W on every sequence, then phase N, then phase I. Each sequence's rules look only at that sequence's characters (and its `sos`/`eos`), so the order makes no difference.
- **Bracket pairs** for rule N0 are found by `_find_bracket_pairs`, using pairs read from [ucd/BidiBrackets.txt](ucd/BidiBrackets.txt).
- **Mirrored characters** for rule L4 are read from [ucd/BidiMirroring.txt](ucd/BidiMirroring.txt).
- Both files are copied unchanged from the [Unicode Character Database](https://www.unicode.org/Public/17.0.0/ucd/) (currently Unicode 17.0.0). To update them, replace them with newer versions.

## Scope and caveats

- `apply_bidi_algorithm` treats its input as a single paragraph. Split longer text with `split_into_paragraphs` (rule P1) first, as the command-line demo does. The official conformance files contain no paragraph separator except at the end of a test, so they do not check P1.
- Line breaking is not handled: the L rules treat the whole input as one line.
- Bidi classes come from Python's `unicodedata` module, so they follow the Unicode version built into your Python, which may be older than 17.0 (for example, Python 3.14 uses Unicode 16.0). Characters added in later Unicode versions may then get the wrong bidi class.
- Rule L3 (combining marks) takes no action. The spec leaves this to the renderer.
- Rule L4 (mirroring, for example `(` → `)` in right-to-left text) swaps the characters listed in BidiMirroring.txt. Some mirrored characters, such as `∛`, have no mirrored counterpart character, so drawing them mirrored is left to the renderer.

## Conformance tests

The implementation is checked against the official Unicode test files. You don't need these to understand the algorithm, but they're there if you want to change the code:

- [BidiCharacterTest.txt](https://www.unicode.org/Public/17.0.0/ucd/BidiCharacterTest.txt) (Unicode 17.0.0) tests real codepoints.
- [BidiTest.txt](https://www.unicode.org/Public/17.0.0/ucd/BidiTest.txt) (Unicode 17.0.0) tests abstract sequences of bidi types.

```bash
python tests/run_bidi_tests.py        # BidiCharacterTest.txt
python tests/run_bidi_type_tests.py   # BidiTest.txt
```

Both runners accept `--max-failures N`, `--lines START-END` and `--fail-fast`.
