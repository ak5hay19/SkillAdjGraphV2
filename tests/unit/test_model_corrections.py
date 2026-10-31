"""P1.4 model extensions: source_value / source_evidence_id on Valued, credit_groups, eligibility source rows."""
import pytest
from pydantic import ValidationError

from skillgraph.model.eligibility import EligibilitySourceRow
from skillgraph.model.evidence import OfficialValued, Valued
from skillgraph.model.qualification import CreditGroup, Qualification

from model_factory import CODE, QID, credits, curated, ev, official


def corrected(**kw):
    base = official("No Experience required", 1, status="CORRECTION_APPLIED", source_value="", source_evidence_id=ev(2))
    return {**base, **kw}


def test_correction_keeps_empty_source_value_distinct_from_absent():
    v = OfficialValued[str].model_validate(corrected())
    assert v.source_value == "" and v.source_value is not None
    plain = OfficialValued[str].model_validate(official("x"))
    assert plain.source_value is None
    again = OfficialValued[str].model_validate_json(v.model_dump_json())
    assert again.source_value == ""


@pytest.mark.parametrize("extra", [{"source_value": "x"}, {"source_evidence_id": ev(2)}])
def test_source_fields_refused_unless_correction_applied(extra):
    for status in ("TRANSCRIBED", "PARSED_UNCERTAIN", "CORROBORATED", "CONFIRMED_BY_GEOMETRY"):
        with pytest.raises(ValidationError, match="only for value_status CORRECTION_APPLIED"):
            Valued[str].model_validate({**official("x", status=status), **extra})


def test_correction_requires_both_source_fields_and_distinct_evidence():
    for drop in ("source_value", "source_evidence_id"):
        with pytest.raises(ValidationError, match="requires source_value"):
            OfficialValued[str].model_validate(corrected(**{drop: None}))
    with pytest.raises(ValidationError, match="must differ"):
        OfficialValued[str].model_validate(corrected(source_evidence_id=ev(1)))


def group(**kw):
    base = {"member_s_nos": [1, 2], "credits": credits(4.0), "overlay_ids": ["OV-034"]}
    return {**base, **kw}


def test_credit_group_representation():
    g = CreditGroup.model_validate(group())
    assert g.credits.engine_use.value == "NOT_USED"
    for bad in ({"member_s_nos": [2, 1]}, {"member_s_nos": [1]}, {"member_s_nos": [1, 1]}, {"overlay_ids": []}):
        with pytest.raises(ValidationError):
            CreditGroup.model_validate(group(**bad))
    with pytest.raises(ValidationError, match="NOT_USED"):
        CreditGroup.model_validate(group(credits=official(4.0, engine_use="SAFE_HOURS")))


def test_qualification_credit_groups_must_refer_to_memberships():
    assert Qualification.model_validate(curated(credit_groups=[group()])).credit_groups
    with pytest.raises(ValidationError, match="not a NOS membership"):
        Qualification.model_validate(curated(credit_groups=[group(member_s_nos=[1, 7])]))


def row(**kw):
    base = {"id": f"rule:{CODE}/E2", "qualification_id": QID, "kind": "ELIGIBILITY_ROW", "s_no": 2,
            "raw_row_text": official("10th Grade pass work", 3), "extraction_status": "PARSED_UNCERTAIN",
            "engine_use": "UNKNOWN"}
    return {**base, **kw}


def test_eligibility_source_row_has_no_components_and_checks_ids():
    r = EligibilitySourceRow.model_validate(row())
    assert not hasattr(r, "components")
    for bad in ({"s_no": 3}, {"raw_row_text": None}, {"qualification_id": "qual:TEST/Q9002"},
                {"min_age": official(18)}):
        with pytest.raises(ValidationError):
            EligibilitySourceRow.model_validate(row(**bad))
    age = row(id=f"rule:{CODE}/AGE", kind="AGE_9C", s_no=None, raw_row_text=None, min_age=official(18, 4))
    assert EligibilitySourceRow.model_validate(age)


# ---- substantiation guard and engine_constraint (P1.4 acceptance fixes) -----------------------------------------


def text_row(status="TRANSCRIBED", use="CONDITIONAL_ON_DECLARED_RELEVANCE", **kw):
    base = row(extraction_status=status, engine_use=use,
               raw_row_text=official("8th grade pass || 1", 3, status=status, engine_use=use))
    return {**base, **kw}


