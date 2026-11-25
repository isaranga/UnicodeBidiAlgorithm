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

from bidi import apply_bidi_algorithm, split_into_paragraphs


# ============================================================
# Built-in examples
# ============================================================
#
# Each example is (text, title, what to watch for in the verbose output).
# Bidi control characters are written as tags such as [LRI], the same way
# you can write them in your own text (see expand_escapes_and_tags below).

EXAMPLES = [
    (
        "Hello, World!",
        "Pure LTR",
        "Everything stays at level 0, so L2 leaves the order unchanged.",
    ),
    (
        "שָׁלוֹם",
        "Pure RTL (Hebrew with nikkud)",
        "P2 finds R first, so the paragraph is RTL (level 1); W1 gives each vowel point (NSM) "
        "the type of the letter before it (R); L2 reverses the whole string, so each point "
        "now comes before its letter (rule L3 leaves fixing that to the renderer).",
    ),
    (
        "שלום 123 Hi",
        "Mixed RTL + digits + LTR",
        "N1 turns the space before the digits into R; I2 raises the digits and Latin letters to level 2.",
    ),
    (
        "سعر 1,000 ريال",
        "Arabic text with a number",
        "W2 turns the digits into AN because the last strong type before them is AL; "
        "W3 then turns AL into R, and W4 makes the comma AN because it sits between two AN.",
    ),
    (
        "Price: $100, 1.5%",
        "Prices and percentages",
        "W4 makes the dot in 1.5 EN; W5 makes $ and % EN because they touch a number; "
        "W6 makes the other separators ON; W7 turns every EN into L because the last strong type before it is L.",
    ),
    (
        "[LRE]Hello שלום[PDF]",
        "LRE/PDF explicit embedding",
        "X1-X9 put the text between LRE and PDF at level 2, so the Hebrew word ends up at level 3 after I1.",
    ),
    (
        "הוא אמר: ״[LRI]Car is מכונית in Hebrew[PDI]״.[RLM]",
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
    (
        "שלום\nHello",
        "Two paragraphs (P1)",
        "P1 splits the text after the newline; P2 then finds R in paragraph 1 (level 1) "
        "and L in paragraph 2 (level 0), so each paragraph gets its own direction.",
    ),
]


# ============================================================
# Writing bidi controls as tags and escapes
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


def show_controls_as_tags(text: str) -> str:
    """
    Quote text for printing, showing each bidi control character as its tag.

    This is the reverse of expand_escapes_and_tags for the controls, so the
    input and output lines can be read and copied back onto the command line.
    """
    shown = ''
    for ch in text:
        tag = None
        for name, control in CONTROL_TAGS.items():
            if ch == control:
                tag = name
        if tag is not None:
            shown += f'[{tag}]'
        else:
            shown += ch
    return repr(shown)


# ============================================================
# Running and printing
# ============================================================

DIRECTION_TO_LEVEL = {'auto': None, 'ltr': 0, 'rtl': 1}


def run_text(text: str, title: str, note: str | None, direction: str, brief: bool) -> None:
    """Split the text into paragraphs (rule P1) and run each one."""
    paragraphs = split_into_paragraphs(text)
    if len(paragraphs) == 1:
        run_paragraph(text, title, note, direction, brief)
        return

    print("=" * 60)
    print(title)
    print(f"Input: {show_controls_as_tags(text)}")
    if note:
        print(f"Watch for: {note}")
    print(f"P1 splits the text into {len(paragraphs)} paragraphs; each is run separately.")
    print()
    for number, paragraph in enumerate(paragraphs, start=1):
        run_paragraph(paragraph, f"{title}, paragraph {number}", None, direction, brief)


def run_paragraph(text: str, title: str, note: str | None, direction: str, brief: bool) -> None:
    print("=" * 60)
    print(title)
    print(f"Input: {show_controls_as_tags(text)}")
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
    print(f"Reordered text:   {show_controls_as_tags(reordered)}")
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
            "Text with several paragraphs (for example, several lines) is split by rule P1 "
            "and run one paragraph at a time."
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
            text = expand_escapes_and_tags(text)
            run_text(text, f"Example {number}: {title}", note, args.direction, args.brief)
        return

    if args.example is not None:
        if not 1 <= args.example <= len(EXAMPLES):
            parser.error(f"--example must be between 1 and {len(EXAMPLES)}")
        text, title, note = EXAMPLES[args.example - 1]
        text = expand_escapes_and_tags(text)
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
    if not user_text:
        parser.error("the text is empty")
    run_text(user_text, "Your text", None, args.direction, args.brief)


if __name__ == '__main__':
    main()
