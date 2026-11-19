#!/usr/bin/env python3
"""
Conformance tests for bidi.py against BidiCharacterTest.txt (Unicode 17.0.0).

Usage:
    python run_bidi_tests.py [TEST_FILE] [--max-failures N] [--lines START-END] [--fail-fast]

Defaults:
    TEST_FILE       BidiCharacterTest.txt
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

# Bidi types removed by rule X9. Characters with these original types are
# excluded from the expected levels and visual order fields in the test file.
X9_TYPES = frozenset({"RLE", "LRE", "RLO", "LRO", "PDF", "BN"})


@dataclass
class TestCase:
    line_number: int
    text: str             # original input string
    direction: int        # 0=force LTR, 1=force RTL, 2=auto
    para_level: int       # expected resolved paragraph embedding level
    # Field 3: one entry per character; None means the char was X9-removed.
    expected_levels: list[int | None]
    # Field 4: visual reordering indices into the original string (X9 chars omitted).
    expected_order: list[int]


def parse_test_file(path: str, line_range: tuple[int, int] | None):
    """Yield TestCase objects from the test file, optionally filtered to a line range."""
    start, end = line_range if line_range else (1, 10**9)
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            if lineno < start:
                continue
            if lineno > end:
                break
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = [field.strip() for field in line.split(";")]
            if len(fields) != 5:
                continue

            text = "".join([chr(int(cp, 16)) for cp in fields[0].split()])
            direction = int(fields[1])
            para_level = int(fields[2])
            expected_levels = [
                None if token == "x" else int(token)
                for token in fields[3].split()
            ]
            expected_order = [int(token) for token in fields[4].split()]

            yield TestCase(lineno, text, direction, para_level, expected_levels, expected_order)


def run_test(tc: TestCase) -> tuple[bool, str]:
    """
    Run a single test case. Returns (passed, failure_description).
    failure_description is empty when passed=True.
    """
    forced_level = None if tc.direction == 2 else tc.direction
    try:
        logical_levels, reordered_text, actual_para_level, visual_order = apply_bidi_algorithm(
            tc.text, paragraph_embedding_level=forced_level
        )
    except Exception:
        codepoints = " ".join(f"{ord(ch):04X}" for ch in tc.text)
        tb = traceback.format_exc().rstrip()
        return False, (
            f"FAIL line {tc.line_number} | dir={tc.direction} | {codepoints}\n"
            f"  exception:\n"
            + "\n".join(f"    {line}" for line in tb.splitlines())
        )

    # --- Sanity-check output lengths before any filtering ---
    if len(logical_levels) != len(tc.text):
        return False, (
            f"FAIL line {tc.line_number} | dir={tc.direction} | "
            f"logical_levels length {len(logical_levels)} != text length {len(tc.text)}"
        )
    if len(reordered_text) != len(tc.text):
        return False, (
            f"FAIL line {tc.line_number} | dir={tc.direction} | "
            f"reordered_text length {len(reordered_text)} != text length {len(tc.text)}"
        )
    if len(visual_order) != len(tc.text):
        return False, (
            f"FAIL line {tc.line_number} | dir={tc.direction} | "
            f"visual_order length {len(visual_order)} != text length {len(tc.text)}"
        )

    actual_levels = [
        level
        for ch, level in zip(tc.text, logical_levels)
        if unicodedata.bidirectional(ch) not in X9_TYPES
    ]
    expected_levels_filtered = [lvl for lvl in tc.expected_levels if lvl is not None]

    levels_ok = actual_levels == expected_levels_filtered

    # --- Compare paragraph level (only meaningful for auto-detect) ---
    para_level_ok = actual_para_level == tc.para_level

    # --- Compare visual order (by logical index, so L4 mirroring doesn't matter) ---
    actual_order = [
        i for i in visual_order
        if unicodedata.bidirectional(tc.text[i]) not in X9_TYPES
    ]

    order_ok = actual_order == tc.expected_order

    if levels_ok and order_ok and para_level_ok:
        return True, ""

    codepoints = " ".join(f"{ord(ch):04X}" for ch in tc.text)
    lines = [f"FAIL line {tc.line_number} | dir={tc.direction} | {codepoints}"]
    if not para_level_ok:
        lines.append(f"  para_level expected: {tc.para_level}  actual: {actual_para_level}")
    if not levels_ok:
        exp_str, act_str = _highlight_diff(expected_levels_filtered, actual_levels)
        lines.append(f"  levels   expected: {exp_str}")
        lines.append(f"           actual:   {act_str}")
    if not order_ok:
        exp_str, act_str = _highlight_diff(tc.expected_order, actual_order)
        lines.append(f"  order    expected indices: {exp_str}")
        lines.append(f"           actual indices:   {act_str}")
    return False, "\n".join(lines)


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
    parts = value.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--lines must be in START-END format, e.g. 44-82")
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError("--lines START and END must be integers")
    if start > end:
        raise argparse.ArgumentTypeError("--lines START must be <= END")
    return start, end


def main():
    parser = argparse.ArgumentParser(
        description="Run BidiCharacterTest.txt conformance tests against bidi.py"
    )
    parser.add_argument(
        "test_file",
        nargs="?",
        default=str(Path(__file__).parent / "BidiCharacterTest.txt"),
        help="Path to BidiCharacterTest.txt (default: next to this script)",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of failures to print (default: 20)",
    )
    parser.add_argument(
        "--lines",
        type=parse_line_range,
        metavar="START-END",
        help="Only run test cases in this line range, e.g. --lines 44-82",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately after the first failure",
    )
    args = parser.parse_args()

    run_tests(args.test_file, args.max_failures, args.lines, args.fail_fast)


if __name__ == "__main__":
    main()
