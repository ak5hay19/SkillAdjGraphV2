"""P1.5 Checkpoint B: the eligibility structuring layer, on synthetic source rows only (codes are TEST/…).

Numbers 1-11 refer to the Checkpoint B tests recorded in TASKS.md (P1.5). The real-data checks are in
tests/integration/test_eligibility_rules_real.py.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from skillgraph.curation import eligibility_rules as er
from skillgraph.curation.eligibility_rules import (
    DELIMITER,
    AgeRuleBlocked,
    CorrectionNotSupported,
    EligibilityRulesError,
)
from skillgraph.model.eligibility import ComponentType, EligibilitySourceRow, UnknownReasonCode
from skillgraph.model.evidence import EngineUse, ValueStatus
from model_factory import ev

REPO = Path(__file__).resolve().parents[2]
CODE = "TEST/Q9001"
REL = "CONDITIONAL_ON_DECLARED_RELEVANCE"


# --------------------------------------------------------------------------------------------- synthetic fixtures
def valued(value, n, *, status="TRANSCRIBED", use="UNKNOWN", **extra) -> dict:
    return {"value": value, "evidence_class": "OFFICIAL", "evidence_id": ev(n), "value_status": status,
            "engine_use": use, **extra}


def src(s_no=1, academic="10th Grade pass", experience="1.5-year relevant experience", *, row_use=REL,
        status="TRANSCRIBED", academic_kw=None, experience_kw=None, **over) -> EligibilitySourceRow:
    text = academic + DELIMITER + experience
    data = {
        "id": f"rule:{CODE}/E{s_no}", "qualification_id": f"qual:{CODE}", "kind": "ELIGIBILITY_ROW", "s_no": s_no,
        "raw_academic_or_skill": valued(academic, 10 + s_no, **(academic_kw or {})),
        "raw_required_experience": valued(experience, 20 + s_no, **(experience_kw or {})),
        "raw_row_text": valued(text, 30 + s_no, use=row_use),
        "extraction_status": status, "engine_use": row_use, "overlay_ids": ["OV-020"], **over}
    return EligibilitySourceRow.model_validate(data)


def age_src(*, text=None, **over) -> EligibilitySourceRow:
    data = {"id": f"rule:{CODE}/AGE", "qualification_id": f"qual:{CODE}", "kind": "AGE_9C",
            "min_age": valued(18, 40, use="SAFE_HARD_RULE", status="CONFIRMED_BY_GEOMETRY"),
            "extraction_status": "TRANSCRIBED", "engine_use": "SAFE_HARD_RULE", "overlay_ids": ["OV-030"], **over}
    if text is not None:
        data["raw_row_text"] = valued(text, 41)
    return EligibilitySourceRow.model_validate(data)


def comp(cell, text, type_, params, safe_from="row", **kw) -> dict:
    return {"cell": cell, "text": text, "type": type_, "params": params, "safe_from": safe_from, **kw}


def rule(s_no=1, components=None, *, academic="10th Grade pass", experience="1.5-year relevant experience",
         row_use=REL, **kw) -> dict:
    return {"id": f"rule:{CODE}/E{s_no}", "review": "SUPPORTED",
            "expect": {"row_engine_use": row_use, "row_text": academic + DELIMITER + experience},
            "components": components if components is not None else [
                comp("academic", academic, "SCHOOL_GRADE_MIN", {"grade": 10}),
                comp("experience", experience, "EXPERIENCE_MIN_YEARS", {"years": 1.5}, requires_relevance=True)], **kw}


def age_rule() -> dict:
    return {"id": f"rule:{CODE}/AGE", "review": "SUPPORTED",
            "expect": {"row_engine_use": "SAFE_HARD_RULE", "min_age": "18"},
            "components": [comp("min_age", "18", "AGE_MIN", {"min_age": 18})]}


def cfg(*rules) -> er.RulesConfig:
    return er.parse_rules_config({"rules": list(rules)})


def cfg_of(rule_dict: dict):
    return er.parse_rules_config({"rules": [rule_dict]}).rules[0]


# ------------------------------------------------------------------------------------------ 1. count, 2. order
def test_1_one_component_per_printed_cell():
    row = er.structure_row(src(), cfg_of(rule()))
    assert [c.type for c in row.components] == [ComponentType.SCHOOL_GRADE_MIN, ComponentType.EXPERIENCE_MIN_YEARS]
    assert len(er.structure_components(age_src(), cfg_of(age_rule()))) == 1
    one = rule(components=[comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10})])
    with pytest.raises(EligibilityRulesError, match="one component per printed cell"):
        er.structure_row(src(), cfg_of(one))
    three = rule()
    three["components"] = three["components"] + [three["components"][0]]
    with pytest.raises(EligibilityRulesError, match="one component per printed cell"):
        er.structure_row(src(), cfg_of(three))
    with pytest.raises(EligibilityRulesError, match="one component per printed cell"):
        er.structure_components(age_src(), cfg_of({**age_rule(), "components": age_rule()["components"] * 2}))


def test_2_components_follow_the_printed_cell_order_and_ids_are_deterministic():
    swapped = rule()
    swapped["components"] = list(reversed(swapped["components"]))
    with pytest.raises(EligibilityRulesError, match="printed order"):
        er.structure_row(src(), cfg_of(swapped))
    assert er.component_id(f"rule:{CODE}/E1", 1) == f"rule:{CODE}/E1#c1"
    assert er.component_id(f"rule:{CODE}/AGE", 1) == f"rule:{CODE}/AGE#c1"
    with pytest.raises(ValueError):
        er.component_id("rule:TEST/Q9001/E1", 0)


# ------------------------------------------------------------------------ 3. verbatim, 4. empty, 5. delimiters
def test_3_text_round_trips_exactly():
    row = er.structure_row(src(), cfg_of(rule()))
    academic, experience = er.split_cells(row.raw_text)
    assert (academic, experience) == ("10th Grade pass", "1.5-year relevant experience")
    assert academic + DELIMITER + experience == row.raw_text
    bad = rule()
    bad["components"][0] = comp("academic", "10th Grade Pass", "SCHOOL_GRADE_MIN", {"grade": 10})
    with pytest.raises(EligibilityRulesError, match="source cell is"):
        er.structure_row(src(), cfg_of(bad))
    with pytest.raises(EligibilityRulesError, match="no ' \\|\\| ' delimiter"):
        er.split_cells("no delimiter here")


def test_4_empty_experience_cell_keeps_its_trailing_delimiter_and_is_never_trimmed():
    empty = src(2, "Completed 1st year of 3-year diploma after 10th.", "", row_use="UNKNOWN", status="PARSED_UNCERTAIN",
                academic_kw={"status": "PARSED_UNCERTAIN"}, experience_kw={"status": "PARSED_UNCERTAIN"},
                pending_overlay_ids=["OV-002"],
                flags=[{"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "pending", "refs": ["OV-002"]}])
    rule2 = rule(2, [comp("academic", "Completed 1st year of 3-year diploma after 10th.", "UNMODELLED", {}, "none",
                          unknown_reason="DIPLOMA_YEAR_NOT_MODELLED"),
                     comp("experience", "", "UNMODELLED", {}, "none", unknown_reason="OVERLAY_NOT_APPROVED")],
                 academic="Completed 1st year of 3-year diploma after 10th.", experience="", row_use="UNKNOWN")
    row = er.structure_row(empty, cfg_of(rule2))
    assert row.raw_text.endswith(DELIMITER) and row.raw_text.endswith(" || ")
    assert er.split_cells(row.raw_text) == ("Completed 1st year of 3-year diploma after 10th.", "")
    assert row.components[1].unknown_reason is UnknownReasonCode.OVERLAY_NOT_APPROVED
    assert "years" not in row.components[1].params  # nothing is back-filled
    # A source whose row text was trimmed no longer reproduces the join: refused, not repaired.
    trimmed = empty.model_copy(update={"raw_row_text": empty.raw_row_text.model_copy(update={"value": empty.raw_row_text.value.rstrip()})})
    with pytest.raises(EligibilityRulesError, match="do not reproduce raw_text|row text changed"):
        er.structure_row(trimmed, cfg_of(rule2))
    # OVERLAY_NOT_APPROVED needs an empty cell and a pending proposal.
    no_pending = empty.model_copy(update={"pending_overlay_ids": [], "flags": []})
    with pytest.raises(EligibilityRulesError, match="OVERLAY_NOT_APPROVED is only"):
        er.structure_row(no_pending, cfg_of(rule2))


def test_4_the_join_check_alone_catches_a_row_text_that_is_not_the_cells_joined():
    """The table is made to agree with the (wrong) row text, so only the join check can object."""
    base = src(2, "8th Grade pass", "")
    for wrong in ("8th Grade pass ||", "8th Grade pass  ||  ", "8th Grade pass"):
        text = base.raw_row_text.model_copy(update={"value": wrong})
        source = base.model_copy(update={"raw_row_text": text})
        table = rule(2, [comp("academic", "8th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                         comp("experience", "", "UNMODELLED", {}, "none", unknown_reason="LITERACY_NOT_MODELLED")],
                     academic="8th Grade pass", experience="")
        table["expect"]["row_text"] = wrong
        with pytest.raises(EligibilityRulesError, match="do not reproduce raw_text"):
            er.structure_row(source, cfg_of(table))


def test_5_ambiguous_or_embedded_delimiters_are_rejected():
    embedded = src(1, "Grade 8 || pass", "1 year relevant experience")  # three cells' worth of delimiters
    r = rule(1, [comp("academic", "Grade 8 || pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                 comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, requires_relevance=True)],
             academic="Grade 8 || pass", experience="1 year relevant experience")
    with pytest.raises(EligibilityRulesError, match="contains the delimiter"):
        er.structure_row(embedded, cfg_of(r))
    in_experience = src(1, "Grade 8 pass", "None || at all")
    unmodelled = rule(1, [comp("academic", "Grade 8 pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                          comp("experience", "None || at all", "UNMODELLED", {}, "none", unknown_reason="REVIEW_FLAG")],
                      academic="Grade 8 pass", experience="None || at all")
    with pytest.raises(EligibilityRulesError, match="contains the delimiter"):
        er.structure_row(in_experience, cfg_of(unmodelled))


# ------------------------------------------------------------------------------------------ 6. stale or inconsistent
def test_6_stale_or_inconsistent_mappings_fail_closed():
    with pytest.raises(EligibilityRulesError, match="engine_use"):
        er.structure_row(src(row_use="CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG"), cfg_of(rule()))
    changed = rule()
    changed["expect"]["row_text"] = "10th Grade pass || 2-year relevant experience"
    with pytest.raises(EligibilityRulesError, match="row text changed"):
        er.structure_row(src(), cfg_of(changed))
    with pytest.raises(EligibilityRulesError, match="not SUPPORTED"):
        er.structure_row(src(), cfg_of({**rule(), "review": "NEEDS_REVIEW"}))
    with pytest.raises(EligibilityRulesError, match="mapped by the entry"):
        er.structure_row(src(2), cfg_of(rule(1)))


def test_6_the_table_and_the_source_must_cover_the_same_rows():
    full = cfg(rule(1), rule(2))
    with pytest.raises(EligibilityRulesError, match="no mapping for"):
        er.structure_all([src(1), src(2), src(3)], full)
    with pytest.raises(EligibilityRulesError, match="mapping without a source row"):
        er.structure_all([src(1)], full)
    with pytest.raises(EligibilityRulesError, match="duplicate source rows"):
        er.structure_all([src(1), src(1)], cfg(rule(1)))
    with pytest.raises(EligibilityRulesError, match="duplicate rule mappings"):
        cfg(rule(1), rule(1))


def test_6_wrong_row_kind_for_the_table_entry():
    with pytest.raises(EligibilityRulesError, match="needs expect.min_age only"):
        er.structure_components(age_src(), cfg_of({**age_rule(), "expect": {"row_engine_use": "SAFE_HARD_RULE", "row_text": "x"}}))
    with pytest.raises(EligibilityRulesError, match="needs expect.row_text only"):
        er.structure_row(src(), cfg_of({**rule(), "expect": {"row_engine_use": REL, "min_age": "18"}}))


# --------------------------------------------------------------------------------- 7. the safe/reason invariant
def test_7_safe_false_needs_a_reason_and_safe_true_has_none():
    safe_row = er.structure_row(src(), cfg_of(rule()))
    assert all(c.safe and c.unknown_reason is None for c in safe_row.components)
    for c in safe_row.components:
        er.check_component_invariant(c)
    template = safe_row.components[0]
    with pytest.raises(EligibilityRulesError, match="safe component cannot carry"):
        er.check_component_invariant(template.model_copy(update={"unknown_reason": UnknownReasonCode.REVIEW_FLAG}))
    with pytest.raises(EligibilityRulesError, match="needs a static unknown_reason"):
        er.check_component_invariant(template.model_copy(update={"safe": False}))


def test_7_a_computed_unsafe_component_without_a_configured_reason_fails_the_build():
    unknown_row = src(1, "10th Grade pass", "1 year relevant experience", row_use="UNKNOWN")
    r = rule(1, [comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}),
                 comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, requires_relevance=True)],
             academic="10th Grade pass", experience="1 year relevant experience", row_use="UNKNOWN")
    with pytest.raises(EligibilityRulesError, match="gives no unknown_reason"):
        er.structure_row(unknown_row, cfg_of(r))


def test_7_the_configured_reason_applies_only_while_the_computed_safe_is_false():
    r = rule()
    r["components"][0]["unknown_reason"] = "UNCERTAIN_EXTRACTION"  # row is a computing, substantiated one: safe wins
    row = er.structure_row(src(), cfg_of(r))
    assert row.components[0].safe and row.components[0].unknown_reason is None


# ---------------------------------------------------------------------------------------- 8. requires_relevance
def test_8_requires_relevance_is_a_field_and_is_projected_into_response_params():
    row = er.structure_row(src(), cfg_of(rule()))
    grade, experience = row.components
    assert experience.requires_relevance is True and "requires_relevance" not in experience.params
    assert er.response_params(experience) == {"years": 1.5, "requires_relevance": True}
    assert er.response_params(grade) == {"grade": 10} and grade.requires_relevance is False
    for c in row.components:
        assert "requires_relevance" not in c.params
    with pytest.raises(EligibilityRulesError, match="does not take params"):
        cfg_of(rule(components=[comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10, "requires_relevance": True}),
                                rule()["components"][1]]))
    with pytest.raises(EligibilityRulesError, match="requires_relevance applies only"):
        cfg_of(rule(components=[comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}, requires_relevance=True),
                                rule()["components"][1]]))


# ------------------------------------------------------------------------------------------ 9. pending overlays
def test_9_pending_overlays_are_never_overlay_ids_and_must_be_named_in_the_flag():
    flag = {"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "pending", "refs": ["OV-002"]}
    pending = src(pending_overlay_ids=["OV-002"], flags=[flag])
    row = er.structure_row(pending, cfg_of(rule()))
    assert row.overlay_ids == ["OV-020"] and "OV-002" not in row.overlay_ids
    assert [f.refs for f in row.flags] == [["OV-002"]]
    with pytest.raises(EligibilityRulesError, match="not named in an OVERLAY_PENDING_APPROVAL flag"):
        er.structure_row(src(pending_overlay_ids=["OV-002"]), cfg_of(rule()))
    with pytest.raises(EligibilityRulesError, match="both decided and pending"):
        er.structure_row(src(pending_overlay_ids=["OV-020"], flags=[{**flag, "refs": ["OV-020"]}]), cfg_of(rule()))


# ----------------------------------------------------------------------------------- 10. no upgrade of any kind
def test_10_a_row_that_is_unknown_never_makes_a_component_safe_through_the_row():
    r = src(1, "10th Grade pass", "1 year relevant experience", row_use="UNKNOWN")
    table = rule(1, [comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}, unknown_reason="ENGINE_USE_UNDECIDED"),
                     comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0},
                          requires_relevance=True, unknown_reason="ENGINE_USE_UNDECIDED")],
                 academic="10th Grade pass", experience="1 year relevant experience", row_use="UNKNOWN")
    row = er.structure_row(r, cfg_of(table))
    assert row.engine_use.value == "UNKNOWN"
    assert [c.safe for c in row.components] == [False, False]
    assert {c.unknown_reason for c in row.components} == {UnknownReasonCode.ENGINE_USE_UNDECIDED}


def test_10_a_safe_sibling_is_not_evidence_and_the_row_stays_unknown():
    r = src(1, "11th Grade pass", "No Experience required", row_use="UNKNOWN", status="PARSED_UNCERTAIN",
            academic_kw={"status": "PARSED_UNCERTAIN"},
            experience_kw={"status": "CONFIRMED_BY_GEOMETRY", "use": "SAFE_HARD_RULE"})
    table = rule(1, [comp("academic", "11th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 11}, "cell", unknown_reason="UNCERTAIN_EXTRACTION"),
                     comp("experience", "No Experience required", "EXPERIENCE_MIN_YEARS", {"years": 0.0}, "cell")],
                 academic="11th Grade pass", experience="No Experience required", row_use="UNKNOWN")
    row = er.structure_row(r, cfg_of(table))
    assert [c.safe for c in row.components] == [False, True]  # the Q2301/E1 shape: only the supported cell evaluates
    assert row.engine_use.value == "UNKNOWN"


def test_10_an_uncertain_cell_is_never_safe_even_if_the_cell_states_a_safe_use():
    r = src(1, "11th Grade pass", "No Experience required", row_use="UNKNOWN", status="PARSED_UNCERTAIN",
            experience_kw={"status": "PARSED_UNCERTAIN", "use": "SAFE_HARD_RULE"})
    table = rule(1, [comp("academic", "11th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 11}, "none", unknown_reason="ENGINE_USE_UNDECIDED"),
                     comp("experience", "No Experience required", "EXPERIENCE_MIN_YEARS", {"years": 0.0}, "cell", unknown_reason="UNCERTAIN_EXTRACTION")],
                 academic="11th Grade pass", experience="No Experience required", row_use="UNKNOWN")
    row = er.structure_row(r, cfg_of(table))
    assert row.components[1].safe is False and row.components[1].unknown_reason is UnknownReasonCode.UNCERTAIN_EXTRACTION


def test_10_reason_codes_are_only_used_for_what_they_mean():
    transcribed = src(1, "10th Grade pass", "5 year relevant experience", row_use="UNKNOWN")
    base = lambda reason: rule(1, [  # noqa: E731
        comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}, "none", unknown_reason="ENGINE_USE_UNDECIDED"),
        comp("experience", "5 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 5.0}, "cell",
             requires_relevance=True, unknown_reason=reason)],
        academic="10th Grade pass", experience="5 year relevant experience", row_use="UNKNOWN")
    row = er.structure_row(transcribed, cfg_of(base("ENGINE_USE_UNDECIDED")))  # the Q0301/E5 shape
    assert row.components[1].unknown_reason is UnknownReasonCode.ENGINE_USE_UNDECIDED and not row.components[1].safe
    with pytest.raises(EligibilityRulesError, match="UNCERTAIN_EXTRACTION is only for an uncertain cell"):
        er.structure_row(transcribed, cfg_of(base("UNCERTAIN_EXTRACTION")))  # never for a TRANSCRIBED cell
    uncertain = src(1, "10th Grade pass", "5 year relevant experience", row_use="UNKNOWN", status="PARSED_UNCERTAIN",
                    academic_kw={"status": "PARSED_UNCERTAIN"}, experience_kw={"status": "PARSED_UNCERTAIN"})
    with pytest.raises(EligibilityRulesError, match="ENGINE_USE_UNDECIDED is only for a parsed"):
        er.structure_row(uncertain, cfg_of(base("ENGINE_USE_UNDECIDED")))


def test_10_a_conflicted_cell_cannot_be_a_computing_input():
    r = src(1, "10th Grade pass", "1 year relevant experience", row_use="UNKNOWN",
            experience_kw={"conflict_id": "conflict:OV-036"})
    table = rule(1, [comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}, "none", unknown_reason="ENGINE_USE_UNDECIDED"),
                     comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, "row",
                          requires_relevance=True)],
                 academic="10th Grade pass", experience="1 year relevant experience", row_use="UNKNOWN")
    # The row is UNKNOWN, so the component is unsafe and the missing reason is reported; nothing is silently accepted.
    with pytest.raises(EligibilityRulesError):
        er.structure_row(r, cfg_of(table))


# ----------------------------------------------------------- 11. unsupported types, parameters and the age rule
@pytest.mark.parametrize("bad, match", [
    ({"type": "NOT_A_TYPE"}, "type"),
    ({"type": "EQUIVALENCE"}, "type"),  # no component type exists for equivalence, exemption, RPL or reduced hours
    ({"type": "EXPERIENCE_MIN_YEARS", "params": {"years": 3}}, "must be float"),
    ({"type": "EXPERIENCE_MIN_YEARS", "params": {"years": True}}, "must be float"),
    ({"type": "EXPERIENCE_MIN_YEARS", "params": {"years": "3.0"}}, "must be float"),
    ({"type": "EXPERIENCE_MIN_YEARS", "params": {"years": -1.0}}, "years must be"),
    ({"type": "EXPERIENCE_MIN_YEARS", "params": {}}, "requires params"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 10.0}}, "must be int"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 13}}, "grade must be"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 9, "below_required_verdict": "NOT_MET"}}, "only 'UNKNOWN'"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 9, "mystery": 1}}, "does not take params"),
    ({"type": "NAMED_CREDENTIAL", "params": {"credential": "UG Diploma"}}, "credential must be"),
    ({"type": "NAMED_CREDENTIAL", "params": {"credential": "OTHER"}}, "credential must be"),
    ({"type": "PRIOR_NSQF_LEVEL", "params": {"level": 2.25}}, "steps of 0.5"),
    ({"type": "PRIOR_NSQF_LEVEL", "params": {"level": 3}}, "must be float"),
    ({"type": "AGE_MIN", "params": {"min_age": 18.0}}, "must be int"),
    ({"type": "UNMODELLED", "params": {"x": 1}, "safe_from": "none", "unknown_reason": "REVIEW_FLAG"}, "does not take params"),
    ({"type": "UNMODELLED", "params": {}, "safe_from": "none"}, "needs safe_from 'none' and an unknown_reason"),
    ({"type": "UNMODELLED", "params": {}, "safe_from": "row", "unknown_reason": "REVIEW_FLAG"}, "needs safe_from 'none'"),
    ({"type": "UNMODELLED", "params": {}, "safe_from": "none", "unknown_reason": "REVIEW_FLAG", "or_equivalent": True},
     "or_equivalent applies only"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 9}, "unknown_reason": "NOT_A_REASON"}, "unknown_reason"),
    ({"type": "SCHOOL_GRADE_MIN", "params": {"grade": 9}, "safe_from": "everywhere"}, "safe_from"),
])
def test_11_invalid_types_enums_and_parameters_are_rejected(bad, match):
    base = comp("academic", "x", "SCHOOL_GRADE_MIN", {"grade": 9})
    with pytest.raises(EligibilityRulesError, match=match):
        cfg_of(rule(components=[{**base, **bad}, rule()["components"][1]]))


def test_11_unknown_keys_and_malformed_files_are_rejected(tmp_path):
    with pytest.raises(EligibilityRulesError):
        er.parse_rules_config({"rules": [], "extra": 1})
    with pytest.raises(EligibilityRulesError):
        er.parse_rules_config({"rules": [{**rule(), "surprise": True}]})
    with pytest.raises(EligibilityRulesError, match="at least one component"):
        cfg_of({**rule(), "components": []})
    bad = tmp_path / "rules.yaml"
    bad.write_text("rules: [unclosed", encoding="utf-8")
    with pytest.raises(EligibilityRulesError, match="cannot read"):
        er.load_rules_config(bad)
    with pytest.raises(EligibilityRulesError, match="cannot read"):
        er.load_rules_config(tmp_path / "missing.yaml")


def test_11_the_age_rule_is_blocked_while_the_source_has_no_verbatim_text():
    table = cfg_of(age_rule())
    components = er.structure_components(age_src(), table)  # the component itself is fine
    assert [c.type for c in components] == [ComponentType.AGE_MIN] and components[0].safe
    with pytest.raises(AgeRuleBlocked, match="P1.5-A1"):
        er.structure_age_rule(age_src(), table)
    structured = er.structure_all([age_src(), src()], cfg(age_rule(), rule()), allow_blocked=True)
    assert structured.age_rules == () and list(structured.blocked) == [f"rule:{CODE}/AGE"]
    assert [c.type for c in structured.age_components[f"rule:{CODE}/AGE"]] == [ComponentType.AGE_MIN]
    with pytest.raises(AgeRuleBlocked, match="P1.5-A1"):
        er.structure_all([age_src(), src()], cfg(age_rule(), rule()))
    with pytest.raises(AgeRuleBlocked):
        er.assemble_specs(structured)


def test_11_a_stale_age_table_is_reported_before_the_age_block():
    stale = {**age_rule(), "expect": {"row_engine_use": "SAFE_HARD_RULE", "min_age": "20"}}
    with pytest.raises(EligibilityRulesError, match="minimum age changed"):
        er.structure_age_rule(age_src(), cfg_of(stale))


def test_11_only_a_synthetic_source_that_carries_the_text_and_evidence_builds_an_age_rule():
    """The code path exists for when the provenance does (A1 option a). The real source does not carry it."""
    built = er.structure_age_rule(age_src(text="Age: 18 years"), cfg_of(age_rule()))
    assert built.raw_text == "Age: 18 years" and built.id == f"rule:{CODE}/AGE"
    structured = er.structure_all([age_src(text="Age: 18 years"), src(), src(2, "8th Grade pass", "1 year relevant experience")],
                                  cfg(age_rule(), rule(), rule(2, [comp("academic", "8th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                                                                 comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, requires_relevance=True)],
                                                                 academic="8th Grade pass", experience="1 year relevant experience")))
    specs = er.assemble_specs(structured)
    assert [r.s_no for r in specs[CODE].rows] == [1, 2] and specs[CODE].age_rule.id.endswith("/AGE")


def test_11_no_component_type_exists_for_equivalence_exemption_rpl_or_reduced_hours():
    assert {t.value for t in ComponentType} == {"AGE_MIN", "SCHOOL_GRADE_MIN", "NAMED_CREDENTIAL", "PRIOR_NSQF_LEVEL",
                                                "EXPERIENCE_MIN_YEARS", "UNMODELLED"}


# ------------------------------------------------------------------------------- approved corrections (A2)
def test_a2_an_applied_correction_on_any_used_cell_fails_closed():
    corrected = {"value_status": ValueStatus.CORRECTION_APPLIED, "source_value": "", "source_evidence_id": ev(99)}
    experience = src(2, "8th Grade pass", "No Experience required",
                     experience_kw={"status": "CORRECTION_APPLIED", "source_value": "", "source_evidence_id": ev(99)})
    table = rule(2, [comp("academic", "8th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                     comp("experience", "No Experience required", "EXPERIENCE_MIN_YEARS", {"years": 0.0})],
                 academic="8th Grade pass", experience="No Experience required")
    with pytest.raises(CorrectionNotSupported, match="P1.5-A2"):
        er.structure_row(experience, cfg_of(table))
    row_text = src(2, "8th Grade pass", "No Experience required")
    changed = row_text.model_copy(update={"raw_row_text": row_text.raw_row_text.model_copy(update=corrected)})
    with pytest.raises(CorrectionNotSupported, match="row text"):
        er.structure_row(changed, cfg_of(table))
    with pytest.raises(CorrectionNotSupported):
        er.structure_age_rule(age_src(min_age=valued(18, 40, use="SAFE_HARD_RULE", status="CORRECTION_APPLIED",
                                                      source_value="17", source_evidence_id=ev(98))), cfg_of(age_rule()))


# ------------------------------------------------------------------------------------------------- determinism
def test_output_is_deterministic_and_independent_of_input_order():
    a = [age_src(text="Age: 18 years"), src(1), src(2, "8th Grade pass", "1 year relevant experience")]
    table = cfg(age_rule(), rule(1), rule(2, [comp("academic", "8th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 8}),
                                              comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, requires_relevance=True)],
                                  academic="8th Grade pass", experience="1 year relevant experience"))

    def dump(rows):
        s = er.structure_all(rows, table)
        return [m.model_dump_json() for m in (*s.age_rules, *s.rows)]

    assert dump(a) == dump(a) == dump(list(reversed(a))) == dump(copy.deepcopy(a))


# --------------------------------------------------------------- the real configuration file (no source data needed)
@pytest.fixture(scope="module")
def real_config() -> er.RulesConfig:
    return er.load_rules_config(REPO / er.RULES_PATH)


def test_the_repository_table_loads_and_covers_28_rows_with_52_components(real_config):
    ids = [r.id for r in real_config.rules]
    assert len(ids) == len(set(ids)) == 28
    assert sum(len(r.components) for r in real_config.rules) == 52
    assert all(r.review is er.Review.SUPPORTED for r in real_config.rules)
    assert sum(1 for i in ids if i.endswith("/AGE")) == 4


def test_the_repository_table_conventions(real_config):
    components = {f"{r.id}#c{n}": c for r in real_config.rules for n, c in enumerate(r.components, start=1)}
    assert {k for k, c in components.items() if c.or_equivalent} == {"rule:AMH/Q2101/E1#c1", "rule:AMH/Q2101/E3#c1"}
    assert {k for k, c in components.items() if "below_required_verdict" in c.params} == {"rule:AMH/Q0301/E1#c1"}
    assert components["rule:AMH/Q2101/E3#c1"].type is ComponentType.SCHOOL_GRADE_MIN
    assert components["rule:AMH/Q2301/E6#c1"].type is ComponentType.UNMODELLED and not components["rule:AMH/Q2301/E6#c1"].or_equivalent
    assert {c.params["credential"] for c in components.values() if c.type is ComponentType.NAMED_CREDENTIAL} == {"UG_DIPLOMA", "UG_CERTIFICATE"}
    assert all("requires_relevance" not in c.params for c in components.values())
    assert all(isinstance(c.params.get("years", 0.0), float) and isinstance(c.params.get("level", 0.0), float)
               for c in components.values())
    assert all(c.safe_from is er.SafeFrom.NONE for c in components.values() if c.type is ComponentType.UNMODELLED)


def test_the_four_cell_audit_request_is_recorded_as_a_request_only(real_config):
    (request,) = real_config.audit_review_requests
    assert request.status == "OPEN_REQUEST_ONLY"
    assert request.cells == ["rule:AMH/Q2301/E5#c2", "rule:AMH/Q2301/E6#c2", "rule:AMH/Q0301/E2#c2", "rule:AMH/Q0301/E5#c2"]


def test_overlay_approvals_are_untouched_by_this_layer():
    assert yaml.safe_load((REPO / "config" / "overlay_approvals.yaml").read_text(encoding="utf-8")) == {"approved": []}
    assert "overlay_approvals" not in Path(er.__file__).read_text(encoding="utf-8").replace("config/overlay_approvals", "")


def test_the_build_uses_this_layer_and_the_code_version_records_it():
    """Checkpoint C: the build structures the rules, so the output changed and the version moved with it."""
    from skillgraph.curation import build, config

    assert "structure_eligibility" in Path(build.__file__).read_text(encoding="utf-8")
    assert config.CURATION_CODE_VERSION == "p1.5-1"


# =============================================================================================================
# Hardening (independent review): one regression test per confirmed weakness.
# =============================================================================================================
def _rules_yaml(tmp_path, text: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_hardening_non_finite_numbers_are_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(EligibilityRulesError, match="finite"):
            cfg_of(rule(components=[comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}),
                                    comp("experience", "1.5-year relevant experience", "EXPERIENCE_MIN_YEARS",
                                         {"years": bad}, requires_relevance=True)]))


def test_hardening_a_duplicate_yaml_key_is_an_error_not_last_wins(tmp_path):
    body = ("rules:\n  - id: 'rule:TEST/Q9001/AGE'\n    review: SUPPORTED\n    review: NEEDS_REVIEW\n"
            "    expect: {row_engine_use: SAFE_HARD_RULE, min_age: '18'}\n"
            "    components: [{cell: min_age, text: '18', type: AGE_MIN, params: {min_age: 18}, safe_from: row}]\n")
    with pytest.raises(EligibilityRulesError, match="duplicate key"):
        er.load_rules_config(_rules_yaml(tmp_path, body))
    with pytest.raises(EligibilityRulesError, match="duplicate key"):
        er.load_rules_config(_rules_yaml(tmp_path, "rules: []\nrules: []\n"))
    with pytest.raises(EligibilityRulesError, match="duplicate key"):
        er.load_rules_config(_rules_yaml(tmp_path, "rules: []\nconventions: {a: 1, a: 2}\n"))
    assert er.load_rules_config(_rules_yaml(tmp_path, "rules: []\n")).rules == []


@pytest.mark.parametrize("cell, type_, params, text", [
    ("academic", "AGE_MIN", {"min_age": 18}, "18"),
    ("experience", "SCHOOL_GRADE_MIN", {"grade": 10}, "10th Grade pass"),
    ("academic", "EXPERIENCE_MIN_YEARS", {"years": 3.0}, "3 year relevant experience"),
    ("min_age", "SCHOOL_GRADE_MIN", {"grade": 10}, "10"),
    ("min_age", "UNMODELLED", {}, "18"),
    ("experience", "PRIOR_NSQF_LEVEL", {"level": 3.0}, "Previous relevant Qualification of NSQF Level 3"),
    ("experience", "NAMED_CREDENTIAL", {"credential": "UG_DIPLOMA"}, "UG Diploma"),
])
def test_hardening_a_type_can_only_be_read_from_its_own_cell(cell, type_, params, text):
    extra = {"unknown_reason": "REVIEW_FLAG", "safe_from": "none"} if type_ == "UNMODELLED" else {}
    with pytest.raises(EligibilityRulesError, match="cannot be read from the"):
        cfg_of(rule(components=[{**comp(cell, text, type_, params), **extra}, rule()["components"][1]]))


@pytest.mark.parametrize("component, match", [
    (comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 11}), "grade 11 is not in the text"),
    (comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 1}), "grade 1 is not in the text"),
    (comp("academic", "Grade 9", "SCHOOL_GRADE_MIN", {"grade": 9}, or_equivalent=True), "or_equivalent must hold exactly"),
    (comp("academic", "Grade 9 pass", "SCHOOL_GRADE_MIN", {"grade": 9, "below_required_verdict": "UNKNOWN"}),
     "only for a grade printed without"),
    (comp("academic", "12th or Equivalent", "SCHOOL_GRADE_MIN", {"grade": 12}), "or_equivalent must hold exactly"),
    (comp("academic", "UG Certificate", "NAMED_CREDENTIAL", {"credential": "UG_DIPLOMA"}), "not what the text names"),
    (comp("academic", "Previous relevant Qualification of NSQF Level 2.5", "PRIOR_NSQF_LEVEL", {"level": 3.0},
          requires_relevance=True), "level 3 is not"),
    (comp("academic", "Previous relevant Qualification of NSQF Level 3", "PRIOR_NSQF_LEVEL", {"level": 3.0}),
     "requires_relevance must hold"),
    (comp("academic", "Previous qualification of NSQF Level 3", "PRIOR_NSQF_LEVEL", {"level": 3.0}, requires_relevance=True),
     "requires_relevance must hold"),
    (comp("experience", "1.5-year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 3.0}, requires_relevance=True),
     "years 3.0 differs"),
    (comp("experience", "6 months relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 6.0}, requires_relevance=True),
     "years 6.0 differs"),
    (comp("experience", "No Experience required", "EXPERIENCE_MIN_YEARS", {"years": 1.0}), "years 1.0 differs"),
    (comp("experience", "One year relevant Experience required", "EXPERIENCE_MIN_YEARS", {"years": 2.0}, requires_relevance=True),
     "years 2.0 differs"),
    (comp("experience", "three years of relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 3.0}, requires_relevance=True),
     "not one the verifier recognises"),
    (comp("experience", "1 year experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, requires_relevance=True),
     "requires_relevance must hold"),
    (comp("min_age", "20", "AGE_MIN", {"min_age": 18}), "min_age differs"),
])
def test_hardening_the_parameters_must_agree_with_the_text_the_table_quotes(component, match):
    with pytest.raises(EligibilityRulesError, match=match):
        er.parse_rules_config({"rules": [{"id": f"rule:{CODE}/E1", "review": "SUPPORTED",
                                          "expect": {"row_engine_use": "UNKNOWN", "row_text": "x || y"},
                                          "components": [{**component, "safe_from": "none", "unknown_reason": "REVIEW_FLAG"}]}]})


def test_hardening_the_text_verifier_accepts_the_wordings_of_the_real_table(real_config):
    assert len(real_config.rules) == 28  # loading already ran the verifier over all 52 components


def test_hardening_safe_hours_never_makes_an_eligibility_component_safe():
    with pytest.raises(EligibilityRulesError, match="gives no unknown_reason"):
        er.structure_row(src(row_use="SAFE_HOURS"), cfg_of(rule(row_use="SAFE_HOURS")))
    cell_hours = src(1, "10th Grade pass", "1 year relevant experience", row_use="UNKNOWN",
                     experience_kw={"use": "SAFE_HOURS"})
    table = rule(1, [comp("academic", "10th Grade pass", "SCHOOL_GRADE_MIN", {"grade": 10}, "none", unknown_reason="ENGINE_USE_UNDECIDED"),
                     comp("experience", "1 year relevant experience", "EXPERIENCE_MIN_YEARS", {"years": 1.0}, "cell",
                          requires_relevance=True, unknown_reason="ENGINE_USE_UNDECIDED")],
                 academic="10th Grade pass", experience="1 year relevant experience", row_use="UNKNOWN")
    assert er.structure_row(cell_hours, cfg_of(table)).components[1].safe is False


def test_hardening_inputs_that_skipped_their_validators_are_revalidated():
    """A row the P1.2 model refuses (a computing use on an uncertain row-level text), built with model_copy."""
    base = src()
    uncertain_text = base.raw_row_text.model_copy(update={"value_status": ValueStatus.PARSED_UNCERTAIN})
    bypassed = base.model_copy(update={"extraction_status": ValueStatus.PARSED_UNCERTAIN, "raw_row_text": uncertain_text})
    with pytest.raises(EligibilityRulesError, match="not valid"):
        er.structure_row(bypassed, cfg_of(rule()))
    with pytest.raises(EligibilityRulesError, match="not valid"):
        er.structure_components(bypassed, cfg_of(rule()))
    assert er.structure_row(base, cfg_of(rule()))  # the genuine row is fine
    table = cfg_of(rule())
    wrong_cell = table.components[0].model_copy(update={"cell": er.Cell.MIN_AGE, "type": ComponentType.AGE_MIN})
    bad_table = table.model_copy(update={"components": [wrong_cell, table.components[1]]})
    with pytest.raises(EligibilityRulesError, match="not valid"):
        er.structure_row(src(), bad_table)
    approved = table.model_copy(update={"review": "APPROVED"})  # not a Review member
    with pytest.raises(EligibilityRulesError, match="not valid"):
        er.structure_row(src(), approved)
    with pytest.raises(EligibilityRulesError, match="not valid"):
        er.structure_age_rule(age_src().model_copy(update={"min_age": None}), cfg_of(age_rule()))


def test_hardening_a_row_level_component_that_is_uncertain_cannot_back_a_row_level_use():
    """Defence in depth, below the revalidation: the row's own component is checked even on a bypassed row."""
    base = src()
    uncertain_text = base.raw_row_text.model_copy(update={"value_status": ValueStatus.PARSED_UNCERTAIN})
    bypassed = base.model_copy(update={"raw_row_text": uncertain_text})
    table = cfg_of(rule())
    with pytest.raises(EligibilityRulesError, match="not evaluable"):
        er._safe_and_reason(bypassed, er.Cell.ACADEMIC, table.components[0], "x")


