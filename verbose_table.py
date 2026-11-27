"""
Before/after tables printed by bidi.py in verbose mode.

Nothing in this file is part of the Unicode Bidirectional Algorithm itself;
it only formats the tables that let a reader trace each rule application.
"""

import unicodedata

BOLD_YELLOW = "\033[1;33m"
RESET       = "\033[0m"

LEFT_TO_RIGHT_MARK = '‎'


def format_char_for_table(ch: str) -> str:
    """
    Return how a single character is shown in a cell of a verbose table.

    - Control and formatting characters (e.g. RLE, PDI) and whitespace have
      no useful visible form, so the cell is left blank; the Codepoint row
      still identifies them.
    - A combining mark would attach to the padding space before it, so it is
      shown on a dotted circle, as the Unicode code charts do.
    - A right-to-left character (bidi type R or AL) is followed by an
      invisible LEFT-TO-RIGHT MARK.  Without it, a viewer that applies the
      bidi algorithm itself (a Markdown preview, a web page, some terminals)
      would treat the spaces and "|" between neighbouring RTL characters as
      RTL too (rule N1) and display the whole stretch of the row reversed.
    """
    if not ch.isprintable() or ch.isspace():
        return ''
    if unicodedata.category(ch).startswith('M'):
        return '◌' + ch
    if unicodedata.bidirectional(ch) in ('R', 'AL'):
        return ch + LEFT_TO_RIGHT_MARK
    return ch


def display_width(text: str) -> int:
    """
    Return the number of terminal columns text occupies.

    Combining marks (category Mn, Me) and formatting characters such as the
    LEFT-TO-RIGHT MARK (category Cf) take up no column of their own, so
    len(text) would overcount them.
    """
    width = 0
    for ch in text:
        if unicodedata.category(ch) not in ('Mn', 'Me', 'Cf'):
            width += 1
    return width


def center_in_column(text: str, column_width: int) -> str:
    """
    Center text in a column, padding by display width instead of len().
    """
    padding = column_width - display_width(text)
    left_padding = padding // 2
    right_padding = padding - left_padding
    return ' ' * left_padding + text + ' ' * right_padding


def format_index_ranges(indices: list[int]) -> str:
    """
    Return a sorted list of character indices as ranges, e.g. [0, 1, 2, 7, 8]
    becomes "0-2, 7-8" and [4] becomes "4".
    """
    ranges = []
    start = indices[0]
    previous = indices[0]
    for index in indices[1:]:
        if index == previous + 1:
            previous = index
            continue
        ranges.append((start, previous))
        start = index
        previous = index
    ranges.append((start, previous))

    parts = []
    for first, last in ranges:
        if first == last:
            parts.append(str(first))
        else:
            parts.append(f"{first}-{last}")
    return ", ".join(parts)


def print_isolating_run_sequences(sequences: list[dict], chars: list) -> None:
    """
    Print the isolating run sequences found by rule X10, one line each:
    the sequence's level, the indices of its characters, and its sos/eos.
    Then list the characters removed by rule X9, which belong to no sequence.

    sequences is the list returned by bidi.get_isolating_run_sequences;
    chars is the list of bidi.CharacterInfo objects (only character_type is
    read, to find the removed characters, whose type is BN).
    """
    print("=== X10: Isolating Run Sequences ===")
    for seq in sequences:
        indices = format_index_ranges(seq['run_indices'])
        print(f"IRS level={seq['embedding_level']}: characters {indices}"
              f" | sos={seq['sos']}, eos={seq['eos']}")

    removed = []
    for ci in chars:
        if ci.character_type == 'BN':
            removed.append(ci.index)
    if removed:
        print(f"Removed by X9 (in no sequence): characters {format_index_ranges(removed)}")
    print()


def print_table(rule_name: str, chars: list,
                types_before: list[str], types_after: list[str],
                irs_label: str = '') -> None:
    """
    Print a before/after table showing the effect of a single rule application.

    chars is a list of bidi.CharacterInfo objects; only their index,
    character and embedding_level are read.  types_before and types_after are
    parallel lists of Bidi type strings, one entry per element of chars.
    irs_label, when provided, is appended to the header to identify the
    isolating run sequence (e.g. "IRS level=2").

    Prints nothing beyond the header line when types_before == types_after.
    Changed cells in the After row are highlighted with BOLD_YELLOW ANSI colour.
    """
    header = f"--- Rule {rule_name}"
    if irs_label:
        header += f" | {irs_label}"
    header += " ---"

    # Check if any changes occurred
    changed = types_before != types_after

    if not changed:
        print(f"{header} (no changes)")
        return

    print(header)

    # Build cell values for each column
    idx_cells = [str(ci.index) for ci in chars]
    codepoint_cells = [f"{ord(ci.character):04X}" for ci in chars]
    char_cells = [format_char_for_table(ci.character) for ci in chars]
    before_cells = list(types_before)
    after_cells = list(types_after)
    after_changed = [b != a for b, a in zip(types_before, types_after)]
    level_cells = [str(ci.embedding_level) for ci in chars]

    # Compute column widths
    col_widths = []
    for j in range(len(chars)):
        w = max(3,
                display_width(idx_cells[j]),
                display_width(codepoint_cells[j]),
                display_width(before_cells[j]),
                display_width(after_cells[j]),
                display_width(level_cells[j]))
        col_widths.append(w)

    # Wide enough for the longest row labels, "Codepoint" and "Character".
    label_width = 9

    def fmt_row(label, cells):
        row = f"{label:<{label_width}} |"
        for j, cell in enumerate(cells):
            row += f" {center_in_column(cell, col_widths[j])} |"
        return row

    print(fmt_row("Index", idx_cells))
    print(fmt_row("Codepoint", codepoint_cells))
    print(fmt_row("Character", char_cells))
    print(fmt_row("Before", before_cells))
    after_row = f"{'After':<{label_width}} |"
    for j, cell in enumerate(after_cells):
        padded = center_in_column(cell, col_widths[j])
        if after_changed[j]:
            after_row += f" {BOLD_YELLOW}{padded}{RESET} |"
        else:
            after_row += f" {padded} |"
    print(after_row)
    print(fmt_row("Level", level_cells))
    print()
