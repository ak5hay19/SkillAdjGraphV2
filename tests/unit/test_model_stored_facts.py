"""Stored source-of-truth facts must be OFFICIAL (audit finding N1). Only OFFICIAL, cited values are accepted for
qualification hours, NSQF level, minimum age, credits, NCO codes and NOS-membership values; the general ``Valued``
remains open to every class, because profile inputs and hypothetical planning values legitimately use them."""

import pytest
from model_factory import curated, ev, hours, membership, official
from pydantic import ValidationError

from skillgraph.model.evidence import CreditValue, DisplayValued, EvidenceClass, OfficialValued, Valued
from skillgraph.model.qualification import HoursBreakdown, NosMembership, Qualification

NON_OFFICIAL = ["HYPOTHETICAL", "DECLARED", "CONFIG", "INFERENCE", "RULE_DERIVED"]


def non_official(cls, value, **extra):
    """A value of another class, otherwise as well-formed as possible (cited where the class requires it)."""
    d = {"value": value, "evidence_class": cls, "evidence_id": ev(9), **extra}
    return d


# Each case: (label, builder of the full entity with the stored fact replaced, model).
def hours_total(v):
    return Qualification, curated(hours={**hours(), "total": v})


def hours_part(v):
    return Qualification, curated(hours={**hours(), "theory": v})


def level(v):
    return Qualification, curated(nsqf_level=v)


def min_age(v):
    return Qualification, curated(min_age=v)


def q_credits(v):
    return Qualification, curated(credits=v)


def nco(v):
    return Qualification, curated(nco_codes=[v])


def m_level(v):
    return NosMembership, membership(nsqf_level=v)


def m_hours(v):
    return NosMembership, membership(hours={**hours(), "total": v})


def m_credits(v):
    return NosMembership, membership(credits=v)


def m_version(v):
    return NosMembership, membership(version=v)


def version_info(v):
    return Qualification, curated(version_info={"item5_version": v})


CATEGORIES = {
    "qualification hours total": (hours_total, 120.0, "SAFE_HOURS"),
    "qualification hours part": (hours_part, 20.0, "SAFE_HOURS"),
    "qualification nsqf_level": (level, 2.5, "SAFE_HARD_RULE"),
    "qualification min_age": (min_age, 18, "SAFE_HARD_RULE"),
    "qualification credits": (q_credits, 4.0, "NOT_USED"),
    "qualification nco_codes": (nco, "8153.0101", None),
    "membership nsqf_level": (m_level, 2.5, None),
    "membership hours": (m_hours, 100.0, "SAFE_HOURS"),
    "membership credits": (m_credits, 4.0, "NOT_USED"),
    "membership version": (m_version, "4.0", "DISPLAY_ONLY"),
    "qualification version_info": (version_info, "4.0", "DISPLAY_ONLY"),
}


@pytest.mark.parametrize("cls", NON_OFFICIAL)
@pytest.mark.parametrize("label", CATEGORIES)
def test_non_official_class_is_refused_for_every_stored_fact(label, cls):
    build, value, use = CATEGORIES[label]
    model, data = build(non_official(cls, value, engine_use=use, value_status="TRANSCRIBED"))
    with pytest.raises(ValidationError, match="must be OFFICIAL"):
        model.model_validate(data)


@pytest.mark.parametrize("label", CATEGORIES)
def test_valid_official_value_is_accepted_for_every_stored_fact(label):
    build, value, use = CATEGORIES[label]
    model, data = build(official(value, engine_use=use))
    assert model.model_validate(data)


def test_the_demonstrated_hypothetical_hours_case_is_closed():
    # Audit probe: HYPOTHETICAL, no evidence, SAFE_HOURS, as Qualification.hours.total.
    hypothetical = {"value": 12.0, "evidence_class": "HYPOTHETICAL", "engine_use": "SAFE_HOURS"}
    model, data = hours_total(hypothetical)
    with pytest.raises(ValidationError, match="must be OFFICIAL"):
        model.model_validate(data)
    with pytest.raises(ValidationError, match="must be OFFICIAL"):
        HoursBreakdown.model_validate({"total": hypothetical})


def test_the_demonstrated_credit_and_level_cases_are_closed():
    for build, value, use in ((q_credits, 4.0, "NOT_USED"), (level, 2.5, None)):
        model, data = build({"value": value, "evidence_class": "CONFIG", "engine_use": use})
        with pytest.raises(ValidationError, match="must be OFFICIAL"):
            model.model_validate(data)
    with pytest.raises(ValidationError, match="must be OFFICIAL"):
        CreditValue.model_validate({"value": 4.0, "evidence_class": "DECLARED", "engine_use": "NOT_USED"})


def test_official_still_requires_its_evidence_and_status():
    for drop in ("evidence_id", "value_status"):
        v = {**official(100.0, engine_use="SAFE_HOURS"), drop: None}
        with pytest.raises(ValidationError):
            HoursBreakdown.model_validate({"total": v})


def test_official_value_with_open_conflict_is_still_not_safe():
    v = official(14.0, engine_use="SAFE_HOURS", conflict_id="conflict:OV-036")
    with pytest.raises(ValidationError, match="open conflict"):
        HoursBreakdown.model_validate({"total": v})


def test_official_keeps_its_cited_corroboration_and_correction_statuses():
    for status in ("CORROBORATED", "CONFIRMED_BY_GEOMETRY", "PARSED_UNCERTAIN"):
        assert OfficialValued[float].model_validate(official(1.0, status=status))
    corrected = official(1.0, status="CORRECTION_APPLIED", source_value="", source_evidence_id=ev(9))
    assert OfficialValued[float].model_validate(corrected).source_value == ""


def test_general_valued_is_unchanged_and_still_serves_other_contexts():
    # Request-scoped and derived values keep their classes elsewhere (profiles, paths, explanations).
    for cls in ("DECLARED", "CONFIG", "HYPOTHETICAL"):
        assert Valued[float].model_validate({"value": 1.0, "evidence_class": cls}).evidence_class is EvidenceClass(cls)
    for cls in ("RULE_DERIVED", "INFERENCE"):
        assert Valued[float].model_validate({"value": 1.0, "evidence_class": cls, "evidence_id": ev(1)})
    # ... but their class is never silently rewritten into OFFICIAL.
    assert Valued[float].model_validate({"value": 1.0, "evidence_class": "CONFIG"}).evidence_class is EvidenceClass.CONFIG


def test_display_valued_is_official_and_display_only():
    base = official("4.0", engine_use="DISPLAY_ONLY")
    assert DisplayValued[str].model_validate(base)
    with pytest.raises(ValidationError, match="must be OFFICIAL"):
        DisplayValued[str].model_validate({**base, "evidence_class": "CONFIG"})
