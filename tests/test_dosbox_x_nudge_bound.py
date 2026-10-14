"""The nudge's ceiling is stated TWICE, in two languages, and this holds the two equal.

WHY IT IS STATED TWICE AT ALL. `keypost.swift` enforces it because it emits one delta event
per point and a runaway call would run for ever; `dosbox_inputs.py` enforces it so the
refusal arrives as `bad_argument` BEFORE the window is touched, the layer `send_keys`
already validates an unknown key name in. Neither can be dropped: the Swift one is the
program's own safety and the Python one is the contract's, and a caller must not have to
learn which layer refused them.

WHAT DRIFT WOULD DO, and why only one direction is loud. If Python's number falls BELOW the
helper's, Python refuses first and the helper's bound is simply never reached: safe, and
invisible. If Python's rises ABOVE it, a call Python accepts dies in the helper with a
native exit code, which is the exact failure the two-sided check exists to prevent. A
comment saying "keep these equal" is a hope; this is the comparison.

IT REFUSES TO PASS ON NOTHING. A rename, a move or a rewrite of either constant makes the
match fail rather than quietly examining zero files and reporting green.
"""

from __future__ import annotations

import re
from pathlib import Path

import dosbox_inputs as inputs

HERE = Path(__file__).resolve().parent.parent
SWIFT = HERE / "keypost.swift"
# The Swift declaration, and the guard that USES it. Both are matched: a constant nothing
# reads would satisfy a check on the declaration alone.
DECLARED = re.compile(r"^let\s+MAX_NUDGE_PX\s*=\s*(\d+)\s*$", re.M)
GUARDED = re.compile(r"d[xy]\s*<=\s*MAX_NUDGE_PX")


def test_the_swift_helper_declares_the_same_nudge_ceiling_python_enforces() -> None:
    text = SWIFT.read_text(encoding="utf-8")
    assert text.strip(), f"{SWIFT} is empty, so this case examined nothing"
    found = DECLARED.findall(text)
    assert len(found) == 1, (
        f"expected exactly one `let MAX_NUDGE_PX = <n>` in {SWIFT}, found {found}: this "
        "check cannot compare what it cannot locate, so it fails rather than pass")
    assert int(found[0]) == inputs.MAX_NUDGE_PX, (
        f"{SWIFT} caps a nudge at {found[0]} px and dosbox_inputs.py at "
        f"{inputs.MAX_NUDGE_PX}: a call Python accepts and the helper refuses comes back as "
        "a native exit code instead of a `bad_argument`")


def test_the_swift_bound_is_inclusive_like_pythons() -> None:
    """Exactly the ceiling is ALLOWED on both sides, and one past it refused on both. The
    two could hold the same number and still disagree by an off-by-one in the comparison,
    which no equality check on the constant would see."""
    text = SWIFT.read_text(encoding="utf-8")
    assert GUARDED.search(text), (
        f"no `dx <= MAX_NUDGE_PX` guard found in {SWIFT}: either the helper stopped bounding "
        "the nudge or it now spells the bound another way, and this check cannot say which")
    # Python's side, read the same way: `abs(v) > MAX` refuses, so the ceiling itself passes.
    inputs.check_mouse(None, None, None, inputs.MAX_NUDGE_PX, 0, None)
