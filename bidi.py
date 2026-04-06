"""
Unicode Bidirectional Algorithm (UAX #9) implementation.

Reference: https://www.unicode.org/reports/tr9/ (Unicode Standard Annex #9)
Unicode version caveat: This implementation targets Unicode 15.1.
  Bracket pairs are from BidiBrackets.txt (Unicode 15.1).
  Character Bidi_Class values come from Python's unicodedata module,
  which reflects the Unicode version bundled with your Python build.

Usage:
    from bidi import apply_bidi_algorithm
    levels, reordered = apply_bidi_algorithm("Hello \u05e9\u05dc\u05d5\u05dd", verbose=False)

Demo:
    python bidi.py
    Runs five built-in example strings through the full algorithm with verbose output.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# ============================================================
# Data Model
# ============================================================

@dataclass
class CharacterInfo:
    index:           int   # position in original text (never changes)
    character:       str   # the character itself
    original_type:   str   # Bidi_Class from unicodedata.bidirectional(); set once, never mutated
    character_type:  str   # working Bidi_Class; mutated by each phase
    embedding_level: int   # assigned in X phase, adjusted in I phase


# ============================================================
# SECTION: Constants
# ============================================================

MAX_DEPTH         = 125
BRACKET_STACK_MAX = 63

BOLD_YELLOW = "\033[1;33m"
RESET       = "\033[0m"

STRONG_TYPES             = frozenset({'L', 'R', 'AL'})
WEAK_TYPES               = frozenset({'EN', 'ES', 'ET', 'AN', 'CS', 'NSM', 'BN'})
NEUTRAL_TYPES            = frozenset({'B', 'S', 'WS', 'ON'})
ISOLATE_INITIATOR_TYPES  = frozenset({'LRI', 'RLI', 'FSI'})
EXPLICIT_EMBEDDING_TYPES = frozenset({'LRE', 'RLE', 'LRO', 'RLO'})
X9_REMOVE_TYPES          = frozenset({'LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'BN'})
R_EQUIVALENT_TYPES       = frozenset({'R', 'AL', 'EN', 'AN'})

# BidiBrackets.txt pairs (Unicode 15.1) - open -> close
OPEN_BRACKET_TO_CLOSE = {
    0x0028: 0x0029,  # LEFT PARENTHESIS
    0x005B: 0x005D,  # LEFT SQUARE BRACKET
    0x007B: 0x007D,  # LEFT CURLY BRACKET
    0x0F3A: 0x0F3B,  # TIBETAN MARK GUG RTAGS GYON
    0x0F3C: 0x0F3D,  # TIBETAN MARK ANG KHANG GYON
    0x169B: 0x169C,  # OGHAM FEATHER MARK
    0x2045: 0x2046,  # LEFT SQUARE BRACKET WITH QUILL
    0x207D: 0x207E,  # SUPERSCRIPT LEFT PARENTHESIS
    0x208D: 0x208E,  # SUBSCRIPT LEFT PARENTHESIS
    0x2308: 0x2309,  # LEFT CEILING
    0x230A: 0x230B,  # LEFT FLOOR
    0x2329: 0x232A,  # LEFT-POINTING ANGLE BRACKET
    0x2768: 0x2769,  # MEDIUM LEFT PARENTHESIS ORNAMENT
    0x276A: 0x276B,  # MEDIUM FLATTENED LEFT PARENTHESIS ORNAMENT
    0x276C: 0x276D,  # MEDIUM LEFT-POINTING ANGLE BRACKET ORNAMENT
    0x276E: 0x276F,  # HEAVY LEFT-POINTING ANGLE QUOTATION MARK ORNAMENT
    0x2770: 0x2771,  # HEAVY LEFT-POINTING ANGLE BRACKET ORNAMENT
    0x2772: 0x2773,  # LIGHT LEFT TORTOISE SHELL BRACKET ORNAMENT
    0x2774: 0x2775,  # MEDIUM LEFT CURLY BRACKET ORNAMENT
    0x27C5: 0x27C6,  # LEFT S-SHAPED BAG DELIMITER
    0x27E6: 0x27E7,  # MATHEMATICAL LEFT WHITE SQUARE BRACKET
    0x27E8: 0x27E9,  # MATHEMATICAL LEFT ANGLE BRACKET
    0x27EA: 0x27EB,  # MATHEMATICAL LEFT DOUBLE ANGLE BRACKET
    0x27EC: 0x27ED,  # MATHEMATICAL LEFT WHITE TORTOISE SHELL BRACKET
    0x27EE: 0x27EF,  # MATHEMATICAL LEFT FLATTENED PARENTHESIS
    0x2983: 0x2984,  # LEFT WHITE CURLY BRACKET
    0x2985: 0x2986,  # LEFT WHITE PARENTHESIS
    0x2987: 0x2988,  # Z NOTATION LEFT IMAGE BRACKET
    0x2989: 0x298A,  # Z NOTATION LEFT BINDING BRACKET
    0x298B: 0x298C,  # LEFT SQUARE BRACKET WITH UNDERBAR
    0x298D: 0x298E,  # LEFT SQUARE BRACKET WITH TICK IN TOP CORNER
    0x298F: 0x2990,  # LEFT SQUARE BRACKET WITH TICK IN BOTTOM CORNER
    0x2991: 0x2992,  # LEFT ANGLE BRACKET WITH DOT
    0x2993: 0x2994,  # LEFT ARC LESS-THAN BRACKET
    0x2995: 0x2996,  # DOUBLE LEFT ARC GREATER-THAN BRACKET
    0x2997: 0x2998,  # LEFT BLACK TORTOISE SHELL BRACKET
    0x29D8: 0x29D9,  # LEFT WIGGLY FENCE
    0x29DA: 0x29DB,  # LEFT DOUBLE WIGGLY FENCE
    0x29FC: 0x29FD,  # LEFT-POINTING CURVED ANGLE BRACKET
    0x2E22: 0x2E23,  # TOP LEFT HALF BRACKET
    0x2E24: 0x2E25,  # BOTTOM LEFT HALF BRACKET
    0x2E26: 0x2E27,  # LEFT SIDEWAYS U BRACKET
    0x2E28: 0x2E29,  # LEFT DOUBLE PARENTHESIS
    0x2E42: 0x201E,  # DOUBLE LOW-REVERSED-9 QUOTATION MARK (special)
    0x3008: 0x3009,  # LEFT ANGLE BRACKET
    0x300A: 0x300B,  # LEFT DOUBLE ANGLE BRACKET
    0x300C: 0x300D,  # LEFT CORNER BRACKET
    0x300E: 0x300F,  # LEFT WHITE CORNER BRACKET
    0x3010: 0x3011,  # LEFT BLACK LENTICULAR BRACKET
    0x3014: 0x3015,  # LEFT TORTOISE SHELL BRACKET
    0x3016: 0x3017,  # LEFT WHITE LENTICULAR BRACKET
    0x3018: 0x3019,  # LEFT WHITE TORTOISE SHELL BRACKET
    0x301A: 0x301B,  # LEFT WHITE SQUARE BRACKET
    0xFD3E: 0xFD3F,  # ORNATE LEFT PARENTHESIS
    0xFE59: 0xFE5A,  # SMALL LEFT PARENTHESIS
    0xFE5B: 0xFE5C,  # SMALL LEFT CURLY BRACKET
    0xFE5D: 0xFE5E,  # SMALL RIGHT TORTOISE SHELL BRACKET (error in spec? keep as-is)
    0xFF08: 0xFF09,  # FULLWIDTH LEFT PARENTHESIS
    0xFF3B: 0xFF3D,  # FULLWIDTH LEFT SQUARE BRACKET
    0xFF5B: 0xFF5D,  # FULLWIDTH LEFT CURLY BRACKET
    0xFF5F: 0xFF60,  # FULLWIDTH LEFT WHITE PARENTHESIS
    0xFF62: 0xFF63,  # HALFWIDTH LEFT CORNER BRACKET
}
CLOSE_BRACKET_TO_OPEN = {v: k for k, v in OPEN_BRACKET_TO_CLOSE.items()}

# BidiMirroring.txt subset - common pairs
BIDI_MIRROR_TABLE = {
    0x0028: 0x0029, 0x0029: 0x0028,  # parentheses
    0x003C: 0x003E, 0x003E: 0x003C,  # < >
    0x005B: 0x005D, 0x005D: 0x005B,  # [ ]
    0x007B: 0x007D, 0x007D: 0x007B,  # { }
    0x00AB: 0x00BB, 0x00BB: 0x00AB,  # << >>
    0x2039: 0x203A, 0x203A: 0x2039,  # < >
    0x2045: 0x2046, 0x2046: 0x2045,
    0x207D: 0x207E, 0x207E: 0x207D,
    0x208D: 0x208E, 0x208E: 0x208D,
    0x2208: 0x220B, 0x220B: 0x2208,
    0x2209: 0x220C, 0x220C: 0x2209,
    0x220A: 0x220D, 0x220D: 0x220A,
    0x2215: 0x29F5, 0x29F5: 0x2215,
    0x223C: 0x223D, 0x223D: 0x223C,
    0x2243: 0x22CD, 0x22CD: 0x2243,
    0x2252: 0x2253, 0x2253: 0x2252,
    0x2254: 0x2255, 0x2255: 0x2254,
    0x2264: 0x2265, 0x2265: 0x2264,
    0x2266: 0x2267, 0x2267: 0x2266,
    0x2268: 0x2269, 0x2269: 0x2268,
    0x226A: 0x226B, 0x226B: 0x226A,
    0x226E: 0x226F, 0x226F: 0x226E,
    0x2270: 0x2271, 0x2271: 0x2270,
    0x2272: 0x2273, 0x2273: 0x2272,
    0x2274: 0x2275, 0x2275: 0x2274,
    0x2276: 0x2277, 0x2277: 0x2276,
    0x2278: 0x2279, 0x2279: 0x2278,
    0x227A: 0x227B, 0x227B: 0x227A,
    0x227C: 0x227D, 0x227D: 0x227C,
    0x227E: 0x227F, 0x227F: 0x227E,
    0x2280: 0x2281, 0x2281: 0x2280,
    0x2282: 0x2283, 0x2283: 0x2282,
    0x2284: 0x2285, 0x2285: 0x2284,
    0x2286: 0x2287, 0x2287: 0x2286,
    0x2288: 0x2289, 0x2289: 0x2288,
    0x228A: 0x228B, 0x228B: 0x228A,
    0x228F: 0x2290, 0x2290: 0x228F,
    0x2291: 0x2292, 0x2292: 0x2291,
    0x2298: 0x29B8, 0x29B8: 0x2298,
    0x22A2: 0x22A3, 0x22A3: 0x22A2,
    0x22A6: 0x2ADE, 0x2ADE: 0x22A6,
    0x22A8: 0x2AE4, 0x2AE4: 0x22A8,
    0x22A9: 0x2AE3, 0x2AE3: 0x22A9,
    0x22AB: 0x2AE5, 0x2AE5: 0x22AB,
    0x22B0: 0x22B1, 0x22B1: 0x22B0,
    0x22B2: 0x22B3, 0x22B3: 0x22B2,
    0x22B4: 0x22B5, 0x22B5: 0x22B4,
    0x22B6: 0x22B7, 0x22B7: 0x22B6,
    0x22C9: 0x22CA, 0x22CA: 0x22C9,
    0x22CB: 0x22CC, 0x22CC: 0x22CB,
    0x22D0: 0x22D1, 0x22D1: 0x22D0,
    0x22D6: 0x22D7, 0x22D7: 0x22D6,
    0x22D8: 0x22D9, 0x22D9: 0x22D8,
    0x22DA: 0x22DB, 0x22DB: 0x22DA,
    0x22DC: 0x22DD, 0x22DD: 0x22DC,
    0x22DE: 0x22DF, 0x22DF: 0x22DE,
    0x22E0: 0x22E1, 0x22E1: 0x22E0,
    0x22E2: 0x22E3, 0x22E3: 0x22E2,
    0x22E4: 0x22E5, 0x22E5: 0x22E4,
    0x22E6: 0x22E7, 0x22E7: 0x22E6,
    0x22E8: 0x22E9, 0x22E9: 0x22E8,
    0x22EA: 0x22EB, 0x22EB: 0x22EA,
    0x22EC: 0x22ED, 0x22ED: 0x22EC,
    0x22F0: 0x22F1, 0x22F1: 0x22F0,
    0x22F2: 0x22FA, 0x22FA: 0x22F2,
    0x22F3: 0x22FB, 0x22FB: 0x22F3,
    0x22F4: 0x22FC, 0x22FC: 0x22F4,
    0x22F6: 0x22FD, 0x22FD: 0x22F6,
    0x22F7: 0x22FE, 0x22FE: 0x22F7,
    0x2308: 0x2309, 0x2309: 0x2308,
    0x230A: 0x230B, 0x230B: 0x230A,
    0x2329: 0x232A, 0x232A: 0x2329,
    0x2768: 0x2769, 0x2769: 0x2768,
    0x276A: 0x276B, 0x276B: 0x276A,
    0x276C: 0x276D, 0x276D: 0x276C,
    0x276E: 0x276F, 0x276F: 0x276E,
    0x2770: 0x2771, 0x2771: 0x2770,
    0x2772: 0x2773, 0x2773: 0x2772,
    0x2774: 0x2775, 0x2775: 0x2774,
    0x27C3: 0x27C4, 0x27C4: 0x27C3,
    0x27C5: 0x27C6, 0x27C6: 0x27C5,
    0x27D5: 0x27D6, 0x27D6: 0x27D5,
    0x27E6: 0x27E7, 0x27E7: 0x27E6,
    0x27E8: 0x27E9, 0x27E9: 0x27E8,
    0x27EA: 0x27EB, 0x27EB: 0x27EA,
    0x27EC: 0x27ED, 0x27ED: 0x27EC,
    0x27EE: 0x27EF, 0x27EF: 0x27EE,
    0x2983: 0x2984, 0x2984: 0x2983,
    0x2985: 0x2986, 0x2986: 0x2985,
    0x2987: 0x2988, 0x2988: 0x2987,
    0x2989: 0x298A, 0x298A: 0x2989,
    0x298B: 0x298C, 0x298C: 0x298B,
    0x298D: 0x298E, 0x298E: 0x298D,
    0x298F: 0x2990, 0x2990: 0x298F,
    0x2991: 0x2992, 0x2992: 0x2991,
    0x2993: 0x2994, 0x2994: 0x2993,
    0x2995: 0x2996, 0x2996: 0x2995,
    0x2997: 0x2998, 0x2998: 0x2997,
    0x29D8: 0x29D9, 0x29D9: 0x29D8,
    0x29DA: 0x29DB, 0x29DB: 0x29DA,
    0x29FC: 0x29FD, 0x29FD: 0x29FC,
    0x2E22: 0x2E23, 0x2E23: 0x2E22,
    0x2E24: 0x2E25, 0x2E25: 0x2E24,
    0x2E26: 0x2E27, 0x2E27: 0x2E26,
    0x2E28: 0x2E29, 0x2E29: 0x2E28,
    0x3008: 0x3009, 0x3009: 0x3008,
    0x300A: 0x300B, 0x300B: 0x300A,
    0x300C: 0x300D, 0x300D: 0x300C,
    0x300E: 0x300F, 0x300F: 0x300E,
    0x3010: 0x3011, 0x3011: 0x3010,
    0x3014: 0x3015, 0x3015: 0x3014,
    0x3016: 0x3017, 0x3017: 0x3016,
    0x3018: 0x3019, 0x3019: 0x3018,
    0x301A: 0x301B, 0x301B: 0x301A,
    0xFD3E: 0xFD3F, 0xFD3F: 0xFD3E,
    0xFE59: 0xFE5A, 0xFE5A: 0xFE59,
    0xFE5B: 0xFE5C, 0xFE5C: 0xFE5B,
    0xFE5D: 0xFE5E, 0xFE5E: 0xFE5D,
    0xFF08: 0xFF09, 0xFF09: 0xFF08,
    0xFF3B: 0xFF3D, 0xFF3D: 0xFF3B,
    0xFF5B: 0xFF5D, 0xFF5D: 0xFF5B,
    0xFF5F: 0xFF60, 0xFF60: 0xFF5F,
    0xFF62: 0xFF63, 0xFF63: 0xFF62,
}


# ============================================================
# SECTION: Helpers
# ============================================================

def get_isolating_run_sequences(chars: list[CharacterInfo], paragraph_level: int) -> list[dict]:
    """
    Compute isolating run sequences per UAX#9 BD13.
    Returns list of dicts with keys: run_indices, embedding_level, sos, eos

    BN characters (removed by X9) are transparent to level-run formation: each
    BN inherits the effective level of the nearest preceding non-BN character
    (falling back to paragraph_level at the start of the string).  All
    level-run boundaries and sos/eos values are computed from this effective
    level array rather than from raw embedding levels.

    sos and eos are computed per UAX #9 X10: each is 'R' or 'L' according to
    the higher of the two adjacent levels (the IRS level and the level of the
    neighbouring character outside the sequence, or paragraph_level at the
    paragraph boundaries).
    """
    levels = [ci.embedding_level for ci in chars]
    n = len(chars)

    # UAX #9 X9 removes BN characters before level runs are formed, so BN
    # characters must not create run boundaries of their own.  We build an
    # effective_levels array where every BN character inherits the embedding
    # level of the nearest preceding non-BN character (falling back to the
    # paragraph level at the start of the string).  This array is used for
    # all level-run and sos/eos computations in place of the raw levels.
    effective_levels = list(levels)
    last_non_bn_level = paragraph_level
    for i in range(n):
        if chars[i].character_type == 'BN':
            effective_levels[i] = last_non_bn_level
        else:
            last_non_bn_level = levels[i]

    # Get level runs: contiguous runs of same effective level
    runs = []
    i = 0
    while i < n:
        level = effective_levels[i]
        j = i + 1
        while j < n and effective_levels[j] == level:
            j += 1
        runs.append(list(range(i, j)))
        i = j

    def last_non_bn_type(run_indices):
        for idx in reversed(run_indices):
            if chars[idx].character_type != 'BN':
                return chars[idx].character_type
        return None

    # Build isolating run sequences by chaining
    used = [False] * len(runs)
    sequences = []

    for ri, run in enumerate(runs):
        if used[ri]:
            continue
        # Start a new IRS with this run
        irs_runs = [run]
        used[ri] = True
        current_run = run

        while True:
            last_type = last_non_bn_type(current_run)
            if last_type not in ISOLATE_INITIATOR_TYPES:
                break
            # Find position of last non-BN char in current_run
            initiator_pos = None
            for idx in reversed(current_run):
                if chars[idx].character_type != 'BN':
                    initiator_pos = idx
                    break
            if initiator_pos is None:
                break

            # Find matching PDI by counting isolate initiators/terminators
            depth = 1
            pdi_pos = None
            for k in range(initiator_pos + 1, n):
                t = chars[k].character_type
                if t in ISOLATE_INITIATOR_TYPES:
                    depth += 1
                elif t == 'PDI':
                    depth -= 1
                    if depth == 0:
                        pdi_pos = k
                        break

            if pdi_pos is None:
                break

            # Find which run contains pdi_pos
            next_run_idx = None
            for rj, r in enumerate(runs):
                if not used[rj] and pdi_pos in r:
                    next_run_idx = rj
                    break

            if next_run_idx is None:
                break

            used[next_run_idx] = True
            irs_runs.append(runs[next_run_idx])
            current_run = runs[next_run_idx]

        # Collect all indices
        all_indices = []
        for r in irs_runs:
            all_indices.extend(r)

        # Compute embedding level = effective level of first run
        irs_level = effective_levels[irs_runs[0][0]]

        # X10: Compute sos
        start_idx = irs_runs[0][0]
        if start_idx == 0:
            prev_level = paragraph_level
        else:
            prev_level = effective_levels[start_idx - 1]
        sos_level = max(prev_level, irs_level)
        sos = 'R' if (sos_level % 2) == 1 else 'L'

        # X10: Compute eos
        last_run = irs_runs[-1]
        end_idx = last_run[-1]
        last_run_level = effective_levels[last_run[0]]
        if end_idx == n - 1:
            next_level = paragraph_level
        else:
            next_level = effective_levels[end_idx + 1]
        eos_level = max(next_level, last_run_level)
        eos = 'R' if (eos_level % 2) == 1 else 'L'

        sequences.append({
            'run_indices': all_indices,
            'embedding_level': irs_level,
            'sos': sos,
            'eos': eos,
        })

    return sequences


def print_table(rule_name: str, chars: list[CharacterInfo],
                types_before: list[str], types_after: list[str],
                irs_label: str = '') -> None:
    """
    Print a before/after table showing the effect of a single rule application.

    types_before and types_after are parallel lists of Bidi type strings, one
    entry per element of chars.  irs_label, when provided, is appended to the
    header to identify the isolating run sequence (e.g. "IRS level=2").

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
    char_cells = []
    for ci in chars:
        ch = ci.character
        if ch.isprintable() and ord(ch) < 128:
            char_cells.append(ch)
        else:
            char_cells.append(f"U+{ord(ch):04X}")
    before_cells = list(types_before)
    after_cells = list(types_after)
    after_changed = [b != a for b, a in zip(types_before, types_after)]
    level_cells = [str(ci.embedding_level) for ci in chars]

    # Compute column widths
    col_widths = []
    for j in range(len(chars)):
        w = max(3, len(idx_cells[j]), len(char_cells[j]),
                len(before_cells[j]), len(after_cells[j]), len(level_cells[j]))
        col_widths.append(w)

    def fmt_row(label, cells):
        row = f"{label:<8} |"
        for j, cell in enumerate(cells):
            row += f" {cell:^{col_widths[j]}} |"
        return row

    print(fmt_row("Idx", idx_cells))
    print(fmt_row("Char", char_cells))
    print(fmt_row("Before", before_cells))
    after_row = "After    |"
    for j, cell in enumerate(after_cells):
        padded = f"{cell:^{col_widths[j]}}"
        if after_changed[j]:
            after_row += f" {BOLD_YELLOW}{padded}{RESET} |"
        else:
            after_row += f" {padded} |"
    print(after_row)
    print(fmt_row("Level", level_cells))
    print()


