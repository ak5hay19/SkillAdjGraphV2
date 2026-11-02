"""P3.8 unit tests: deterministic explanation templates for an eligibility result (``explain.for_eligibility``).

Synthetic registry only (``TEST/…`` codes, ``Registry.from_records``); no file, no real data. Scope: ``for_eligibility`` only.
``for_path`` and an OVERLAP item are deliberately not built (see ``explain/templates.py``), so there is no test for them.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from model_factory import CODE, age_rule, component, curated, ev, hours, official, row
from pydantic import ValidationError

from skillgraph.eligibility.evaluate import (
    EligibilityResult,
    EngineConfig,
    ExplanationItem,
    ProfileState,
    TargetDeclaration,
    evaluate,
)
from skillgraph.explain import CAVEAT_TEXT, ExplanationError, for_eligibility
from skillgraph.explain import templates as T
from skillgraph.explain.lint import find_forbidden
from skillgraph.model.conflict import Conflict
from skillgraph.model.eligibility import UnknownReasonCode, Verdict
from skillgraph.model.evidence import Evidence, EvidenceClass, QualityFlagCode
from skillgraph.model.qualification import Qualification
from skillgraph.registry import Registry, UnknownEntityError

SRC = Path(__file__).resolve().parents[2] / "src"
TEMPLATES = SRC / "skillgraph" / "explain" / "templates.py"
HELD1 = "TEST/Q9002"
N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET


# ---- fixtures ---------------------------------------------------------------------------------------------------------


def comp(kind: str) -> dict:
    """A component whose verdict depends only on the declared experience (2 years) and the safe flag."""
    if kind == "M":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 0.0})
    if kind == "C":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 2.0}, requires_relevance=True)
    if kind == "N":
        return component("EXPERIENCE_MIN_YEARS", params={"years": 5.0}, requires_relevance=True)
    if kind == "U":
        return component("UNMODELLED", params={}, safe=False, unknown_reason="REVIEW_FLAG")
    raise AssertionError(kind)


def mkrow(s_no: int, first: str, second: str = "M", **kw) -> dict:
    return row(s_no, raw_text=f"cell one of {s_no} || cell two of {s_no}", components=[comp(first), comp(second)],
               engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE", overlay_ids=[], **kw)


def held_qual(n: int, claims=()) -> dict:
    code = f"TEST/Q900{n}"
    return curated(id=f"qual:{code}", code=code, slug=f"TEST.Q900{n}", titles={"qf": f"Held Qualification {n}"},
                   nsqf_level=official(2.5, 10 + n, engine_use="SAFE_HARD_RULE"), nos_memberships=[], modules=[],
                   eligibility=None,
                   progression_claims=[{"id": f"claim:{code}/P{i}", "qualification_id": f"qual:{code}", "text_verbatim": t,
                                        "direction_label": "Vertical", "evidence_id": ev(30 + i)}
                                       for i, t in enumerate(claims, start=1)])


def evidence(n: int, *, page: str | None = "3-4", location: str | None = None) -> dict:
    """A synthetic OFFICIAL evidence record with id ``ev(n)``. The model requires a page or a location."""
    return {"id": ev(n), "evidence_class": "OFFICIAL", "source_id": "src:A5", "source_sha256": "0" * 64, "page": page,
            "location": location, "method": "pdfplumber_table", "value_status": "TRANSCRIBED"}


def conflict(n: int = 1, *, lead: bool = False) -> dict:
    values = [{"value": 420.0, "evidence_id": ev(7)}] + ([] if lead else [{"value": 400.0, "evidence_id": ev(8)}])
    return {"id": f"conflict:OV-{n:03d}", "subject": {"entity_id": f"qual:{CODE}", "field": "hours.total"}, "values": values,
            "status": "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE" if lead else "UNRESOLVED_SOURCE_CONFLICT",
            "overlay_ids": [f"OV-{n:03d}"], "engine_effect": "UNKNOWN"}


def make(rows=None, *holdings: dict, evidence=(), conflicts=(), **target_kw) -> tuple[Registry, Qualification]:
    spec = {"age_rule": age_rule(), "rows": rows if rows is not None else [mkrow(1, "M")]}
    target = curated(eligibility=spec, nos_memberships=[], modules=[], **target_kw)
    reg = Registry.from_records(qualifications=[Qualification.model_validate(d) for d in (target, *holdings)],
                                evidence=[Evidence.model_validate(d) for d in evidence],
                                conflicts=[Conflict.model_validate(d) for d in conflicts])
    return reg, reg.qualification_by_code(CODE)


def profile(**kw) -> ProfileState:
    kw.setdefault("age_years", 30)
    kw.setdefault("declarations", (TargetDeclaration(target_code=CODE, relevant_experience_years=2),))
    return ProfileState(**kw)


def result_for(rows, state=None, match=None, *holdings, **target_kw) -> tuple[EligibilityResult, Registry]:
    reg, q = make(rows, *holdings, **target_kw)
    return evaluate(q.eligibility, state or profile(), EngineConfig(nsqf_level_match=match), reg), reg


def by_kind(items, kind):
    return [i for i in items if i.kind == kind]


def reachable_ids(res: EligibilityResult, reg: Registry) -> set[str]:
    ids = {e for c in (res.age, *(c for r in res.rows for c in r.components)) for e in c.evidence_ids}
    ids |= {e for s in res.supporting_evidence for e in s.evidence_ids}
    h = reg.qualification_by_code(res.target.code).hours
    ids |= {v.evidence_id for v in (h.theory, h.practical, h.ojt_mandatory, h.ojt_recommended, h.total) if v and v.evidence_id}
    return ids


CASES = {"MET": ([mkrow(1, "M")], M), "CONDITIONAL": ([mkrow(1, "C")], C), "UNKNOWN": ([mkrow(1, "U")], U),
         "NOT_MET": ([mkrow(1, "N")], N)}


@pytest.fixture(params=sorted(CASES))
def case(request):
    rows, expected = CASES[request.param]
    res, reg = result_for(rows)
    assert res.verdict is expected  # the fixture really produces the verdict it is named for
    return res, reg


# ---- every supported verdict ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "prefix"), [("MET", "Met:"), ("CONDITIONAL", "Conditional:"), ("UNKNOWN", "Unknown:"),
                                              ("NOT_MET", "Not met:")])
def test_the_summary_states_exactly_the_engine_verdict(name, prefix):
    rows, expected = CASES[name]
    res, reg = result_for(rows)
    summary = for_eligibility(res, reg)[0]
    assert summary.kind == "VERDICT_SUMMARY" and summary.text.startswith(prefix)
    others = {"Met:", "Conditional:", "Unknown:", "Not met:"} - {prefix}
    assert not any(o in summary.text for o in others)


def test_unknown_and_conditional_are_never_presented_as_a_yes_or_a_no():
    unknown = for_eligibility(*result_for([mkrow(1, "U")]))[0].text
    conditional = for_eligibility(*result_for([mkrow(1, "C")]))[0].text
    assert "not a negative result" in unknown and "met." not in unknown.split("Unknown:")[1].split("because")[0]
    assert "only if" in conditional and "cannot verify" in conditional


def test_the_item_order_is_fixed_and_the_caveat_is_last_for_every_verdict(case):
    items = for_eligibility(*case)
    kinds = [i.kind for i in items]
    assert kinds[0] == "VERDICT_SUMMARY" and kinds[1] == "AGE_REASONING" and kinds[-1] == "CAVEAT"
    assert kinds.count("CAVEAT") == 1 and kinds.count("VERDICT_SUMMARY") == 1
    assert items[-1].text == CAVEAT_TEXT
    order = ["VERDICT_SUMMARY", "AGE_REASONING", "ROW_REASONING", "CONDITION", "WHAT_WOULD_RESOLVE", "HOURS", "PROGRESSION_CLAIM",
             "CAVEAT"]
    assert [order.index(k) for k in kinds] == sorted(order.index(k) for k in kinds)


def test_every_row_gets_a_reasoning_item_in_the_engines_order_even_when_it_is_not_the_deciding_row():
    res, reg = result_for([mkrow(1, "N"), mkrow(2, "C"), mkrow(3, "U")])
    rows = by_kind(for_eligibility(res, reg), "ROW_REASONING")
    assert [r.text.split(" ")[2] for r in rows] == ["1", "2", "3"]  # "Entry row <s_no> (…"
    assert "Deciding entry row: 2." in for_eligibility(res, reg)[0].text
    assert "is NOT_MET" in rows[0].text and "is CONDITIONAL" in rows[1].text and "is UNKNOWN" in rows[2].text


def test_a_not_met_target_states_which_part_failed_and_does_not_suggest_a_workaround():
    age_fail, reg = result_for([mkrow(1, "M")], profile(age_years=17))
    assert age_fail.verdict is N
    text = for_eligibility(age_fail, reg)[0].text
    assert "age requirement is not met" in text and "no entry row" not in text
    rows_fail, reg = result_for([mkrow(1, "N"), mkrow(2, "N")])
    assert "no entry row is met" in for_eligibility(rows_fail, reg)[0].text
    assert by_kind(for_eligibility(rows_fail, reg), "WHAT_WOULD_RESOLVE") == []  # nothing advised for a definite failure


def test_the_age_alone_can_limit_the_result_and_the_summary_says_so():
    res, reg = result_for([mkrow(1, "C")], profile(age_years=None))
    assert res.verdict is U and res.decisive_rule_ids == ()
    text = for_eligibility(res, reg)[0].text
    assert "The age requirement limits this result; no entry row attains it." in text


# ---- uncertainty, missing evidence, conditions ------------------------------------------------------------------------


def test_each_unknown_reason_gets_a_resolution_item_that_never_promises_a_met_result():
    res, reg = result_for([mkrow(1, "U"), mkrow(2, "U")])
    items = by_kind(for_eligibility(res, reg), "WHAT_WOULD_RESOLVE")
    assert len(items) == len(res.unknown_reasons) == 2
    for item, reason in zip(items, res.unknown_reasons, strict=True):
        assert item.text.startswith(reason.text)
        assert find_forbidden(item.text) == [] and "will be met" not in item.text
    assert "stays unevaluated" in items[0].text  # REVIEW_FLAG: its own wording, not a generic review sentence


def one_reason_text(code: UnknownReasonCode, who: str = "SOURCE_REVIEW") -> str:
    """The WHAT_WOULD_RESOLVE text for a single synthetic reason with the given code (everything else untouched)."""
    res, reg = result_for([mkrow(1, "U")])
    reason = res.unknown_reasons[0].model_copy(update={"code": code, "resolvable_by": who, "text": f"Cause text for {code.value}."})
    return by_kind(for_eligibility(res.model_copy(update={"unknown_reasons": (reason,)}), reg), "WHAT_WOULD_RESOLVE")[0].text


def test_every_cause_code_has_its_own_documented_guidance():
    assert set(T._GUIDANCE) == set(UnknownReasonCode)  # a new code must be given guidance (or be added here deliberately)
    assert len(set(T._GUIDANCE.values())) >= 8  # not one generic sentence reused for everything


@pytest.mark.parametrize("code", sorted(UnknownReasonCode, key=lambda c: c.value))
def test_guidance_is_cause_specific_cautious_and_never_promises_a_result(code):
    text = one_reason_text(code)
    assert text.startswith(f"Cause text for {code.value}.") and T._GUIDANCE[code] in text
    assert "Engine classification of who can resolve this: SOURCE_REVIEW." in text  # the engine's own value, restated
    assert find_forbidden(text) == []
    assert not any(p in text.lower() for p in ("will be met", "will become", "will resolve", "will change", "is approved", "approve it"))


def test_an_unapproved_overlay_is_not_told_to_get_another_source_review():
    text = one_reason_text(UnknownReasonCode.OVERLAY_NOT_APPROVED)
    assert "overlay approvals" in text and "neither makes nor assumes that approval" in text
    assert "review of the source" not in text and "source review" not in text.lower()
    assert "no profile or configuration input changes the outcome" in text.lower()  # the user cannot fix it from the profile


@pytest.mark.parametrize("code", [UnknownReasonCode.INPUT_NOT_DECLARED, UnknownReasonCode.RELEVANCE_NOT_DECLARED,
                                  UnknownReasonCode.CONFIG_UNSET])
def test_actionable_causes_say_the_result_is_evaluated_again_and_may_not_improve(code):
    assert "evaluated again and could still be not met, conditional or unknown" in one_reason_text(code, "PROFILE")


@pytest.mark.parametrize("code", [UnknownReasonCode.EQUIVALENCE_UNDEFINED, UnknownReasonCode.CREDENTIAL_ORDER_UNDEFINED,
                                  UnknownReasonCode.ENROLMENT_NOT_MODELLED, UnknownReasonCode.ENGINE_USE_UNDECIDED])
def test_causes_no_input_can_fix_say_so(code):
    assert "no profile or configuration input" in one_reason_text(code, "NOT_RESOLVABLE_FROM_CURRENT_SOURCES").lower()


def test_a_cause_without_documented_guidance_gets_a_cautious_limited_sentence_not_a_guess(monkeypatch):
    monkeypatch.setattr(T, "_GUIDANCE", {k: v for k, v in T._GUIDANCE.items() if k is not UnknownReasonCode.REVIEW_FLAG})
    text = one_reason_text(UnknownReasonCode.REVIEW_FLAG)
    assert "No resolution is documented for this cause." in text and "stays unevaluated" not in text


def test_conditions_are_the_engines_own_texts_with_the_engines_own_evidence_class():
    res, reg = result_for([mkrow(1, "C")])
    assert res.conditions
    items = by_kind(for_eligibility(res, reg), "CONDITION")
    assert [i.text for i in items] == [c.text for c in res.conditions]
    assert [i.evidence_class for i in items] == [c.evidence_class for c in res.conditions]
    assert all(QualityFlagCode.DEPENDS_ON_DECLARATION in i.flags for i in items)
    assert all(i.evidence_ids for i in items)  # traceable to the components they arose from
    resolve = by_kind(for_eligibility(res, reg), "WHAT_WOULD_RESOLVE")
    assert len(resolve) == 1 and "stays conditional" in resolve[0].text


def test_a_condition_on_a_non_conditional_result_is_labelled_as_not_making_it_conditional():
    res, reg = result_for([mkrow(1, "C", "U")])  # row = and_(CONDITIONAL, UNKNOWN) = UNKNOWN, but a condition is recorded
    assert res.verdict is U and res.conditions
    items = by_kind(for_eligibility(res, reg), "CONDITION")
    assert items and all("does not make it conditional" in i.text and "UNKNOWN" in i.text for i in items)


def test_row_flags_are_reported_with_their_codes_and_references_and_reach_the_item_flags():
    flag = {"code": "OVERLAY_PENDING_APPROVAL", "severity": "INFO", "message": "Proposed value (OV-002) is not applied.",
            "refs": ["OV-002"]}
    res, reg = result_for([mkrow(1, "U", flags=[flag])])
    item = by_kind(for_eligibility(res, reg), "ROW_REASONING")[0]
    assert "Note (OVERLAY_PENDING_APPROVAL): Proposed value (OV-002) is not applied. [OV-002]" in item.text
    assert QualityFlagCode.OVERLAY_PENDING_APPROVAL in item.flags
    assert QualityFlagCode.OVERLAY_PENDING_APPROVAL in for_eligibility(res, reg)[0].flags  # the engine's own target flags


def test_an_empty_source_cell_is_described_as_empty_not_as_an_empty_quotation():
    res, reg = result_for([mkrow(1, "M")])
    comp0 = res.rows[0].components[0].model_copy(update={"requirement_text": ""})
    row0 = res.rows[0].model_copy(update={"components": (comp0, *res.rows[0].components[1:])})
    text = by_kind(for_eligibility(res.model_copy(update={"rows": (row0,)}), reg), "ROW_REASONING")[0].text
    assert "The empty source cell is MET" in text and '""' not in text


def test_hypothetical_inputs_are_labelled_as_assumed_not_held():
    res, reg = result_for([mkrow(1, "M")])
    from skillgraph.eligibility.components import InputUsed

    hyp = InputUsed(field="qual:TEST/Q9002.nsqf_level", value=2.5, evidence_class=EvidenceClass.HYPOTHETICAL)
    c0 = res.age.model_copy(update={"inputs_used": (hyp,)})
    text = by_kind(for_eligibility(res.model_copy(update={"age": c0}), reg), "AGE_REASONING")[0].text
    assert "assumed completed on a path, not held" in text


# ---- hours and progression claims -------------------------------------------------------------------------------------


def test_the_hours_item_states_official_hours_with_their_stored_ids_and_claims_no_reduction():
    res, reg = result_for([mkrow(1, "M")], hours=hours(total=420.0, n=7))
    item = by_kind(for_eligibility(res, reg), "HOURS")[0]
    assert item.evidence_class is EvidenceClass.OFFICIAL and item.evidence_ids == (ev(7),)
    assert "420 in total" in item.text and "theory 20" in item.text and "practical 80" in item.text
    assert "records no source that defines a reduced route" in item.text
    assert QualityFlagCode.NO_OFFICIAL_REDUCTION_SOURCE in item.flags
    assert "credit" not in item.text.lower()


# ---- the official source page of the hours --------------------------------------------------------------------------------


def hours_text(**kw) -> str:
    res, reg = result_for([mkrow(1, "M")], **kw)
    return by_kind(for_eligibility(res, reg), "HOURS")[0].text


def test_the_hours_item_reports_the_page_recorded_on_the_evidence_record():
    text = hours_text(hours=hours(total=420.0, n=7), evidence=[evidence(7, page="3-4")])
    assert "Source page: 3-4." in text and "not recorded" not in text


def test_the_page_comes_from_the_record_not_from_a_fixed_value():
    assert "Source page: 12." in hours_text(hours=hours(total=420.0, n=7), evidence=[evidence(7, page="12")])
    assert "3-4" not in hours_text(hours=hours(total=420.0, n=7), evidence=[evidence(7, page="12")])


def test_several_distinct_pages_are_all_listed_in_a_fixed_order():
    h = hours(total=420.0, n=7)
    h["practical"] = {**h["practical"], "evidence_id": ev(8)}
    text = hours_text(hours=h, evidence=[evidence(7, page="5"), evidence(8, page="3-4")])
    assert "Source pages: 3-4, 5." in text


def test_a_record_with_only_a_location_gives_no_page_and_none_is_invented():
    text = hours_text(hours=hours(total=420.0, n=7), evidence=[evidence(7, page=None, location="QF item 13")])
    assert "The source page is not recorded in the available metadata." in text and "Source page" not in text


def test_a_registry_without_the_evidence_record_gives_no_page_and_does_not_fail():
    text = hours_text(hours=hours(total=420.0, n=7))  # no evidence records at all
    assert "The source page is not recorded in the available metadata." in text and "Source page" not in text


def test_a_page_missing_for_some_values_is_stated_as_partial():
    h = hours(total=420.0, n=7)
    h["practical"] = {**h["practical"], "evidence_id": ev(8)}
    text = hours_text(hours=h, evidence=[evidence(7, page="3-4"), evidence(8, page=None, location="QF item 13")])
    assert "Source page: 3-4." in text and "The page is not recorded for every one of these values." in text


# ---- conflicting hours (synthetic: the real pilot hours carry no conflict) ---------------------------------------------------


def conflicted_hours(conflict_id="conflict:OV-001") -> dict:
    h = hours(total=420.0, n=7)
    h["total"] = {**h["total"], "conflict_id": conflict_id, "engine_use": "UNKNOWN"}
    return h


def conflict_item(conflicts=(), conflict_id="conflict:OV-001"):
    res, reg = result_for([mkrow(1, "M")], hours=conflicted_hours(conflict_id), evidence=[evidence(7), evidence(8)],
                          conflicts=list(conflicts))
    return by_kind(for_eligibility(res, reg), "HOURS")[0]


def test_conflicting_hours_are_flagged_and_the_figure_is_not_presented_as_settled():
    item = conflict_item([conflict()])
    assert QualityFlagCode.SOURCE_CONFLICT in item.flags
    assert "the sources disagree and the conflict is unresolved (conflict:OV-001)" in item.text
    assert "so the stated figure is not settled" in item.text
    assert "420 in total" in item.text  # the stored value is still reported as what it is, never silently replaced
    assert "400" not in item.text  # the other recorded value is not promoted to an answer either


def test_a_lead_whose_other_source_is_unavailable_is_worded_as_a_lead_not_a_disagreement():
    item = conflict_item([conflict(lead=True)])
    assert "a lead whose other source is unavailable remains unresolved (conflict:OV-001)" in item.text
    assert "the sources disagree" not in item.text


def test_a_conflict_id_with_no_conflict_record_is_stated_cautiously_not_dropped():
    item = conflict_item([])
    assert QualityFlagCode.SOURCE_CONFLICT in item.flags
    assert "a source conflict is recorded (conflict:OV-001) but its record is not available" in item.text


def test_the_hours_are_omitted_when_the_registry_gives_nothing_citable():
    # the model already refuses an OFFICIAL value without an evidence ID; a printed-nothing (null) total is the reachable case
    h = hours(total=420.0)
    h["total"] = {**h["total"], "value": None}
    res, reg = result_for([mkrow(1, "M")], hours=h)
    assert reg.qualification_by_code(CODE).hours.total.value is None
    assert by_kind(for_eligibility(res, reg), "HOURS") == []


def test_uncertain_hours_are_reported_as_uncertain():
    h = hours(total=420.0)
    h["total"] = {**h["total"], "value_status": "PARSED_UNCERTAIN"}
    res, reg = result_for([mkrow(1, "M")], hours=h)
    item = by_kind(for_eligibility(res, reg), "HOURS")[0]
    assert QualityFlagCode.UNCERTAIN_EXTRACTION in item.flags and "extracted with uncertainty" in item.text


def test_progression_claims_are_restated_verbatim_with_their_own_evidence_and_never_change_the_result():
    reg_args = ([mkrow(1, "C")], held_qual(2, claims=["Target (Vertical)"]))
    state = profile(held_qualification_codes=(HELD1,), external_qualifications=(),
                    declarations=(TargetDeclaration(target_code=CODE, relevant_experience_years=2,
                                                    relevant_prior_qualifications=(HELD1,)),))
    res, reg = result_for(reg_args[0], state, None, reg_args[1])
    assert res.supporting_evidence
    items = by_kind(for_eligibility(res, reg), "PROGRESSION_CLAIM")
    assert [(i.text, i.evidence_ids, i.evidence_class) for i in items] == [
        (s.text, s.evidence_ids, s.evidence_class) for s in res.supporting_evidence]
    assert "does not change the verdict" in items[0].text


def test_no_claim_means_no_progression_item_and_no_claim_of_absence():
    res, reg = result_for([mkrow(1, "M")])
    assert by_kind(for_eligibility(res, reg), "PROGRESSION_CLAIM") == []


# ---- evidence rules ---------------------------------------------------------------------------------------------------


def test_every_item_has_an_evidence_class_and_every_factual_item_cites_a_stored_id(case):
    res, reg = case
    items = for_eligibility(res, reg)
    assert items and all(isinstance(i.evidence_class, EvidenceClass) for i in items)
    for i in items:
        if i.kind != "CAVEAT" and i.evidence_class in (EvidenceClass.OFFICIAL, EvidenceClass.RULE_DERIVED):
            assert i.evidence_ids, f"{i.kind} is a factual item without an evidence ID"
    for i in items:
        assert i.kind in {"VERDICT_SUMMARY", "AGE_REASONING", "ROW_REASONING", "CONDITION", "WHAT_WOULD_RESOLVE", "HOURS",
                          "PROGRESSION_CLAIM", "CAVEAT"}


def test_no_evidence_id_is_invented(case):
    res, reg = case
    allowed = reachable_ids(res, reg)
    for i in for_eligibility(res, reg):
        assert set(i.evidence_ids) <= allowed, (i.kind, set(i.evidence_ids) - allowed)
        assert len(set(i.evidence_ids)) == len(i.evidence_ids)


def test_the_caveat_is_not_a_data_claim_and_carries_no_evidence_id():
    caveat = for_eligibility(*result_for([mkrow(1, "M")]))[-1]
    assert caveat.kind == "CAVEAT" and caveat.evidence_ids == () and caveat.flags == ()
    assert "not a prediction of admission, employability, placement or earnings" in caveat.text
    assert "does not establish enrolment, a job transition or any reduction in the training required" in caveat.text


def test_a_factual_item_that_cannot_cite_a_stored_id_is_refused_not_papered_over():
    res, reg = result_for([mkrow(1, "M")])
    bare_age = res.age.model_copy(update={"evidence_ids": ()})
    with pytest.raises(ExplanationError, match="no stored evidence ID"):
        for_eligibility(res.model_copy(update={"age": bare_age}), reg)
    bare_row = res.rows[0].model_copy(update={"components": tuple(c.model_copy(update={"evidence_ids": ()}) for c in res.rows[0].components)})
    with pytest.raises(ExplanationError, match="row 1"):
        for_eligibility(res.model_copy(update={"rows": (bare_row,)}), reg)


def test_an_unknown_reason_that_points_at_no_component_is_refused():
    res, reg = result_for([mkrow(1, "U")])
    stray = res.unknown_reasons[0].model_copy(update={"ref": "rule:TEST/Q9001/E99#c1"})
    with pytest.raises(ExplanationError, match="not a component of the result"):
        for_eligibility(res.model_copy(update={"unknown_reasons": (stray,)}), reg)


def test_a_supporting_item_without_an_evidence_id_is_refused():
    res, reg = result_for([mkrow(1, "M")])
    bare = ExplanationItem(kind="PROGRESSION_CLAIM", text="x", evidence_class=EvidenceClass.OFFICIAL)
    with pytest.raises(ExplanationError, match="supporting-evidence item"):
        for_eligibility(res.model_copy(update={"supporting_evidence": (bare,)}), reg)


def test_a_target_missing_from_the_registry_raises_the_registry_error():
    res, _ = result_for([mkrow(1, "M")])
    other = Registry.from_records(qualifications=[Qualification.model_validate(held_qual(2))])
    with pytest.raises(UnknownEntityError):
        for_eligibility(res, other)


# ---- which components a condition may cite ---------------------------------------------------------------------------------


def idrow(s_no: int, first: str, ids: tuple[int, int]) -> dict:
    """``mkrow`` with its two components given evidence ids ``ev(ids[0])`` and ``ev(ids[1])`` so that citations are observable."""
    r = mkrow(s_no, first)
    r["components"][0]["evidence_id"], r["components"][1]["evidence_id"] = ev(ids[0]), ev(ids[1])
    return r


def prior_idrow(s_no: int, ids: tuple[int, int], level: float = 2.5) -> dict:
    return row(s_no, raw_text=f"prior level {level} || {s_no}", engine_use="CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG",
               overlay_ids=[], components=[
                   component("PRIOR_NSQF_LEVEL", params={"level": level}, requires_relevance=True, evidence_id=ev(ids[0])),
                   component("EXPERIENCE_MIN_YEARS", params={"years": 0.0}, evidence_id=ev(ids[1]))])


def level_state() -> ProfileState:
    d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=(HELD1,))
    return profile(held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(d,))


def condition_ids(items) -> dict[str, tuple[str, ...]]:
    return {i.text: i.evidence_ids for i in by_kind(items, "CONDITION")}


def test_a_condition_cites_only_the_components_that_carry_it_not_every_deciding_component():
    # row 1: experience is CONDITIONAL (ev 21), second component MET (ev 22); row 2: level is CONDITIONAL (ev 31: a declaration
    # and a CONFIG condition), second component MET (ev 32). Both rows decide, so all four components are deciding components.
    res, reg = result_for([idrow(1, "C", (21, 22)), prior_idrow(2, (31, 32))], level_state(), "exact", held_qual(2))
    assert res.verdict is C and len(res.decisive_rule_ids) == 2 and len(res.conditions) == 3
    got = condition_ids(for_eligibility(res, reg))
    experience = next(c.text for c in res.conditions if c.key.endswith("relevant_experience_years"))
    prior = next(c.text for c in res.conditions if c.key.endswith("relevant_prior_qualifications"))
    config = next(c.text for c in res.conditions if c.key == "config.nsqf_level_match")
    assert got[experience] == (ev(21),)  # not the level component (31), and never a MET component (22, 32)
    assert got[prior] == (ev(31),)
    assert got[config] == (ev(31),)  # row 1 used no config, so its component is not cited
    assert not ({ev(22), ev(32)} & {e for ids in got.values() for e in ids})  # a MET component carries no condition


def test_a_condition_carried_by_several_components_cites_each_of_them_in_printed_order():
    res, reg = result_for([idrow(1, "C", (21, 22)), idrow(2, "C", (41, 42))])
    (only,) = res.conditions
    assert condition_ids(for_eligibility(res, reg)) == {only.text: (ev(21), ev(41))}


def test_the_old_behaviour_would_have_failed_the_regression():
    # the broad citation (every deciding component) differs from the narrow one on this result, so the test above can fail
    res, reg = result_for([idrow(1, "C", (21, 22)), prior_idrow(2, (31, 32))], level_state(), "exact", held_qual(2))
    broad = tuple(dict.fromkeys(e for r in res.rows for c in r.components for e in c.evidence_ids))
    assert len(broad) == 4 and all(len(ids) < 4 for ids in condition_ids(for_eligibility(res, reg)).values())


def test_a_condition_that_no_deciding_component_carries_is_refused_not_linked_by_guesswork():
    res, reg = result_for([mkrow(1, "C")])
    stray = res.conditions[0].model_copy(update={"text": "Holds only if something that no component states.", "key": "x.y"})
    with pytest.raises(ExplanationError, match="carried by no deciding component"):
        for_eligibility(res.model_copy(update={"conditions": (stray,)}), reg)


def test_a_not_met_component_that_used_the_same_config_key_does_not_carry_the_condition():
    # age 17: the target is NOT_MET, so every row is deciding. Row 1's level component is CONDITIONAL (config + declaration, ev 31);
    # row 2 asks for level 4.0 against the held 2.5, so its level component is NOT_MET and also lists config.nsqf_level_match in
    # inputs_used (ev 61) without carrying any condition. Matching by key alone would credit it.
    d = TargetDeclaration(target_code=CODE, relevant_experience_years=2, relevant_prior_qualifications=(HELD1,))
    state = profile(age_years=17, held_qualification_codes=(HELD1,), external_qualifications=(), declarations=(d,))
    res, reg = result_for([prior_idrow(1, (31, 32)), prior_idrow(2, (61, 62), level=4.0)], state, "exact", held_qual(2))
    assert res.verdict is N and len(res.decisive_rule_ids) == 2
    not_met = res.rows[1].components[0]
    assert not_met.verdict is N and any(u.field == "config.nsqf_level_match" for u in not_met.inputs_used)
    got = condition_ids(for_eligibility(res, reg))
    config = next(c.text for c in res.conditions if c.key == "config.nsqf_level_match")
    assert got[f"Recorded assumption on the deciding rows (the overall result is NOT_MET, so this does not make it conditional): {config}"] == (ev(31),)


def test_a_condition_on_a_non_deciding_row_is_never_cited_by_a_deciding_one():
    res, reg = result_for([idrow(1, "C", (21, 22)), idrow(2, "N", (51, 52))])  # row 2 NOT_MET: not deciding
    assert res.decisive_rule_ids == (f"rule:{CODE}/E1",)
    assert all(ev(51) not in ids and ev(52) not in ids for ids in condition_ids(for_eligibility(res, reg)).values())


# ---- cited evidence IDs against the registry's evidence lookup ---------------------------------------------------------------


def with_evidence(res: EligibilityResult, reg: Registry, *, drop: set[str] = frozenset(), extra=()) -> Registry:
    """The same qualifications plus a synthetic OFFICIAL evidence record for every ID reachable from the result."""
    ids = sorted(reachable_ids(res, reg) - drop)
    return Registry.from_records(qualifications=list(reg.qualifications()),
                                 evidence=[Evidence.model_validate(evidence(int(i[3:], 16))) for i in ids] + list(extra))


def citation_problems(items, reg: Registry) -> list[tuple[str, str, str]]:
    """Every cited ID that does not resolve through ``evidence_by_id`` or resolves to a record that is not OFFICIAL. DECLARED,
    CONFIG and HYPOTHETICAL facts are request-scoped and have no stored record, so no item may cite one."""
    bad = []
    for i in items:
        for e in i.evidence_ids:
            try:
                rec = reg.evidence_by_id(e)
            except UnknownEntityError:
                bad.append((i.kind, e, "unresolved"))
                continue
            if rec.evidence_class is not EvidenceClass.OFFICIAL:
                bad.append((i.kind, e, f"resolves to {rec.evidence_class.value}"))
    return bad


def test_every_cited_id_resolves_through_the_registry_to_an_official_record(case):
    res, reg = case
    full = with_evidence(res, reg)
    items = for_eligibility(res, full)
    assert any(i.evidence_ids for i in items)
    assert citation_problems(items, full) == []
    # an item's class is about the kind of statement; the records behind it are always stored OFFICIAL cells or values
    assert {i.evidence_class for i in items if i.evidence_ids} <= {EvidenceClass.OFFICIAL, EvidenceClass.RULE_DERIVED,
                                                                   EvidenceClass.DECLARED, EvidenceClass.CONFIG}


def test_an_unknown_id_is_reported_by_the_resolver_with_a_clear_reason():
    res, reg = result_for([mkrow(1, "M")])
    missing = ev(2)  # every synthetic component cites ev(2)
    partial = with_evidence(res, reg, drop={missing})
    problems = citation_problems(for_eligibility(res, partial), partial)
    assert problems and all(p[1] == missing and p[2] == "unresolved" for p in problems)
    fabricated = [ExplanationItem(kind="X", text="y", evidence_class=EvidenceClass.OFFICIAL, evidence_ids=("ev:ffffffffffffffff",))]
    assert citation_problems(fabricated, partial) == [("X", "ev:ffffffffffffffff", "unresolved")]


def test_a_cited_id_that_resolves_to_a_request_scoped_record_is_rejected_by_the_resolver():
    res, reg = result_for([mkrow(1, "M")])
    declared = {"id": ev(2), "evidence_class": "DECLARED", "declared_field": "profile.age_years"}
    full = Registry.from_records(qualifications=list(reg.qualifications()),
                                 evidence=[Evidence.model_validate(declared)] + [Evidence.model_validate(evidence(int(i[3:], 16)))
                                                                                for i in sorted(reachable_ids(res, reg) - {ev(2)})])
    assert {p[2] for p in citation_problems(for_eligibility(res, full), full)} == {"resolves to DECLARED"}


def test_a_well_formed_non_empty_id_is_a_pointer_not_proof_so_the_function_does_not_vouch_for_it():
    # for_eligibility copies IDs from the result; it does not look them up, and the stored data could not confirm content anyway.
    res, reg = result_for([mkrow(1, "M")])
    bare = for_eligibility(res, reg)  # a registry that holds no evidence records at all
    assert bare and citation_problems(bare, reg)  # still explained; every cited ID is unresolvable against this registry
    full = with_evidence(res, reg)
    assert [i.evidence_ids for i in for_eligibility(res, full)] == [i.evidence_ids for i in bare]  # identical IDs either way


def test_the_evidence_schema_stores_no_value_so_content_level_support_cannot_be_tested():
    assert not ({"value", "text", "content", "quote", "excerpt"} & set(Evidence.model_fields))
    assert {"source_id", "page", "location", "method", "value_status"} <= set(Evidence.model_fields)  # what CAN be checked


# ---- partial and empty data -------------------------------------------------------------------------------------------


def test_an_empty_profile_gives_an_unknown_explanation_that_names_every_gap():
    res, reg = result_for([mkrow(1, "C")], ProfileState())
    assert res.verdict is U
    items = for_eligibility(res, reg)
    assert items[0].text.startswith("Unknown:") and items[-1].kind == "CAVEAT"
    assert len(by_kind(items, "WHAT_WOULD_RESOLVE")) == len(res.unknown_reasons) >= 1
    assert "Not declared" in by_kind(items, "WHAT_WOULD_RESOLVE")[0].text


def test_a_result_without_rows_is_refused_not_explained_without_a_route():
    # EligibilityResult accepts rows=() (its validator checks only component invariants), but evaluate() refuses a specification
    # without rows (D-1), so the engine cannot produce this shape; no verdict can be traced to a route, so nothing is explained.
    res, reg = result_for([mkrow(1, "M")])
    with pytest.raises(ExplanationError, match="without entry rows"):
        for_eligibility(res.model_copy(update={"rows": (), "decisive_rule_ids": ()}), reg)


def test_a_conditional_result_with_no_deciding_row_is_valid_for_the_model_but_refused():
    # The model validator does not forbid it; the engine cannot produce it (a condition always arises in a deciding row,
    # and evaluate() derives decisive_rule_ids from the rows). It is refused with a clear message, and no validation is relaxed.
    res, reg = result_for([mkrow(1, "C")])
    odd = res.model_copy(update={"decisive_rule_ids": ()})
    assert odd.verdict is C  # the result model itself accepts it
    EligibilityResult.model_validate(odd.model_dump())
    with pytest.raises(ExplanationError, match="no deciding row"):
        for_eligibility(odd, reg)


def swap_row_verdict(res: EligibilityResult, s_no: int, verdict: Verdict) -> EligibilityResult:
    rows = tuple(r.model_copy(update={"verdict": verdict}) if r.s_no == s_no else r for r in res.rows)
    return res.model_copy(update={"rows": rows})


@pytest.mark.parametrize(("what", "message"), [
    ("row verdict above its components", "is not the lowest verdict of its components"),
    ("target verdict not the fold", "is not the fold of its age and rows"),
    ("stray decisive id", "is not an entry row of the result"),
    ("decisive set wrong", "are not the rows that attain the result verdict"),
    ("duplicate row", "the same entry row twice"),
])
def test_conflicting_component_and_row_outcomes_are_refused_never_resolved_by_the_explanation(what, message):
    res, reg = result_for([mkrow(1, "N"), mkrow(2, "C")])  # row 1 NOT_MET, row 2 CONDITIONAL, target CONDITIONAL, decisive row 2
    assert res.verdict is C and res.decisive_rule_ids == (f"rule:{CODE}/E2",)
    bad = {
        "row verdict above its components": swap_row_verdict(res, 1, M),
        "target verdict not the fold": res.model_copy(update={"verdict": M}),
        "stray decisive id": res.model_copy(update={"decisive_rule_ids": (f"rule:{CODE}/E9",)}),
        "decisive set wrong": res.model_copy(update={"decisive_rule_ids": (f"rule:{CODE}/E1", f"rule:{CODE}/E2")}),
        "duplicate row": res.model_copy(update={"rows": (res.rows[0], res.rows[0], res.rows[1])}),
    }[what]
    with pytest.raises(ExplanationError, match=message):
        for_eligibility(bad, reg)


def test_a_consistent_result_is_never_refused_for_every_supported_verdict(case):
    res, reg = case
    assert for_eligibility(res, reg)  # no ExplanationError for anything the engine produces


# ---- determinism and non-interference ---------------------------------------------------------------------------------


def test_repeated_and_rebuilt_inputs_give_identical_output(case):
    res, reg = case
    first = [i.model_dump(mode="json") for i in for_eligibility(res, reg)]
    assert first == [i.model_dump(mode="json") for i in for_eligibility(res, reg)]
    rebuilt = EligibilityResult.model_validate(json.loads(res.model_dump_json()))
    assert first == [i.model_dump(mode="json") for i in for_eligibility(rebuilt, reg)]


def distinct_rows() -> list[dict]:
    """Three rows whose six components each carry their own evidence ID, so that the order of cited IDs is observable."""
    rows = [mkrow(1, "N"), mkrow(2, "C"), mkrow(3, "U")]
    n = 100
    for r in rows:
        for c in r["components"]:
            c["evidence_id"] = ev(n)
            n += 1
    return rows


def test_cited_ids_follow_the_printed_order_of_the_components_without_duplicates():
    res, reg = result_for(distinct_rows())
    first_ids = [e for c in (res.age, *(c for r in res.rows for c in r.components)) for e in c.evidence_ids]
    assert len(set(first_ids)) == 7  # age + 6 components, all distinct
    items = for_eligibility(res, reg)
    decisive = [c for r in res.rows if r.rule_id in res.decisive_rule_ids for c in r.components]
    assert items[0].evidence_ids == tuple(dict.fromkeys(e for c in [res.age, *decisive] for e in c.evidence_ids))
    for item, r in zip(by_kind(items, "ROW_REASONING"), res.rows, strict=True):
        assert item.evidence_ids == tuple(e for c in r.components for e in c.evidence_ids)


def test_the_output_is_the_same_in_other_processes_and_under_any_hash_seed():
    child = f"""
