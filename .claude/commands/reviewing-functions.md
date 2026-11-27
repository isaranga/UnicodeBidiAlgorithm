---
name: reviewing-functions
description: Reviews bidi.py function by function, line by line. For each function, checks clarity, correctness, naming, docstring quality, and UAX#9 spec rule alignment. Outputs a structured findings table followed by a short verdict. Use this skill when doing a systematic review of bidi.py — the Unicode Bidirectional Algorithm implementation. Accepts an optional starting function name, or the special token "next" to continue from where the last review left off.
---

Arguments passed: `$ARGUMENTS`

## Argument parsing

Parse `$ARGUMENTS`:

- If empty: start from the first function in `bidi.py`.
- If a function name: jump directly to that function.
- If `next`: advance to the function immediately after the last one reviewed in this conversation. If no prior function was reviewed, start from the first.

## Step 1 — Read the file

1. Read `bidi.py` using the Read tool.
2. Extract the ordered list of all top-level function definitions (lines matching `^def `). Build an internal index: function name → start line → end line.
3. Identify the starting function: first in file order, the named argument, or "next" continuation.
4. Announce: "Reviewing `<function_name>` (lines M–N)."

## Step 2 — Review the function, line by line

Work through the function body from the `def` statement through the last line before the next top-level definition. For each logical unit (def line, docstring, each statement block), apply the criteria below.

### Review criteria

| ID | Criterion | What to check |
|----|-----------|---------------|
| C1 | Clarity | Is the intent obvious without tracing execution? Explicit loops preferred over compact comprehensions when the body has logic. |
| C2 | Naming | Does the function name reflect what it does? Are local variables named for what they hold, not how they are computed? |
| C3 | Docstring | Present? Accurate? Does it state preconditions, what is mutated vs returned, and any non-obvious invariants? |
| C4 | Correctness | Does the code match the algorithm described in its docstring and comments? Look for off-by-one errors, wrong comparisons, missing edge cases (empty input, single element, boundary levels). |
| C5 | Spec alignment | Does the function name match the rule label (e.g., `_apply_w1` ↔ W1)? Do inline comments cite the rule step? Does the implementation match the rule's textual description? |
| C6 | Mutation vs return | Is it clear which arguments are mutated in place vs which produce new values? Does the signature match sibling functions? |
| C7 | Verbose/tracing | Does this function participate in the `verbose` parameter pattern consistently? Are `print_table` calls present where expected? |
| C8 | Constants & sets | Are magic literals extracted to named constants? Are set membership tests using the project's named frozensets where available? |

### UAX#9 context for bidi.py

The data model centers on `CharacterInfo` — `original_type` is immutable, `character_type` is the working copy mutated per phase. Phase-orchestrating functions delegate to `_apply_*` helpers; `apply_bidi_algorithm` computes the isolating run sequences once (X10, `get_isolating_run_sequences`) and passes them to the W and N phases (`apply_weak_rules`, `apply_neutral_rules`); the I phase works on the whole paragraph, since I1/I2 are per-character. `print_table` handles verbose output uniformly. Flag any divergence from these conventions.

## Step 3 — Produce the findings table

Output exactly this structure:

### `<function_name>` — lines M–N

| Line(s) | Criterion | Severity | Finding |
|---------|-----------|----------|---------|
| M       | C4        | warning  | <concise description> |
| M–N     | C1        | info     | <suggestion> |

Severity levels:
- **error** — likely bug or spec violation
- **warning** — correctness risk, misleading name/doc, or silent deviation from project convention
- **info** — style suggestion, clarity improvement, or missing trace output

If the function is clean on all criteria, output a single row: criterion "all", severity "info", finding "No issues found."

After the table, add a short one-paragraph **Verdict** summarising: overall quality, the most important finding (if any), and whether the function upholds the project's clarity-first philosophy.

## Step 4 — Offer to continue

After the verdict, output exactly:

---
Reviewed `<function_name>` (<N> finding(s)). Next function: `<next_function_name>` (line K).
Type `/reviewing-functions next` to continue, or `/reviewing-functions <name>` to jump to a specific function.

If this is the last function in the file, output instead:

---
Reviewed `<function_name>` — this is the last function in `bidi.py`. Review complete.

## Reviewer notes

- Do not propose rewrites unless the finding is an **error**. For warnings and info, describe what to change, not how.
- Respect the priority order: clarity > correctness > performance. Never flag an explicit loop as inferior to a comprehension.
- Nested functions (e.g., `last_non_bn_type`, `fmt_row`, `strong_equiv`) are reviewed as part of their parent function block, not as separate index entries.
- Line references should point to the specific line(s) exhibiting the finding, not the whole function range.
