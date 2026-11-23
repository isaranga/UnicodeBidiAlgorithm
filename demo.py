"""
Command-line demo for the Unicode Bidirectional Algorithm in bidi.py.

This file only handles the command line: choosing the input text, reading
escapes and tags in it, and printing the results. It holds no algorithm logic.

Usage:
    python bidi.py                    List the built-in examples
    python bidi.py --all              Run every built-in example
    python bidi.py --example 3        Run built-in example 3
    python bidi.py "Hello שלום"       Run your own text
    python bidi.py --file input.txt   Run the text in a UTF-8 file

Options for every mode:
    --direction {auto,ltr,rtl}   Paragraph direction (default: auto, rules P2-P3)
    --brief                      Print only the results, not the rule-by-rule tables
"""

import argparse
import re
import sys
import unicodedata

from bidi import apply_bidi_algorithm


# ============================================================
# Built-in examples
# ============================================================
#
# Each example is (text, title, what to watch for in the verbose output).

EXAMPLES = [
    (
        "Hello, World!",
        "Pure LTR",
        "Everything stays at level 0, so L2 leaves the order unchanged.",
    ),
    (
        "שלום",
        "Pure RTL (Hebrew: shalom)",
        "P2 finds R first, so the paragraph is RTL (level 1); L2 reverses the whole string.",
    ),
    (
        "שלום 123 Hi",
        "Mixed RTL + digits + LTR",
        "N1 turns the space before the digits into R; I2 raises the digits and Latin letters to level 2.",
    ),
    (
        "‪Hello שלום‬",
        "LRE/PDF explicit embedding",
        "X1-X9 put the text between LRE and PDF at level 2, so the Hebrew word ends up at level 3 after I1.",
    ),
    (
        "הוא אמר: ״⁦Car is מכונית in Hebrew⁩״.‏",
        "LRI/PDI isolate",
        "The text between LRI and PDI forms its own isolating run sequence (level 2), "
        "separate from the Hebrew sentence around it (level 1).",
    ),
    (
        "Hello שלום (עולם)",
        "Brackets (N0) and mirroring (L4)",
        "N0 makes both parentheses R, because they hold Hebrew text that follows Hebrew; "
        "L4 then mirrors them in the reordered text.",
    ),
]


# ============================================================
# Reading escapes and tags in user text
# ============================================================
#
# Bidi control characters are invisible and hard to type on a command line,
# so user text may name them with a tag such as [RLI], or give any character
# as an escape such as ⁧.

CONTROL_TAGS = {
    'LRE': '‪',  # LEFT-TO-RIGHT EMBEDDING
    'RLE': '‫',  # RIGHT-TO-LEFT EMBEDDING
    'PDF': '‬',  # POP DIRECTIONAL FORMATTING
    'LRO': '‭',  # LEFT-TO-RIGHT OVERRIDE
    'RLO': '‮',  # RIGHT-TO-LEFT OVERRIDE
    'LRI': '⁦',  # LEFT-TO-RIGHT ISOLATE
    'RLI': '⁧',  # RIGHT-TO-LEFT ISOLATE
    'FSI': '⁨',  # FIRST STRONG ISOLATE
    'PDI': '⁩',  # POP DIRECTIONAL ISOLATE
    'LRM': '‎',  # LEFT-TO-RIGHT MARK
    'RLM': '‏',  # RIGHT-TO-LEFT MARK
    'ALM': '؜',  # ARABIC LETTER MARK
}


def _replace_tag(match: re.Match) -> str:
    name = match.group(1)
    if name in CONTROL_TAGS:
        return CONTROL_TAGS[name]
    # Not a known tag (for example "[x]"): keep the text as written.
    return match.group(0)


def _replace_escape(match: re.Match) -> str:
    hex_digits = match.group(1) or match.group(2)
    return chr(int(hex_digits, 16))


def expand_escapes_and_tags(text: str) -> str:
    """Replace [TAG] names and \\uXXXX / \\UXXXXXXXX escapes with real characters."""
    text = re.sub(r'\[([A-Z]{3})\]', _replace_tag, text)
    text = re.sub(r'\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})', _replace_escape, text)
    return text


# ============================================================
# Splitting user text into paragraphs
# ============================================================

