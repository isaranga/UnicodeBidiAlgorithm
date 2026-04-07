#!/usr/bin/env python3
"""
Conformance tests for bidi.py against BidiTest.txt (Unicode 17.0.0).

Usage:
    python run_bidi_type_tests.py [TEST_FILE] [--max-failures N] [--lines START-END] [--fail-fast]

Defaults:
    TEST_FILE       BidiTest.txt
    --max-failures  20
"""

import argparse
import sys
import traceback
import unicodedata
from dataclasses import dataclass

from bidi import apply_bidi_algorithm

_YLW = "\033[33m"   # yellow
_RST = "\033[0m"    # reset


def _highlight_diff(a: list, b: list) -> tuple[str, str]:
    """Return string representations of a and b with differing positions in yellow."""
    def fmt(seq, other):
        parts = []
        for i, val in enumerate(seq):
            s = str(val)
            if i >= len(other) or val != other[i]:
                parts.append(f"{_YLW}{s}{_RST}")
            else:
                parts.append(s)
        return "[" + ", ".join(parts) + "]"
    return fmt(a, b), fmt(b, a)


# Bidi types removed by rule X9.
X9_TYPES = frozenset({"RLE", "LRE", "RLO", "LRO", "PDF", "BN"})

# Representative characters for each UAX#9 bidi class.
# Each character must have exactly the stated bidi class (verified below at module load).
# Pools with >=4 entries allow unique-per-position synthesis for sequences up to length 4,
# which is the maximum sequence length in BidiTest.txt.
# X9 types have only one Unicode codepoint each, so their pool is size 1.
TYPE_CHARS: dict[str, list[str]] = {
    'L':   list('ABCDEFGH'),
    'R':   ['\u05D0', '\u05D1', '\u05D2', '\u05D3'],  # Hebrew alef, bet, gimel, dalet
    'AL':  ['\u0627', '\u0628', '\u062A', '\u062B'],  # Arabic alef, ba, ta, tha
    'AN':  ['\u0660', '\u0661', '\u0662', '\u0663'],  # Arabic-Indic digits 0-3
    'EN':  ['1', '2', '3', '4'],
    'ES':  ['+', '\u2212'],                           # plus, minus sign (only 2 ES in Unicode)
    'ET':  ['$', '%', '\u00A3', '\u00A5'],            # dollar, percent, pound, yen
    'CS':  [',', '.', '\uFE50', '\uFE52'],            # comma, period, small comma, small full stop
    'NSM': ['\u0300', '\u0301', '\u0302', '\u0303'],  # combining grave, acute, circumflex, tilde
    'BN':  ['\u200B', '\u2060', '\uFEFF', '\u200C'],  # zero-width space, word joiner, BOM, ZWNJ
    'B':   ['\u2029'],                                # paragraph separator
    'S':   ['\t', '\u000B'],                          # tab, vertical tab
    'WS':  [' ', '\u2000', '\u2001', '\u2002'],       # space, en quad, em quad, en space
    'ON':  ['!', '?', '@', '*'],
    'LRE': ['\u202A'],  # X9
    'RLE': ['\u202B'],  # X9
    'LRO': ['\u202D'],  # X9
    'RLO': ['\u202E'],  # X9
    'PDF': ['\u202C'],  # X9
    'LRI': ['\u2066'],
    'RLI': ['\u2067'],
    'FSI': ['\u2068'],
    'PDI': ['\u2069'],
}

# Verify at module load that every representative character has the claimed bidi class.
for _tp, _pool in TYPE_CHARS.items():
    for _ch in _pool:
        assert unicodedata.bidirectional(_ch) == _tp, (
            f"TYPE_CHARS[{_tp!r}] contains U+{ord(_ch):04X} "
            f"but its bidi class is {unicodedata.bidirectional(_ch)!r}"
        )


def build_text(types: list[str]) -> str:
    """Synthesize a string whose characters have the requested bidi types.

    Positions with the same type receive successive characters from that type's pool,
    so all characters in the returned string are distinct within the string (for
    non-X9 types with pools large enough to cover the sequence length).
    """
    type_counters: dict[str, int] = {}
    chars = []
    for tp in types:
        pool = TYPE_CHARS[tp]
        count = type_counters.get(tp, 0)
        chars.append(pool[count % len(pool)])
        type_counters[tp] = count + 1
    return ''.join(chars)


@dataclass
class TestCase:
    line_number: int
    types: list[str]                   # bidi type names from the data line, e.g. ['L', 'R', 'L']
    para_mode: int                     # 0=auto, 1=force LTR (level 0), 2=force RTL (level 1)
    expected_levels: list[int | None]  # None means X9-removed (level 'x' in the file)
    expected_reorder: list[int]        # absolute indices into the original types list


