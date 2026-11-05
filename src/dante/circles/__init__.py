"""One module per circle. Each exposes run(ctx) and touches nothing below it."""

from . import (
    c1_limbo,
    c2_lust,
    c3_gluttony,
    c4_greed,
    c5_wrath,
    c6_heresy,
    c7_violence,
    c8_fraud,
    c9_treachery,
)

DESCENT = [
    c1_limbo, c2_lust, c3_gluttony, c4_greed, c5_wrath, c6_heresy, c7_violence,
    c8_fraud, c9_treachery,
]

__all__ = ["DESCENT"]