def split_into_paragraphs(text: str) -> list[str]:
    """
    Split text after each paragraph separator (bidi type B, such as a newline).

    bidi.py does not implement rule P1 and treats its input as one paragraph,
    so the demo does the splitting itself. As P1 says, each separator stays
    at the end of the paragraph it closes. CR LF counts as a single separator.
    """
    paragraphs = []
    current = ''
    for i, ch in enumerate(text):
        current += ch
        if unicodedata.bidirectional(ch) != 'B':
            continue
        next_is_lf = i + 1 < len(text) and text[i + 1] == '\n'
        if ch == '\r' and next_is_lf:
            continue  # the LF that follows ends this paragraph
        paragraphs.append(current)
        current = ''
    if current:
        paragraphs.append(current)
    return paragraphs


# ============================================================
# Running and printing
# ============================================================

DIRECTION_TO_LEVEL = {'auto': None, 'ltr': 0, 'rtl': 1}


def run_text(text: str, title: str, note: str | None, direction: str, brief: bool) -> None:
    print("=" * 60)
    print(title)
    print(f"Input: {repr(text)}")
    if note:
        print(f"Watch for: {note}")
    print()

    levels, reordered, para_level, visual_order = apply_bidi_algorithm(
        text,
        verbose=not brief,
        paragraph_embedding_level=DIRECTION_TO_LEVEL[direction],
    )

    if not brief:
        print()
    print(f"Paragraph level:  {para_level}")
    print(f"Embedding levels: {levels}")
    print(f"Visual order:     {visual_order}")
    print(f"Reordered text:   {repr(reordered)}")
    print()


def list_examples() -> None:
    print("Built-in examples:")
    for number, (text, title, _note) in enumerate(EXAMPLES, start=1):
        print(f"  {number}. {title:<34} {repr(text)}")
    print()
    print("Try:")
    print("  python bidi.py --example 3          run one example, showing every rule")
    print("  python bidi.py --all                run all the examples")
    print('  python bidi.py "Hello שלום"         run your own text')
    print('  python bidi.py "[RLI]Hi[PDI] שלום"  name control characters with tags (or \\u2067)')
    print("  python bidi.py --file input.txt     run the text in a UTF-8 file")
    print()
    print("Add --brief to skip the tables, or --direction ltr/rtl to set the paragraph direction.")
    print("Run python bidi.py --help for details.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python bidi.py",
        description="Trace the Unicode Bidirectional Algorithm (UAX #9) rule by rule.",
        epilog=(
            "Bidi control characters can be written as tags: "
            + ", ".join(f"[{name}]" for name in CONTROL_TAGS)
            + ". Any character can also be written as \\uXXXX or \\UXXXXXXXX. "
            "Text with several paragraphs (for example, several lines) is run one paragraph at a time."
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("text", nargs="?", help="your own text to run")
    source.add_argument("--all", action="store_true", help="run every built-in example")
    source.add_argument("--example", type=int, metavar="N", help="run built-in example N")
    source.add_argument("--file", metavar="PATH", help="run the text in a UTF-8 file")
    parser.add_argument(
        "--direction",
        choices=["auto", "ltr", "rtl"],
        default="auto",
        help="paragraph direction (default: auto, detected by rules P2-P3)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="print only the results, not the rule-by-rule tables",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    # Windows consoles may not use UTF-8 by default, which makes printing
    # Hebrew or Arabic fail.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.all:
        for number, (text, title, note) in enumerate(EXAMPLES, start=1):
            run_text(text, f"Example {number}: {title}", note, args.direction, args.brief)
        return

    if args.example is not None:
        if not 1 <= args.example <= len(EXAMPLES):
            parser.error(f"--example must be between 1 and {len(EXAMPLES)}")
        text, title, note = EXAMPLES[args.example - 1]
        run_text(text, f"Example {args.example}: {title}", note, args.direction, args.brief)
        return

    if args.file is not None:
        try:
            with open(args.file, encoding="utf-8") as f:
                user_text = f.read()
        except (OSError, UnicodeDecodeError) as error:
            parser.error(f"cannot read {args.file}: {error}")
    elif args.text is not None:
        user_text = args.text
    else:
        list_examples()
        return

    user_text = expand_escapes_and_tags(user_text)
    paragraphs = split_into_paragraphs(user_text)
    if not paragraphs:
        parser.error("the text is empty")

    if len(paragraphs) == 1:
        run_text(paragraphs[0], "Your text", None, args.direction, args.brief)
        return

    print(f"The text has {len(paragraphs)} paragraphs; each is run separately (rule P1).")
    print()
    for number, paragraph in enumerate(paragraphs, start=1):
        run_text(paragraph, f"Paragraph {number}", None, args.direction, args.brief)


if __name__ == '__main__':
    main()