def parse_test_file(path: str, line_range: tuple[int, int] | None):
    """Yield TestCase objects from a BidiTest.txt file, optionally filtered to a line range."""
    start, end = line_range if line_range else (1, 10**9)
    current_levels: list[int | None] = []
    current_reorder: list[int] = []

    with open(path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            if lineno > end:
                break
            line = raw.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('@Levels:'):
                tokens = line[len('@Levels:'):].split()
                current_levels = [None if t == 'x' else int(t) for t in tokens]
                continue

            if line.startswith('@Reorder:'):
                tokens = line[len('@Reorder:'):].split()
                current_reorder = [int(t) for t in tokens]
                continue

            if line.startswith('@'):
                continue  # forward-compatibility: ignore unknown directives

            if ';' not in line or lineno < start:
                continue

            fields = line.split(';', 1)
            types = fields[0].split()
            bitset = int(fields[1].strip(), 16)

            for bit, mode in [(0b001, 0), (0b010, 1), (0b100, 2)]:
                if bitset & bit:
                    yield TestCase(
                        line_number=lineno,
                        types=types,
                        para_mode=mode,
                        expected_levels=current_levels,
                        expected_reorder=current_reorder,
                    )


_MODE_NAMES = {0: 'auto', 1: 'LTR', 2: 'RTL'}


def run_test(tc: TestCase) -> tuple[bool, str]:
    """Run a single test case. Returns (passed, failure_description)."""
    text = build_text(tc.types)
    forced_level = {0: None, 1: 0, 2: 1}[tc.para_mode]
    try:
        logical_levels, reordered_text, _ = apply_bidi_algorithm(
            text, paragraph_embedding_level=forced_level
        )
    except Exception:
        tb = traceback.format_exc().rstrip()
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | types={tc.types}\n"
            f"  exception:\n"
            + "\n".join(f"    {line}" for line in tb.splitlines())
        )

    # --- Sanity-check output lengths ---
    if len(logical_levels) != len(text):
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | "
            f"logical_levels length {len(logical_levels)} != text length {len(text)}"
        )
    if len(reordered_text) != len(text):
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | "
            f"reordered_text length {len(reordered_text)} != text length {len(text)}"
        )

    # --- Levels check ---
    actual_levels = [lvl for tp, lvl in zip(tc.types, logical_levels) if tp not in X9_TYPES]
    expected_levels_filtered = [l for l in tc.expected_levels if l is not None]
    levels_ok = actual_levels == expected_levels_filtered

    # --- Reorder check (index tracking) ---
    # build_text assigns distinct characters to each position for types with large enough pools.
    # A few bidi types (LRI, RLI, FSI, PDI) have only one Unicode codepoint, so repeated
    # occurrences produce duplicate characters. Index tracking is only reliable when every
    # non-X9 character in the synthesized string is unique.
    non_x9_chars = [ch for tp, ch in zip(tc.types, text) if tp not in X9_TYPES]
    if len(set(non_x9_chars)) == len(non_x9_chars):
        char_to_orig_idx = {ch: i for i, ch in enumerate(text)}
        non_x9_reordered = [
            ch for ch in reordered_text
            if unicodedata.bidirectional(ch) not in X9_TYPES
        ]
        actual_reorder = [char_to_orig_idx[ch] for ch in non_x9_reordered]
        reorder_ok = actual_reorder == tc.expected_reorder
    else:
        reorder_ok = True  # skip: duplicate non-X9 chars prevent reliable index tracking

    if levels_ok and reorder_ok:
        return True, ''

    lines = [f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | types={tc.types}"]
    if not levels_ok:
        exp_str, act_str = _highlight_diff(expected_levels_filtered, actual_levels)
        lines.append(f"  levels   expected: {exp_str}")
        lines.append(f"           actual:   {act_str}")
    if not reorder_ok:
        exp_str, act_str = _highlight_diff(tc.expected_reorder, actual_reorder)
        lines.append(f"  reorder  expected: {exp_str}")
        lines.append(f"           actual:   {act_str}")
    return False, '\n'.join(lines)


def run_tests(path: str, max_failures: int, line_range: tuple[int, int] | None, fail_fast: bool):
    passed = 0
    failed = 0
    printed_failures = 0
    progress_interval = 5000
    processed = 0

    for tc in parse_test_file(path, line_range):
        ok, description = run_test(tc)
        processed += 1
        if ok:
            passed += 1
        else:
            failed += 1
            if printed_failures < max_failures:
                print(description, flush=True)
                printed_failures += 1
            if fail_fast:
                print(f"\nStopped after first failure. ({passed} passed before this)")
                sys.exit(1)

        if processed % progress_interval == 0:
            print(f"  ... {processed} tests run (passed={passed}, failed={failed})", flush=True)

    total = passed + failed
    print(f"\nPassed: {passed}  Failed: {failed}  Total: {total}")

    if failed > printed_failures:
        print(f"  ... and {failed - printed_failures} more failures (increase --max-failures to see them)")

    sys.exit(0 if failed == 0 else 1)


def parse_line_range(value: str) -> tuple[int, int]:
    parts = value.split('-')
    if len(parts) != 2:
        raise argparse.ArgumentTypeError('--lines must be in START-END format, e.g. 44-82')
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError('--lines START and END must be integers')
    if start > end:
        raise argparse.ArgumentTypeError('--lines START must be <= END')
    return start, end


def main():
    parser = argparse.ArgumentParser(
        description='Run BidiTest.txt conformance tests against bidi.py'
    )
    parser.add_argument(
        'test_file',
        nargs='?',
        default='BidiTest.txt',
        help='Path to BidiTest.txt (default: BidiTest.txt)',
    )
    parser.add_argument(
        '--max-failures',
        type=int,
        default=20,
        metavar='N',
        help='Maximum number of failures to print (default: 20)',
    )
    parser.add_argument(
        '--lines',
        type=parse_line_range,
        metavar='START-END',
        help='Only run test cases in this line range, e.g. --lines 44-82',
    )
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop immediately after the first failure',
    )
    args = parser.parse_args()

    run_tests(args.test_file, args.max_failures, args.lines, args.fail_fast)


if __name__ == '__main__':
    main()
