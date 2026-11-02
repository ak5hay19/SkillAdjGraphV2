"""The enums in the models must equal the enum table of API_SPEC.md §2.1, parsed from the spec itself."""

import re
from enum import Enum
from pathlib import Path

import pytest

from skillgraph.model.eligibility import ComponentType, UnknownReasonCode, Verdict
from skillgraph.model.evidence import EngineUse, EvidenceClass, QualityFlagCode, Severity, ValueStatus
from skillgraph.model.occupation import TitleVerification
from skillgraph.model.qualification import Coverage
from skillgraph.model.source import LicenceStatus

SPEC = Path(__file__).resolve().parents[2] / "API_SPEC.md"
BACKTICKED = re.compile(r"`([^`]+)`")


def spec_enum_rows() -> dict[str, str]:
    text = SPEC.read_text(encoding="utf-8")
    section = text.split("### 2.1 Enums", 1)[1].split("\n### ", 1)[0]
    rows = {}
    for line in section.splitlines():
        m = re.match(r"^\|\s*`(\w+)`[^|]*\|(.*)\|\s*$", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def spec_values(cell: str) -> list[str]:
    """Backticked values of a cell, excluding the ordering expression ('A < B') and trailing prose."""
    return [t for t in BACKTICKED.findall(cell) if "<" not in t]


ROWS = spec_enum_rows()
MODELLED = [EvidenceClass, Verdict, EngineUse, ValueStatus, Coverage, ComponentType, UnknownReasonCode,
            QualityFlagCode, Severity, TitleVerification, LicenceStatus]


def test_the_spec_table_was_parsed():
    assert {"EvidenceClass", "Verdict", "EngineUse", "ValueStatus"} <= set(ROWS)
    assert len(ROWS) >= 15


@pytest.mark.parametrize("enum", MODELLED, ids=lambda e: e.__name__)
def test_enum_matches_spec_exactly(enum: type[Enum]):
    assert [m.value for m in enum] == spec_values(ROWS[enum.__name__])


@pytest.mark.parametrize("name", ["EvidenceClass", "Verdict", "EngineUse", "ValueStatus"])
def test_the_four_required_enums_are_covered(name):
    assert name in {e.__name__ for e in MODELLED}


def test_verdict_order_matches_the_spec_ordering_expression():
    ordering = next(t for t in BACKTICKED.findall(ROWS["Verdict"]) if "<" in t)
    expected = [s.strip() for s in ordering.split("<")]
    assert sorted(Verdict, key=lambda v: v.rank) == [Verdict(s) for s in expected]
    assert Verdict.NOT_MET.rank < Verdict.UNKNOWN.rank < Verdict.CONDITIONAL.rank < Verdict.MET.rank
