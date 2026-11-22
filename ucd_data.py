"""
Tables read from the Unicode Character Database (UCD) for bidi.py.

Nothing in this file is part of the Unicode Bidirectional Algorithm itself;
it only reads the data files that the algorithm looks characters up in.

Two data files from the Unicode Character Database are kept, unchanged,
in the ucd/ folder next to this file:

  BidiBrackets.txt  - which characters form bracket pairs (used by rule N0)
  BidiMirroring.txt - which character to show in place of a mirrored one (rule L4)

To move to a newer Unicode version, replace both files with the ones from
https://www.unicode.org/Public/<version>/ucd/
"""

from pathlib import Path

UCD_DIRECTORY = Path(__file__).parent / "ucd"


def read_ucd_file(file_name: str) -> list[list[str]]:
    """
    Read a UCD data file and return its data lines, each split into fields.

    UCD files share a simple format: fields are separated by ';', and
    everything after '#' is a comment. Blank and comment-only lines are skipped.
    For example, this line from BidiBrackets.txt:
        0028; 0029; o # LEFT PARENTHESIS
    becomes ['0028', '0029', 'o'].
    """
    rows = []
    with open(UCD_DIRECTORY / file_name, encoding="utf-8") as ucd_file:
        for line in ucd_file:
            data = line.split("#")[0].strip()
            if data == "":
                continue
            fields = []
            for field in data.split(";"):
                fields.append(field.strip())
            rows.append(fields)
    return rows


def load_bracket_pairs() -> dict[int, int]:
    """
    Read BidiBrackets.txt and map each opening bracket to its closing bracket.

    Each line has three fields: code point; paired bracket; type, where the
    type is 'o' for an opening bracket and 'c' for a closing one.
    Only the 'o' lines are kept: the closing-to-opening map is simply the
    reverse of this one (see CLOSE_BRACKET_TO_OPEN below).
    """
    open_to_close = {}
    for code_point, paired_bracket, bracket_type in read_ucd_file("BidiBrackets.txt"):
        if bracket_type == "o":
            open_to_close[int(code_point, 16)] = int(paired_bracket, 16)
    return open_to_close


def load_mirror_pairs() -> dict[int, int]:
    """
    Read BidiMirroring.txt and map each character to its mirrored counterpart.

    Each line has two fields: code point; mirrored code point.
    The file lists both directions of every pair (e.g. '(' -> ')' and
    ')' -> '('), so no reversing is needed. Characters that have only an
    approximate ("best fit") mirror appear in the file as comments only,
    so they are not loaded.
    """
    mirrors = {}
    for code_point, mirrored_code_point in read_ucd_file("BidiMirroring.txt"):
        mirrors[int(code_point, 16)] = int(mirrored_code_point, 16)
    return mirrors


OPEN_BRACKET_TO_CLOSE = load_bracket_pairs()
CLOSE_BRACKET_TO_OPEN = {v: k for k, v in OPEN_BRACKET_TO_CLOSE.items()}
BIDI_MIRROR_TABLE     = load_mirror_pairs()
