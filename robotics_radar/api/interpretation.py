"""Reading guidance attached to every basket response.

A NARRATIVE basket moving is sentiment, not constraint. The API must not let a
narrative basket and a pure basket read identically, so the distinction is
carried as text on the response rather than left for a caller to infer from an
enum they may ignore.
"""

from __future__ import annotations

from robotics_radar.models.enums import PurityGrade

_BY_PURITY = {
    PurityGrade.pure: (
        "Constituents derive material revenue from this constraint. A move here "
        "is the strongest constraint read available on this board -- which is "
        "still not a tightness measurement."
    ),
    PurityGrade.mixed: (
        "Constituents have real exposure to this constraint, diluted by "
        "unrelated revenue. A move here is weak evidence about the constraint "
        "and should be read alongside the linked node's series, not instead of "
        "them."
    ),
    PurityGrade.narrative: (
        "Exposure is thematic. A move in this basket is SENTIMENT, not "
        "constraint, and must not be read as evidence that the underlying "
        "constraint has tightened or loosened."
    ),
}

_DEMAND = (
    " This is a demand-side basket, not a constraint. It exists to help judge "
    "whether tightness elsewhere is demand-led."
)

_UNIVERSAL = (
    " Nothing in robotics is tight today and unit volumes are trivial; this "
    "board is a forward map of what breaks first as volume scales, not a live "
    "tightness gauge."
)


def interpretation_for(purity: PurityGrade, is_demand_side: bool) -> str:
    text = _BY_PURITY[purity]
    if is_demand_side:
        text += _DEMAND
    return text + _UNIVERSAL


def coverage_caveat(priced: int, total: int) -> str:
    if total == 0:
        return "This basket has no members by design; there is no listed pure play."
    if priced == 0:
        return "No constituent could be priced. No return is reported."
    if priced < total:
        return (
            f"Computed on {priced} of {total} constituents. A basket computed on "
            "partial coverage is a different number from the full basket."
        )
    return "All constituents priced."