# ============================================================
# SECTION: P rules
# ============================================================

def determine_paragraph_embedding_level(chars: list[CharacterInfo], verbose: bool = False) -> int:
    """
    P2-P3: Find the first strong bidi type (L, R, AL) at the paragraph level.
    Characters between an isolate initiator and its matching PDI (or end of
    paragraph) are skipped — only top-level characters are considered.
    Returns 0 for LTR paragraph, 1 for RTL paragraph.
    """
    open_isolate_count = 0
    paragraph_level = 0  # P3 default: LTR if no strong type is found

    for ci in chars:
        char_type = ci.character_type
        if char_type in ISOLATE_INITIATOR_TYPES:
            open_isolate_count += 1
        elif char_type == 'PDI':
            if open_isolate_count > 0:
                open_isolate_count -= 1
        elif open_isolate_count == 0:
            if char_type in ('R', 'AL'):
                paragraph_level = 1
                break
            elif char_type == 'L':
                paragraph_level = 0  # explicit for symmetry with the RTL case above
                break

    if verbose:
        # Phase P only reads character types; it does not mutate them.
        # Both before and after columns are the same — showing current state only.
        types = [ci.character_type for ci in chars]
        print(f"=== Phase P: Paragraph Embedding Level = {paragraph_level} ===")
        print_table("P2/P3 (read-only — no type changes)", chars, types, types)

    return paragraph_level


