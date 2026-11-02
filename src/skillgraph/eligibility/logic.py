"""Verdict lattice (ARCHITECTURE §11.1; TASKS P3.2).

The verdicts are totally ordered ``NOT_MET < UNKNOWN < CONDITIONAL < MET`` (``Verdict.rank``, defined with the enum in
``skillgraph.model.eligibility``; there is no second verdict type). ``and_`` is the minimum and ``or_`` the maximum:

* one definite failure fails a conjunction: ``and_(NOT_MET, UNKNOWN) == NOT_MET``;
* an unknown never becomes a pass: ``and_(UNKNOWN, MET) == UNKNOWN``;
* a conditional route beats an unknown one: ``or_(CONDITIONAL, UNKNOWN) == CONDITIONAL``.

Both are associative, commutative and idempotent, so any grouping or order of operands gives the same result.

An empty call raises ``ValueError``. The identity elements would be ``MET`` for ``and_`` and ``NOT_MET`` for ``or_``, but
a rule with no operands is a data problem, not a pass: the architecture defines no verdict for it and none is invented
here. The caller (P3.3) decides what a specification without rows means.
"""

from __future__ import annotations

from skillgraph.model.eligibility import Verdict

__all__ = ["and_", "or_"]


def _checked(verdicts: tuple[object, ...], name: str) -> tuple[Verdict, ...]:
    if not verdicts:
        raise ValueError(f"{name}() needs at least one verdict")
    for v in verdicts:
        if not isinstance(v, Verdict):  # a plain string such as "MET" is rejected, never coerced
            raise TypeError(f"{name}() takes Verdict members, got {v!r}")
    return verdicts  # type: ignore[return-value]


def and_(*verdicts: Verdict) -> Verdict:
    """The lowest verdict: AND of the components of a row, and of the age rule with the rows."""
    return min(_checked(verdicts, "and_"), key=lambda v: v.rank)


def or_(*verdicts: Verdict) -> Verdict:
    """The highest verdict: OR over alternative rows."""
    return max(_checked(verdicts, "or_"), key=lambda v: v.rank)