def test_hardening_the_output_does_not_alias_or_change_the_source_rows():
    flag = {"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "pending", "refs": ["OV-002"]}
    source = src(pending_overlay_ids=["OV-002"], flags=[flag])
    before = source.model_dump_json()
    row = er.structure_row(source, cfg_of(rule()))
    row.flags[0].refs.append("OV-999")  # a caller mutating its result ...
    row.components[0].params["grade"] = 99
    assert source.model_dump_json() == before  # ... does not reach the source row
    assert cfg_of(rule()).components[0].params == {"grade": 10}
    assert er.structure_row(source, cfg_of(rule())).components[0].params == {"grade": 10}


def test_hardening_an_audit_request_can_only_be_a_request():
    ok = {"id": "R", "status": "OPEN_REQUEST_ONLY", "text": "t", "cells": ["rule:AMH/Q2301/E5#c2"]}
    parsed = er.parse_rules_config({"rules": [], "audit_review_requests": [ok]})
    assert parsed.audit_review_requests[0].cells == ["rule:AMH/Q2301/E5#c2"]
    for bad in ({**ok, "status": "APPROVED"}, {**ok, "status": "DECIDED"}, {**ok, "cells": ["Q2301/E5"]},
                {**ok, "cells": ["rule:AMH/Q2301/E5#c0"]}, {**ok, "approved_by": "me"}):
        with pytest.raises(EligibilityRulesError):
            er.parse_rules_config({"rules": [], "audit_review_requests": [bad]})


def test_hardening_requires_relevance_may_never_be_a_stored_param():
    c = er.structure_row(src(), cfg_of(rule())).components[1]
    smuggled = c.model_copy(update={"params": {"years": 1.5, "requires_relevance": False}})
    with pytest.raises(EligibilityRulesError, match="requires_relevance"):
        er.response_params(smuggled)
    with pytest.raises(EligibilityRulesError, match="requires_relevance"):
        er.check_component_invariant(smuggled)


# ------------------------------------------------------------------------------ static projection (API_SPEC §2.4)
def test_projection_carries_the_stored_rule_flags_without_aliasing_them():
    flag = {"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "pending", "refs": ["OV-002"]}
    stored = er.structure_row(src(pending_overlay_ids=["OV-002"], flags=[flag]), cfg_of(rule()))
    view = er.project_rule(stored)
    assert view["flags"] == [{"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "pending", "refs": ["OV-002"]}]
    view["flags"][0]["refs"].append("OV-999")  # a caller changing its view does not change the stored rule
    assert stored.flags[0].refs == ["OV-002"]
    assert er.project_rule(er.structure_row(src(), cfg_of(rule())))["flags"] == []


def test_projection_has_the_documented_key_sets_for_rows_and_age_rules():
    row = er.project_rule(er.structure_row(src(), cfg_of(rule())))
    assert set(row) == {"rule_id", "raw_text", "engine_use", "overlay_ids", "flags", "s_no", "components"}
    age = er.project_rule(er.structure_age_rule(age_src(text="Age: 18 years"), cfg_of(age_rule())))
    assert set(age) == {"rule_id", "raw_text", "engine_use", "overlay_ids", "flags", "components"}  # no s_no
    for view in (row, age):
        assert all(set(c) == {"component_id", "type", "requirement_text", "params", "evidence_ids"} for c in view["components"])
