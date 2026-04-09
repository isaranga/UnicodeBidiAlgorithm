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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
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
# Pool sizes are set to cover the maximum repeat count of each type observed in BidiTest.txt
# (e.g. L appears up to 14 times in one sequence, R up to 13, etc.).
# Types with inherently few Unicode codepoints (B, S, ES, LRI/RLI/FSI/PDI) cannot be expanded
# further; repeated occurrences of those types will still cause the reorder check to be skipped.
# X9 types have only one Unicode codepoint each, so their pool is size 1.
TYPE_CHARS: dict[str, list[str]] = {
    'L':   list('ABCDEFGHIJKLMNOPQRST'),              # 20 chars; max repeat in file: 14
    'R':   [chr(c) for c in range(0x05D0, 0x05DF)],  # Hebrew alef..mem (15 letters); max repeat: 13
    'AL':  [chr(c) for c in range(0x0627, 0x062F)],  # Arabic alef..dal (8 letters); max repeat: 8
    'AN':  [chr(c) for c in range(0x0660, 0x0666)],  # Arabic-Indic digits 0-5 (6); max repeat: 6
    'EN':  list('0123456789'),                        # ASCII digits; max repeat: 8
    'ES':  ['+', '-', '\u207A', '\u207B'],            # plus, hyphen-minus, superscript plus/minus
    'ET':  ['$', '%', '\u00A3', '\u00A5'],            # dollar, percent, pound, yen
    'CS':  [',', '.', '\uFE50', '\uFE52'],            # comma, period, small comma, small full stop
    'NSM': ['\u0300', '\u0301', '\u0302', '\u0303'],  # combining grave, acute, circumflex, tilde
    'BN':  ['\u200B', '\u2060', '\uFEFF', '\u200C'],  # zero-width space, word joiner, BOM, ZWNJ
    'B':   ['\u2029'],                                # paragraph separator (only 1 in Unicode)
    'S':   ['\t', '\u000B', '\u001F'],                # tab, vertical tab, unit separator
    'WS':  [' ', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003', '\u2004'],  # spaces; max repeat: 7
    'ON':  ['!', '?', '@', '*', '=', '~', '|'],      # safe punctuation (no brackets); max repeat: 7
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


def run_test(tc: TestCase) -> tuple[bool, str, bool]:
    """Run a single test case. Returns (passed, failure_description, reorder_skipped)."""
    text = build_text(tc.types)
    chars_repr = [repr(ch) for ch in text]
    forced_level = {0: None, 1: 0, 2: 1}[tc.para_mode]
    try:
        logical_levels, reordered_text, _ = apply_bidi_algorithm(
            text, paragraph_embedding_level=forced_level
        )
    except Exception:
        tb = traceback.format_exc().rstrip()
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | types={tc.types}\n"
            f"  chars={chars_repr}\n"
            f"  exception:\n"
            + "\n".join(f"    {line}" for line in tb.splitlines())
        ), False

    # --- Sanity-check output lengths ---
    if len(logical_levels) != len(text):
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | "
            f"logical_levels length {len(logical_levels)} != text length {len(text)}\n"
            f"  chars={chars_repr}"
        ), False
    if len(reordered_text) != len(text):
        return False, (
            f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | "
            f"reordered_text length {len(reordered_text)} != text length {len(text)}\n"
            f"  chars={chars_repr}"
        ), False

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
    reorder_skipped = len(set(non_x9_chars)) != len(non_x9_chars)
    if not reorder_skipped:
        char_to_orig_idx = {ch: i for i, ch in enumerate(text)}
        non_x9_reordered = [
            ch for ch in reordered_text
            if unicodedata.bidirectional(ch) not in X9_TYPES
        ]
        actual_reorder = [char_to_orig_idx[ch] for ch in non_x9_reordered]
        reorder_ok = actual_reorder == tc.expected_reorder
    else:
        reorder_ok = True

    if levels_ok and reorder_ok:
        return True, '', reorder_skipped

    lines = [
        f"FAIL line {tc.line_number} | dir={_MODE_NAMES[tc.para_mode]} | types={tc.types}",
        f"  chars={chars_repr}",
    ]
    if not levels_ok:
        exp_str, act_str = _highlight_diff(expected_levels_filtered, actual_levels)
        lines.append(f"  levels   expected: {exp_str}")
        lines.append(f"           actual:   {act_str}")
    if not reorder_ok:
        exp_str, act_str = _highlight_diff(tc.expected_reorder, actual_reorder)
        lines.append(f"  reorder  expected: {exp_str}")
        lines.append(f"           actual:   {act_str}")
    return False, '\n'.join(lines), False


def run_tests(path: str, max_failures: int, line_range: tuple[int, int] | None, fail_fast: bool):
    passed = 0
    failed = 0
    reorder_skipped = 0
    printed_failures = 0
    progress_interval = 5000
    processed = 0

    for tc in parse_test_file(path, line_range):
        ok, description, skipped = run_test(tc)
        processed += 1
        if skipped:
            reorder_skipped += 1
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
    if reorder_skipped:
        print(f"  (reorder check skipped for {reorder_skipped} tests)")

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
        default=str(Path(__file__).parent / 'BidiTest.txt'),
        help='Path to BidiTest.txt (default: next to this script)',
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