import sys; sys.path[:0] = [{str(SRC)!r}, {str(Path(__file__).parent)!r}]
import json
from test_explain_templates import result_for, distinct_rows, for_eligibility
res, reg = result_for(distinct_rows())
print(json.dumps([i.model_dump(mode="json") for i in for_eligibility(res, reg)], sort_keys=True))
"""
    outs = set()
    for seed in ("0", "1", "4242", "random"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outs.add(subprocess.run([sys.executable, "-B", "-c", child], env=env, capture_output=True, text=True, check=True).stdout)
    assert len(outs) == 1 and json.loads(outs.pop())


def test_explaining_never_modifies_the_result_or_the_registry(case):
    res, reg = case
    before = res.model_dump_json()
    q_before = reg.qualification_by_code(CODE).model_dump_json()
    for_eligibility(res, reg)
    assert res.model_dump_json() == before and reg.qualification_by_code(CODE).model_dump_json() == q_before
    assert res.explanation == ()  # the engine's own field is untouched: the façade (P3.10) decides where this goes


def _names_and_attrs(tree: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


def test_the_templates_import_only_result_types_and_the_lattice_so_they_cannot_evaluate_or_enumerate():
    # an allowlist, not a deny-list: an aliased import of the evaluator (``from … import evaluate as e``) cannot slip through
    tree = ast.parse(TEMPLATES.read_text(encoding="utf-8"))
    allowed = {
        "skillgraph.eligibility.components": {"Condition", "ConditionKind"},
        "skillgraph.eligibility.evaluate": {"ComponentResult", "EligibilityResult", "ExplanationItem", "RowResult"},
        "skillgraph.eligibility.logic": {"and_", "or_"},
        "skillgraph.model.conflict": {"ConflictStatus"},
        "skillgraph.model.eligibility": {"UnknownReasonCode", "Verdict"},
        "skillgraph.model.evidence": {"EvidenceClass", "QualityFlagCode", "ValueStatus"},
        "skillgraph.registry": {"Registry", "UnknownEntityError"},
        "__future__": {"annotations"}, "collections.abc": {"Iterable"},
    }
    got = {n.module: {a.name for a in n.names} for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    got |= {a.name: set() for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert set(got) - {"json"} <= set(allowed) and got.get("json", set()) == set()
    assert all(names <= allowed[mod] for mod, names in got.items() if mod in allowed), got
    assert not ({"evaluate", "evaluate_component", "enumerate_paths", "rank"} & _names_and_attrs(tree))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del))]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
                and getattr(n.func, "id", getattr(n.func, "attr", "")) in {"setattr", "delattr", "__setattr__", "model_copy",
                                                                           "model_construct"}]


def test_the_lattice_is_used_only_to_refuse_an_inconsistent_result_never_to_choose_a_verdict():
    tree = ast.parse(TEMPLATES.read_text(encoding="utf-8"))
    users = {fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef) and {"and_", "or_"} & _names_and_attrs(fn)}
    assert users == {"_check_consistent"}
    src = ast.get_source_segment(TEMPLATES.read_text(encoding="utf-8"),
                                 next(f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == "_check_consistent"))
    assert src.count("raise ExplanationError") >= 6 and "return" not in src.replace("returns", "")  # it can only raise or pass


def test_explaining_works_with_the_evaluator_disabled_so_it_cannot_re_evaluate(case, monkeypatch):
    import skillgraph.eligibility.evaluate as ev_mod

    def boom(*a, **k):
        raise AssertionError("the explanation must not evaluate eligibility")

    res, reg = case
    monkeypatch.setattr(ev_mod, "evaluate", boom)
    assert for_eligibility(res, reg)


def test_an_explanation_attached_to_the_result_leaves_every_other_field_exactly_as_the_engine_returned_it(case):
    res, reg = case
    attached = res.model_copy(update={"explanation": tuple(for_eligibility(res, reg))})
    assert attached.model_dump(exclude={"explanation"}) == res.model_dump(exclude={"explanation"})
    assert attached.verdict is res.verdict and attached.conditions == res.conditions and attached.unknown_reasons == res.unknown_reasons


def test_the_items_fit_the_api_shape_and_round_trip_through_the_result_model(case):
    res, reg = case
    items = for_eligibility(res, reg)
    assert isinstance(items, list) and all(isinstance(i, ExplanationItem) for i in items)
    assert all(set(i.model_dump()) == {"kind", "text", "evidence_class", "evidence_ids", "flags"} for i in items)
    full = EligibilityResult.model_validate({**res.model_dump(), "explanation": [i.model_dump() for i in items]})
    assert tuple(full.explanation) == tuple(items)
    with pytest.raises(ValidationError):
        ExplanationItem(kind="X", text="y")  # an evidence class is required


@pytest.mark.parametrize("bad", [None, "x", 3, {}])
def test_wrong_argument_types_are_refused(bad):
    res, reg = result_for([mkrow(1, "M")])
    with pytest.raises(TypeError, match="result"):
        for_eligibility(bad, reg)
    with pytest.raises(TypeError, match="registry"):
        for_eligibility(res, bad)


# ---- text lint and boundaries -----------------------------------------------------------------------------------------


# The template-source scan and the lint's own tests are in tests/unit/test_explain_lint.py.


def test_no_generated_text_contains_a_forbidden_claim_including_the_engine_supplied_text(case):
    res, reg = case
    for i in for_eligibility(res, reg):
        assert find_forbidden(i.text) == [], (i.kind, i.text)
    engine_texts = [c.text for c in res.conditions] + [r.text for r in res.unknown_reasons]
    assert all(find_forbidden(t) == [] for t in engine_texts)


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            found.add(n.module or "")
    return found


def test_the_explanation_code_is_offline_pure_and_separate_from_the_judge_graph_and_api():
    for f in (SRC / "skillgraph" / "explain").glob("*.py"):
        mods = _imports(f)
        banned = ("skillgraph.judge", "skillgraph.graph", "skillgraph.api", "skillgraph.labour", "skillgraph.settings",
                  "anthropic", "httpx", "requests", "urllib", "socket", "http", "openai", "random", "datetime", "time", "os",
                  "subprocess", "secrets", "uuid")
        assert not [m for m in mods if m.split(".")[0] in {b.split(".")[0] for b in banned if "." not in b}
                    or any(m == b or m.startswith(b + ".") for b in banned if "." in b)], (f.name, mods)
        assert all(m.split(".")[0] in {"skillgraph", "__future__", "json", "collections", "re", "unicodedata"}
                   for m in mods), (f.name, mods)


def test_nothing_in_the_engine_or_the_judge_imports_the_explanation_package():
    for pkg in ("eligibility", "graph", "judge", "model", "registry", "curation"):
        for f in (SRC / "skillgraph" / pkg).rglob("*.py"):
            assert not [m for m in _imports(f) if m == "skillgraph.explain" or m.startswith("skillgraph.explain.")], f