def test_computing_use_on_an_uncertain_row_is_refused():
    with pytest.raises(ValidationError, match="requires a substantiated row: the extraction status is PARSED_UNCERTAIN"):
        EligibilitySourceRow.model_validate(text_row(status="PARSED_UNCERTAIN"))
    with pytest.raises(ValidationError, match="requires a substantiated row"):
        EligibilitySourceRow.model_validate(text_row(status="PARSED_UNCERTAIN", use="SAFE_WITH_CONSTRAINT",
                                                     engine_constraint="within the stated grade"))


def test_a_substantiated_computing_row_passes():
    assert EligibilitySourceRow.model_validate(text_row()).engine_use.value == "CONDITIONAL_ON_DECLARED_RELEVANCE"
    # an uncertain extraction whose row text was confirmed by geometry may be computing, if nothing else is uncertain
    confirmed = text_row(status="PARSED_UNCERTAIN",
                         raw_row_text=official("8th grade pass || 1", 3, status="CONFIRMED_BY_GEOMETRY",
                                               engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE"))
    assert EligibilitySourceRow.model_validate(confirmed)


def test_one_uncertain_required_text_blocks_a_computing_row_even_if_the_row_text_is_confirmed():
    confirmed = text_row(status="PARSED_UNCERTAIN",
                         raw_row_text=official("8th grade pass || 1", 3, status="CONFIRMED_BY_GEOMETRY",
                                               engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE"),
                         raw_academic_or_skill=official("8th grade pass", 4, status="PARSED_UNCERTAIN"))
    with pytest.raises(ValidationError, match="refused while raw_academic_or_skill is PARSED_UNCERTAIN"):
        EligibilitySourceRow.model_validate(confirmed)


def test_an_unknown_row_with_uncertain_source_data_passes():
    unknown = row(raw_academic_or_skill=official("x", 4, status="PARSED_UNCERTAIN"))
    assert EligibilitySourceRow.model_validate(unknown).engine_use.value == "UNKNOWN"


def test_audit_hints_alone_never_make_an_uncertain_row_computing():
    hint = {"overlay_id": "OV-001", "field": "raw_required_experience", "engine_use": "SAFE_HARD_RULE",
            "engine_constraint": "experience_years = 0"}
    assert EligibilitySourceRow.model_validate(row(audit_hints=[hint])).engine_use.value == "UNKNOWN"
    with pytest.raises(ValidationError, match="cannot be safer than the row's own row-level component"):
        EligibilitySourceRow.model_validate(row(audit_hints=[hint], engine_use="SAFE_HARD_RULE"))
    with pytest.raises(ValidationError, match="requires a substantiated row"):
        EligibilitySourceRow.model_validate(text_row(status="PARSED_UNCERTAIN", audit_hints=[hint]))


def test_engine_constraint_is_verbatim_optional_and_round_trips():
    wording = "education >= '8th grade pass'; experience_years >= 1.0; relevance is a user declaration"
    r = EligibilitySourceRow.model_validate(text_row(engine_constraint=wording))
    assert r.engine_constraint == wording
    assert EligibilitySourceRow.model_validate_json(r.model_dump_json()) == r
    assert EligibilitySourceRow.model_validate(text_row()).engine_constraint is None
    plain = EligibilitySourceRow.model_validate(row())
    assert plain.model_dump(mode="json")["engine_constraint"] is None
    with pytest.raises(ValidationError):
        EligibilitySourceRow.model_validate(text_row(engine_constraint=""))


def test_a_constraint_never_changes_the_use_and_safe_with_constraint_needs_one():
    unknown = EligibilitySourceRow.model_validate(row(engine_constraint="parseable, but literacy is not modelled"))
    assert unknown.engine_use.value == "UNKNOWN"
    with pytest.raises(ValidationError, match="SAFE_WITH_CONSTRAINT requires the engine_constraint"):
        EligibilitySourceRow.model_validate(text_row(use="SAFE_WITH_CONSTRAINT"))
    assert EligibilitySourceRow.model_validate(text_row(use="SAFE_WITH_CONSTRAINT", engine_constraint="Grade 9 only"))