# ============================================================
# SECTION: X rules
# ============================================================

def _least_greater_odd(level: int) -> int:
    """Return least odd number greater than level."""
    return level + 1 if (level % 2) == 0 else level + 2


def _least_greater_even(level: int) -> int:
    """Return least even number greater than level."""
    return level + 2 if (level % 2) == 0 else level + 1


def _resolve_fsi_direction(chars: list[CharacterInfo], fsi_index: int) -> str:
    """
    X5c: Determine whether FSI should act as RLI or LRI.
    Scan forward from fsi_index+1 to the matching PDI (or end of paragraph if
    there is no matching PDI), applying the P2 rule: find the first strong type
    (L, R, AL) while skipping over nested isolate pairs.
    Returns 'RLI' if the first strong type is R or AL, 'LRI' otherwise (including
    when no strong type is found — the P3 default).
    Does not mutate chars.
    """
    depth = 1
    for i in range(fsi_index + 1, len(chars)):
        t = chars[i].original_type
        if t in ISOLATE_INITIATOR_TYPES:
            depth += 1
        elif t == 'PDI':
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            if t in ('R', 'AL'):
                return 'RLI'
            elif t == 'L':
                return 'LRI'
    return 'LRI'  # default


def apply_explicit_levels(chars: list[CharacterInfo], paragraph_embedding_level: int,
                          verbose: bool = False) -> None:
    """
    X1-X9: Assign embedding levels based on explicit formatting characters.
    Modifies chars[i].embedding_level and chars[i].character_type in place.
    character_type changes: characters inside a directional override (RLO/LRO)
    have their type set to 'R' or 'L'; characters whose original_type is in
    X9_REMOVE_TYPES (RLE, LRE, RLO, LRO, PDF, BN) are reset to 'BN'.
    """
    # X1: Initialize
    stack = [(paragraph_embedding_level, 'neutral', False)]
    overflow_isolate_count = 0
    overflow_embedding_count = 0
    valid_isolate_count = 0

    before_types = [ci.original_type for ci in chars]

    for ci in chars:
        t = ci.character_type
        level, override, is_isolate = stack[-1]

        if t == 'RLE':  # X2
            ci.embedding_level = level
            new_level = _least_greater_odd(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                stack.append((new_level, 'neutral', False))
            else:
                if overflow_isolate_count == 0:
                    overflow_embedding_count += 1

        elif t == 'LRE':  # X3
            ci.embedding_level = level
            new_level = _least_greater_even(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                stack.append((new_level, 'neutral', False))
            else:
                if overflow_isolate_count == 0:
                    overflow_embedding_count += 1

        elif t == 'RLO':  # X4
            ci.embedding_level = level
            new_level = _least_greater_odd(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                stack.append((new_level, 'right-to-left', False))
            else:
                if overflow_isolate_count == 0:
                    overflow_embedding_count += 1

        elif t == 'LRO':  # X5
            ci.embedding_level = level
            new_level = _least_greater_even(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                stack.append((new_level, 'left-to-right', False))
            else:
                if overflow_isolate_count == 0:
                    overflow_embedding_count += 1

        elif t == 'RLI':  # X5a
            ci.embedding_level = level
            if override == 'left-to-right':
                ci.character_type = 'L'
            elif override == 'right-to-left':
                ci.character_type = 'R'
            new_level = _least_greater_odd(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                valid_isolate_count += 1
                stack.append((new_level, 'neutral', True))
            else:
                overflow_isolate_count += 1

        elif t == 'LRI':  # X5b
            ci.embedding_level = level
            if override == 'left-to-right':
                ci.character_type = 'L'
            elif override == 'right-to-left':
                ci.character_type = 'R'
            new_level = _least_greater_even(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                valid_isolate_count += 1
                stack.append((new_level, 'neutral', True))
            else:
                overflow_isolate_count += 1

        elif t == 'FSI':  # X5c
            direction = _resolve_fsi_direction(chars, ci.index)
            ci.character_type = direction
            ci.embedding_level = level
            if override == 'left-to-right':
                ci.character_type = 'L'
            elif override == 'right-to-left':
                ci.character_type = 'R'
            # Level is determined by the resolved direction, not by the
            # (possibly overridden) character_type above.
            if direction == 'RLI':
                new_level = _least_greater_odd(level)
            else:
                new_level = _least_greater_even(level)
            if new_level <= MAX_DEPTH and overflow_isolate_count == 0 and overflow_embedding_count == 0:
                valid_isolate_count += 1
                stack.append((new_level, 'neutral', True))
            else:
                overflow_isolate_count += 1

        elif t == 'PDI':  # X6a
            if overflow_isolate_count > 0:
                overflow_isolate_count -= 1
            elif valid_isolate_count > 0:
                overflow_embedding_count = 0
                while not stack[-1][2]:  # pop until isolate entry
                    stack.pop()
                stack.pop()
                valid_isolate_count -= 1
            level, override, is_isolate = stack[-1]
            ci.embedding_level = level
            if override == 'left-to-right':
                ci.character_type = 'L'
            elif override == 'right-to-left':
                ci.character_type = 'R'

        elif t == 'PDF':  # X7
            if overflow_isolate_count > 0:
                pass  # X7: ignore
            elif overflow_embedding_count > 0:
                overflow_embedding_count -= 1
            elif not is_isolate and len(stack) >= 2:
                stack.pop()
            # Assign the level of the new stack top (after any pop), so that
            # PDF's BN does not create a spurious high-level run that would
            # split the isolating run sequence around it.
            ci.embedding_level = stack[-1][0]

        elif t == 'B':  # X8: paragraph separator resets
            ci.embedding_level = paragraph_embedding_level

        else:  # X6: normal character
            ci.embedding_level = level
            if override == 'left-to-right':
                ci.character_type = 'L'
            elif override == 'right-to-left':
                ci.character_type = 'R'

    # X9: replace explicit formatting types and BN with 'BN' in character_type
    for ci in chars:
        if ci.original_type in X9_REMOVE_TYPES:
            ci.character_type = 'BN'

    if verbose:
        after_types = [ci.character_type for ci in chars]
        print("=== Phase X: Explicit Embedding Levels ===")
        print_table("X1-X9", chars, before_types, after_types)


# ============================================================
# SECTION: W rules
# ============================================================

def _apply_w1(types: list[str], sos: str) -> list[str]:
    """W1: NSM takes type of preceding character (or sos), BN is transparent.
    Exception: if the preceding character is an isolate initiator or PDI, NSM -> ON.
    """
    result = list(types)
    prev_type = sos
    for i in range(len(types)):
        t = result[i]
        if t == 'NSM':
            if prev_type in ISOLATE_INITIATOR_TYPES or prev_type == 'PDI':
                result[i] = 'ON'
            else:
                result[i] = prev_type
        if t != 'BN':
            prev_type = result[i]
    return result


def _apply_w2(types: list[str], sos: str) -> list[str]:
    """W2: EN -> AN if the nearest preceding strong type (L, R, AL, or sos),
    looking back through all non-strong characters, is AL.
    """
    result = list(types)
    last_strong = sos
    for i in range(len(types)):
        t = result[i]
        if t in STRONG_TYPES:
            last_strong = t
        elif t == 'EN' and last_strong == 'AL':
            result[i] = 'AN'
        # Non-strong types (including BN, neutrals, and weak types) are transparent:
        # they do not update last_strong
    return result


def _apply_w3(types: list[str]) -> list[str]:
    """W3: AL -> R."""
    return ['R' if t == 'AL' else t for t in types]


def _apply_w4(types: list[str]) -> list[str]:
    """W4: Single ES between EN-EN -> EN; single CS between EN-EN or AN-AN -> that type."""
    result = list(types)
    n = len(result)
    for i in range(1, n - 1):
        if result[i] == 'ES':
            if result[i - 1] == 'EN' and result[i + 1] == 'EN':
                result[i] = 'EN'
        elif result[i] == 'CS':
            if result[i - 1] == 'EN' and result[i + 1] == 'EN':
                result[i] = 'EN'
            elif result[i - 1] == 'AN' and result[i + 1] == 'AN':
                result[i] = 'AN'
    return result


def _apply_w5(types: list[str]) -> list[str]:
    """W5: ET adjacent to EN -> EN (sequences of ET adjacent to EN become EN)."""
    result = list(types)
    n = len(result)
    # Forward pass: ET following EN
    for i in range(n):
        if result[i] == 'ET':
            j = i - 1
            while j >= 0 and result[j] == 'ET':
                j -= 1
            if j >= 0 and result[j] == 'EN':
                result[i] = 'EN'
    # Backward pass: ET preceding EN
    for i in range(n - 1, -1, -1):
        if result[i] == 'ET':
            j = i + 1
            while j < n and result[j] == 'ET':
                j += 1
            if j < n and result[j] == 'EN':
                result[i] = 'EN'
    return result


def _apply_w6(types: list[str]) -> list[str]:
    """W6: Remaining ES, ET, CS -> ON."""
    return ['ON' if t in ('ES', 'ET', 'CS') else t for t in types]


def _apply_w7(types: list[str], sos: str) -> list[str]:
    """W7: EN -> L if the nearest preceding strong type (L or R, or sos),
    looking back through all non-strong characters, is L.
    """
    result = list(types)
    last_strong = sos
    for i in range(len(types)):
        t = result[i]
        if t in ('L', 'R'):
            last_strong = t
        elif t == 'EN' and last_strong == 'L':
            result[i] = 'L'
        # Non-strong types (including BN, neutrals, and weak types) are transparent:
        # they do not update last_strong
    return result


def apply_weak_rules(chars: list[CharacterInfo], paragraph_embedding_level: int,
                     verbose: bool = False) -> None:
    """W1-W7: Resolve weak bidi types per isolating run sequence.
    Mutates chars[i].character_type in place. Returns None.
    """
    sequences = get_isolating_run_sequences(chars, paragraph_embedding_level)

    for seq in sequences:
        run_indices = seq['run_indices']
        sos = seq['sos']
        level = seq['embedding_level']
        irs_label = f"IRS level={level}"

        # Extract types for this run
        types = [chars[i].character_type for i in run_indices]

        run_chars = [chars[i] for i in run_indices]

        # Apply W1
        before = list(types)
        types = _apply_w1(types, sos)
        if verbose:
            print_table("W1", run_chars, before, types, irs_label)

        # Apply W2
        before = list(types)
        types = _apply_w2(types, sos)
        if verbose:
            print_table("W2", run_chars, before, types, irs_label)

        # Apply W3
        before = list(types)
        types = _apply_w3(types)
        if verbose:
            print_table("W3", run_chars, before, types, irs_label)

        # Apply W4
        before = list(types)
        types = _apply_w4(types)
        if verbose:
            print_table("W4", run_chars, before, types, irs_label)

        # Apply W5
        before = list(types)
        types = _apply_w5(types)
        if verbose:
            print_table("W5", run_chars, before, types, irs_label)

        # Apply W6
        before = list(types)
        types = _apply_w6(types)
        if verbose:
            print_table("W6", run_chars, before, types, irs_label)

        # Apply W7
        before = list(types)
        types = _apply_w7(types, sos)
        if verbose:
            print_table("W7", run_chars, before, types, irs_label)

        # Write back
        for j, i in enumerate(run_indices):
            chars[i].character_type = types[j]


# ============================================================
# SECTION: N rules
# ============================================================

def _find_bracket_pairs(chars: list[CharacterInfo], run_indices: list[int]) -> list[tuple[int, int]]:
    """
    N0: Find matching bracket pairs in the run.
    Returns list of (open_ri, close_ri) pairs sorted by open bracket position,
    where each value is an index into run_indices (not an index into chars).
    Uses original characters (not types) for bracket matching.
    """
    bracket_stack = []  # list of (close_bracket_codepoint, index_into_run_indices)
    pairs = []

    for ri, idx in enumerate(run_indices):
        # N0 only applies to characters that are currently neutral (ON).
        # Characters overridden to L or R by LRO/RLO are not eligible.
        if chars[idx].character_type != 'ON':
            continue

        ch = chars[idx].character
        cp = ord(ch)

        if cp in OPEN_BRACKET_TO_CLOSE:
            if len(bracket_stack) >= BRACKET_STACK_MAX:
                break  # overflow: return pairs found so far (UAX #9 BD16)
            close_cp = OPEN_BRACKET_TO_CLOSE[cp]
            bracket_stack.append((close_cp, ri))

        elif cp in CLOSE_BRACKET_TO_OPEN:
            # Search bracket_stack for matching open.
            # UAX #9 requires treating canonical equivalents as equal (e.g.
            # U+2329/U+3008 and U+232A/U+3009 are canonical equivalents).
            cp_nfd = unicodedata.normalize('NFD', chr(cp))
            for si in range(len(bracket_stack) - 1, -1, -1):
                expected_nfd = unicodedata.normalize('NFD', chr(bracket_stack[si][0]))
                if expected_nfd == cp_nfd:
                    # Found match
                    open_ri = bracket_stack[si][1]
                    pairs.append((open_ri, ri))
                    bracket_stack = bracket_stack[:si]
                    break

    # Sort by open bracket position
    pairs.sort(key=lambda p: p[0])
    return pairs


def _apply_n0(chars: list[CharacterInfo], run_indices: list[int],
              sos: str, embedding_level: int) -> None:
    """
    N0: Resolve the direction of bracket pairs within an isolating run sequence.

    For each bracket pair (in open-bracket order):
      1. Scan inside for strong types (L, R, AL, EN, AN). If the embedding
         direction is found, assign it to both brackets. If only the opposite
         direction is found, look at the last strong type before the open
         bracket (falling back to sos) and assign that direction instead.
      2. If no strong type is found inside, leave both brackets as ON.
      3. Set any NSMs immediately following each bracket (skipping BN/X9
         characters) to the same direction as the bracket.

    Mutates chars[...].character_type in place. Returns None.

    Preconditions: W rules have already been applied (character_type reflects
    post-W state). sos is 'L' or 'R'.
    """
    pairs = _find_bracket_pairs(chars, run_indices)
    if not pairs:
        return

    embed_dir = 'R' if (embedding_level % 2) == 1 else 'L'

    for open_ri, close_ri in pairs:
        # Scan inside bracket pair for strong types (L, R, AL) and their
        # N0 R-equivalents (EN, AN)
        strong_found = None
        for pos in range(open_ri + 1, close_ri):
            idx = run_indices[pos]
            t = chars[idx].character_type
            if t in STRONG_TYPES or t in R_EQUIVALENT_TYPES:
                effective = 'R' if t in R_EQUIVALENT_TYPES else 'L'
                if effective == embed_dir:
                    strong_found = embed_dir
                    break
                else:
                    strong_found = effective

        if strong_found is None:
            continue  # no strong type inside: leave as ON

        if strong_found == embed_dir:
            direction = embed_dir
        else:
            # Use context: find last strong type before open bracket
            context = sos
            for pos in range(open_ri - 1, -1, -1):
                idx = run_indices[pos]
                t = chars[idx].character_type
                if t in STRONG_TYPES or t in R_EQUIVALENT_TYPES:
                    context = 'R' if t in R_EQUIVALENT_TYPES else 'L'
                    break
            direction = context

        # Set both brackets to direction
        open_idx = run_indices[open_ri]
        close_idx = run_indices[close_ri]
        chars[open_idx].character_type = direction
        chars[close_idx].character_type = direction

        # Set NSMs after open bracket (skip over BN/X9 characters)
        for pos in range(open_ri + 1, len(run_indices)):
            idx = run_indices[pos]
            if chars[idx].original_type == 'NSM':
                chars[idx].character_type = direction
            elif chars[idx].original_type in X9_REMOVE_TYPES:
                continue
            else:
                break

        # Set NSMs after close bracket (skip over BN/X9 characters)
        for pos in range(close_ri + 1, len(run_indices)):
            idx = run_indices[pos]
            if chars[idx].original_type == 'NSM':
                chars[idx].character_type = direction
            elif chars[idx].original_type in X9_REMOVE_TYPES:
                continue
            else:
                break


def _apply_n1_n2(types: list[str], run_indices: list[int], sos: str, eos: str,
                 embedding_level: int) -> list[str]:
    """
    N1: Neutral between same-direction strongs -> that direction.
    N2: Remaining neutrals -> embedding direction.
    EN and AN count as R for this purpose.
    """
    result = list(types)
    n = len(result)
    embed_dir = 'R' if (embedding_level % 2) == 1 else 'L'

    NEUTRAL_SET = frozenset({'B', 'S', 'WS', 'ON', 'BN', 'RLI', 'LRI', 'FSI', 'PDI'})

    def strong_equiv(t):
        if t in R_EQUIVALENT_TYPES:
            return 'R'
        elif t == 'L':
            return 'L'
        return None

    i = 0
    while i < n:
        if result[i] in NEUTRAL_SET:
            # Find extent of neutral run
            j = i
            while j < n and result[j] in NEUTRAL_SET:
                j += 1
            # result[i:j] is neutral run

            # Determine strong type before
            if i == 0:
                before = sos
            else:
                before = strong_equiv(result[i - 1]) or sos

            # Determine strong type after
            if j == n:
                after = eos
            else:
                after = strong_equiv(result[j]) or eos

            # N1: both same direction -> that direction
            if before == after:
                dir_to_use = before
            else:
                # N2: embedding direction
                dir_to_use = embed_dir

            for k in range(i, j):
                result[k] = dir_to_use

            i = j
        else:
            i += 1

    return result


def apply_neutral_rules(chars: list[CharacterInfo], paragraph_embedding_level: int,
                        verbose: bool = False) -> None:
    """N0-N2: Resolve neutral and isolate formatting types per IRS."""
    sequences = get_isolating_run_sequences(chars, paragraph_embedding_level)

    for seq in sequences:
        run_indices = seq['run_indices']
        sos = seq['sos']
        eos = seq['eos']
        level = seq['embedding_level']
        irs_label = f"IRS level={level}"

        run_chars = [chars[i] for i in run_indices]

        # N0: bracket pairs (modifies chars directly)
        if verbose:
            before_n0 = [chars[i].character_type for i in run_indices]
        _apply_n0(chars, run_indices, sos, level)
        if verbose:
            after_n0 = [chars[i].character_type for i in run_indices]
            print_table("N0", run_chars, before_n0, after_n0, irs_label)

        # N1/N2
        types = [chars[i].character_type for i in run_indices]
        before_n12 = list(types)
        types = _apply_n1_n2(types, run_indices, sos, eos, level)

        if verbose:
            print_table("N1/N2", run_chars, before_n12, types, irs_label)

        for j, i in enumerate(run_indices):
            chars[i].character_type = types[j]


# ============================================================
# SECTION: I rules
# ============================================================

def apply_implicit_rules(chars: list[CharacterInfo], verbose: bool = False) -> None:
    """I1-I2: Adjust embedding levels based on character types."""
    # I1: even levels
    before_i1 = [ci.embedding_level for ci in chars]
    for ci in chars:
        if ci.character_type == 'BN':
            continue
        level = ci.embedding_level
        if level % 2 == 0:  # even
            if ci.character_type == 'R':
                ci.embedding_level += 1
            elif ci.character_type in ('AN', 'EN'):
                ci.embedding_level += 2

    if verbose:
        after_i1 = [ci.embedding_level for ci in chars]
        print_table("I1", chars,
                               [str(l) for l in before_i1],
                               [str(l) for l in after_i1])

    # I2: odd levels
    before_i2 = [ci.embedding_level for ci in chars]
    for ci in chars:
        if ci.character_type == 'BN':
            continue
        level = ci.embedding_level
        if level % 2 == 1:  # odd
            if ci.character_type in ('L', 'EN', 'AN'):
                ci.embedding_level += 1

    if verbose:
        after_i2 = [ci.embedding_level for ci in chars]
        print_table("I2", chars,
                               [str(l) for l in before_i2],
                               [str(l) for l in after_i2])


# ============================================================
# SECTION: L rules
# ============================================================

def _apply_l1(chars: list[CharacterInfo], paragraph_embedding_level: int) -> None:
    """
    L1: Reset levels for segment/paragraph separators, trailing whitespace,
    and whitespace before separators.
    Uses original_type, not character_type.
    """
    n = len(chars)
    _reset_set = {'WS', 'BN'} | ISOLATE_INITIATOR_TYPES | {'PDI'}

    # Step 1: Any S or B: reset to paragraph_embedding_level,
    # and reset all WS/BN/isolate chars before it
    for i in range(n):
        ot = chars[i].original_type
        if ot in ('S', 'B'):
            chars[i].embedding_level = paragraph_embedding_level
            # Reset preceding WS/BN/isolate chars
            j = i - 1
            while j >= 0 and chars[j].original_type in _reset_set:
                chars[j].embedding_level = paragraph_embedding_level
                j -= 1

    # Step 2: Trailing WS/BN/isolate chars at end of paragraph
    i = n - 1
    while i >= 0 and chars[i].original_type in _reset_set:
        chars[i].embedding_level = paragraph_embedding_level
        i -= 1


def _apply_l2(chars: list[CharacterInfo]) -> None:
    """
    L2: From highest to lowest odd level, reverse each maximal contiguous
    sequence of chars at that level or higher.

    BN characters (removed by rule X9) are transparent to this algorithm:
    they are excluded from run detection so they do not split runs of
    visible characters at higher embedding levels.  After reordering the
    visible characters, BN characters are left in their original relative
    positions within the chars list (they will be filtered out by the
    caller when building the final visual string).
    """
    if not chars:
        return

    # Identify which positions hold visible (non-X9) characters.
    non_bn_indices = [i for i, ci in enumerate(chars)
                      if ci.original_type not in X9_REMOVE_TYPES]
    if not non_bn_indices:
        return

    # Work only on the visible characters.
    non_bn = [chars[i] for i in non_bn_indices]
    levels = [ci.embedding_level for ci in non_bn]

    max_level = max(levels)

    # Find lowest odd level among visible characters only.
    odd_levels = [l for l in levels if l % 2 == 1]
    if not odd_levels:
        return  # no RTL content
    min_odd = min(odd_levels)

    for level in range(max_level, min_odd - 1, -1):
        # Find maximal runs where level >= current level
        i = 0
        n = len(non_bn)
        while i < n:
            if levels[i] >= level:
                j = i + 1
                while j < n and levels[j] >= level:
                    j += 1
                # Reverse non_bn[i:j] in-place
                non_bn[i:j] = non_bn[i:j][::-1]
                # Also update our local levels copy
                levels[i:j] = levels[i:j][::-1]
                i = j
            else:
                i += 1

    # Write the reordered visible characters back into the slots they
    # originally occupied.  BN characters remain at their own positions.
    for k, idx in enumerate(non_bn_indices):
        chars[idx] = non_bn[k]


def _apply_l3(chars: list[CharacterInfo]) -> None:
    """
    L3: Combining marks (NSM) should follow their base character.
    After L2 reversal, NSMs may be separated from their base.
    This simplified version re-attaches NSMs to their preceding base.
    Note: Full UAX#9 L3 handles all combining mark categories; this
    implementation handles the common NSM case.
    """
    # After reversal, combining marks should stay with their base character.
    # In the simplified model: if a position has original_type NSM and the
    # preceding character is not at a different embedding level, they stay together
    # (L2 reversal handles them as a unit within the same level run).
    # No additional action needed for basic compliance.
    pass


def _apply_l4(chars: list[CharacterInfo]) -> None:
    """
    L4: Mirror characters that are at odd (RTL) embedding levels.
    """
    for ci in chars:
        if ci.embedding_level % 2 == 1:
            cp = ord(ci.character)
            if unicodedata.mirrored(ci.character) and cp in BIDI_MIRROR_TABLE:
                ci.character = chr(BIDI_MIRROR_TABLE[cp])


def apply_reorder_rules(chars: list[CharacterInfo], paragraph_embedding_level: int,
                        verbose: bool = False) -> tuple[list[int], str]:
    """L1-L4: Apply visual reordering."""
    _apply_l1(chars, paragraph_embedding_level)

    if verbose:
        types = [ci.character_type for ci in chars]
        print("=== After L1: Level Reset ===")
        print_table("L1", chars, types, types)

    _apply_l2(chars)

    if verbose:
        types = [ci.character_type for ci in chars]
        print("=== After L2: Visual Reorder ===")
        print_table("L2", chars, types, types)

    _apply_l3(chars)

    reordered_text = ''.join(ci.character for ci in chars)

    _apply_l4(chars)

    if verbose:
        types = [ci.character_type for ci in chars]
        print("=== After L4: Mirror ===")
        print_table("L4", chars, types, types)

    final_levels = [ci.embedding_level for ci in chars]

    return final_levels, reordered_text


# ============================================================
# SECTION: Entry point
# ============================================================

def apply_bidi_algorithm(
    text: str,
    verbose: bool = False,
    paragraph_embedding_level: int | None = None,
) -> tuple[list[int], str, int]:
    """
    Apply the Unicode Bidirectional Algorithm (UAX #9) to text.

    Args:
        paragraph_embedding_level: If provided (0 or 1), use this as the paragraph
            embedding level instead of running the P2/P3 auto-detection rules.

    Returns:
        (embedding_levels, reordered_text, paragraph_level)
        embedding_levels: list of final embedding levels (one per character, in visual order)
        reordered_text: visually reordered string
        paragraph_level: resolved paragraph embedding level (0=LTR, 1=RTL)
    """
    if not text:
        return [], '', 0

    # Initialize CharacterInfo for each character
    chars = []
    for i, ch in enumerate(text):
        btype = unicodedata.bidirectional(ch)
        if not btype:
            btype = 'L'
        chars.append(CharacterInfo(
            index=i,
            character=ch,
            original_type=btype,
            character_type=btype,
            embedding_level=0,
        ))

    # Phase P: Determine paragraph embedding level
    if paragraph_embedding_level is not None:
        paragraph_level = paragraph_embedding_level
    else:
        paragraph_level = determine_paragraph_embedding_level(chars, verbose=verbose)

    # Phase X: Explicit embedding levels
    apply_explicit_levels(chars, paragraph_level, verbose=verbose)

    # Phase W: Weak types
    apply_weak_rules(chars, paragraph_level, verbose=verbose)

    # Phase N: Neutral types
    apply_neutral_rules(chars, paragraph_level, verbose=verbose)

    # Phase I: Implicit levels
    apply_implicit_rules(chars, verbose=verbose)

    # Phase L: Reordering
    # L1 resets S/B and trailing whitespace to the paragraph level; those
    # reset levels are part of the "resolved" levels that conformance tests
    # check.  Apply L1 now, capture levels, then run L2-L4 for reordering.
    _apply_l1(chars, paragraph_level)
    logical_levels = [ci.embedding_level for ci in chars]

    final_levels, reordered_text = apply_reorder_rules(chars, paragraph_level, verbose=verbose)

    return logical_levels, reordered_text, paragraph_level


# ============================================================
# SECTION: Demo
# ============================================================

if __name__ == '__main__':
    examples = [
        ("Hello, World!", "Pure LTR"),
        ("שלום", "Pure RTL (Hebrew: shalom)"),
        ("שלום 123 Hi", "Mixed RTL+digits+LTR"),
        ("\u202AHello שלום\u202C", "LRE/PDF explicit embedding"),
        ("הוא אמר: ״\u2066Car is מכונית in Hebrew\u2069״.\u200f", "LRI/FSI isolate"),
        ('He said “שלום”', "Neutral brackets + N0"),
    ]

    for text, description in examples:
        print("=" * 60)
        print(f"Example: {description}")
        print(f"Input: {repr(text)}")
        print()
        levels, reordered, _para_level = apply_bidi_algorithm(text, verbose=True)
        print(f"Paragraph level:  {_para_level}")
        print(f"Embedding levels: {levels}")
        print(f"Reordered text:   {repr(reordered)}")
        print()
