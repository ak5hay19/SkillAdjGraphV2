import pytest
from model_factory import (
    CODE,
    QID,
    age_rule,
    bridge_membership,
    catalogue_only,
    component,
    curated,
    ev,
    membership,
    module,
    official,
    row,
)
from pydantic import ValidationError

from skillgraph.model.conflict import Conflict, ConflictStatus
from skillgraph.model.eligibility import AgeRule, Component, ComponentType, EligibilityRow, EligibilitySpec
from skillgraph.model.evidence import EngineUse
from skillgraph.model.occupation import NcoLevels, Occupation, TitleVerification
from skillgraph.model.qualification import (
    NosMembership,
    NosUnit,
    ProgressionClaim,
    Qualification,
)
from skillgraph.model.source import SourceDocument

SHA = "b" * 64


def refused(model, data, match=None):
    with pytest.raises(ValidationError, match=match):
        model.model_validate(data)


class TestQualification:
    def test_curated_roundtrips_through_json(self):
        q = Qualification.model_validate(curated())
        assert Qualification.model_validate_json(q.model_dump_json()) == q

    def test_catalogue_only_is_accepted_and_carries_no_eligibility(self):
        q = Qualification.model_validate(catalogue_only())
        assert q.eligibility is None and not q.nos_memberships and q.min_age is None

    def test_catalogue_only_rejects_curated_content(self):
        refused(Qualification, catalogue_only(eligibility=curated()["eligibility"]), "no NOS, module")
        refused(Qualification, catalogue_only(modules=[module()]), "no NOS, module")
        refused(Qualification, catalogue_only(min_age=official(18)), "minimum age")
        refused(Qualification, catalogue_only(titles={"qf": "x"}), "catalogue title")

    def test_curated_requires_full_evidence(self):
        refused(Qualification, curated(titles={"catalogue": "x"}), "QF title")
        refused(Qualification, curated(min_age=None), "min_age and eligibility")
        refused(Qualification, curated(eligibility=None), "min_age and eligibility")
        partial = {"total": official(100.0, engine_use="SAFE_HOURS")}
        refused(Qualification, curated(hours=partial), "all five hours")

    def test_id_slug_and_code_must_agree(self):
        refused(Qualification, curated(slug="TEST/Q9001"), "derived from code")
        refused(Qualification, curated(id="qual:TEST/Q9003"), "derived from code")
        refused(Qualification, curated(code="test/q9001"))

    def test_titles_keep_variants_side_by_side(self):
        q = Qualification.model_validate(curated(titles={"qf": "Inline Checker - Sewing", "qp": "Checker - Inline & Measurement"}))
        assert q.titles.qf != q.titles.qp

    def test_nsqf_level_range_and_step(self):
        for bad in (0.5, 10.5, 2.3):
            refused(Qualification, curated(nsqf_level=official(bad)))
        assert Qualification.model_validate(curated(nsqf_level=official(3.5)))

    def test_rules_modules_and_memberships_must_belong_to_the_qualification(self):
        other_age = {**age_rule(), "id": "rule:TEST/Q9002/AGE"}
        refused(Qualification, curated(eligibility={"age_rule": other_age, "rows": []}), "another qualification|one qualification")
        refused(Qualification, curated(nos_memberships=[membership(qualification_id="qual:TEST/Q9002")]), "another qualification")
        refused(Qualification, curated(nos_memberships=[bridge_membership()], modules=[]), "unknown module")
        refused(Qualification, curated(nos_memberships=[membership(), membership()]), "duplicate S.No")

    def test_ncp_code_format_is_checked(self):
        refused(Qualification, curated(nco_codes=[official("8153")]))


class TestMembershipsAndNos:
    def test_exactly_one_of_nos_or_module(self):
        refused(NosMembership, membership(module_id=f"mod:{CODE}/S1"), "exactly one")
        refused(NosMembership, membership(nos_id=None), "exactly one")

    def test_a_bridge_row_is_a_module(self):
        refused(NosMembership, membership(is_bridge=True), "bridge row is a module")
        assert NosMembership.model_validate(bridge_membership()).module_id.endswith("/S1")

    def test_membership_states_all_hours(self):
        refused(NosMembership, membership(hours={"total": official(1.0, engine_use="SAFE_HOURS")}), "all five")

    def test_membership_version_is_display_only(self):
        refused(NosMembership, membership(version=official("4.0", engine_use="SAFE_HOURS")), "DISPLAY_ONLY")

    def test_nos_unit_has_no_level_and_keeps_titles_per_source(self):
        unit = NosUnit.model_validate({"id": "nos:TEST/N9001", "code": "TEST/N9001", "titles_by_source": {QID: "Title"}})
        assert "nsqf_level" not in NosUnit.model_fields and unit.titles_by_source[QID] == "Title"
        refused(NosUnit, {"id": "nos:TEST/N9001", "code": "TEST/N9002", "titles_by_source": {QID: "T"}}, "nos:<code>")
        refused(NosUnit, {"id": "nos:TEST/N9001", "code": "TEST/N9001", "titles_by_source": {}})

    def test_module_id_must_match_its_qualification_and_s_no(self):
        refused(type(Qualification.model_validate(curated()).modules[0]), {**module(), "s_no": 2}, "mod:")


class TestProgressionClaims:
    BASE = {"id": f"claim:{CODE}/P1", "qualification_id": QID, "text_verbatim": "Next Role(Vertical)",
            "direction_label": "Vertical", "evidence_id": ev(7)}

    def test_claims_are_display_only_with_no_target_by_default(self):
        c = ProgressionClaim.model_validate(self.BASE)
        assert c.engine_use is EngineUse.DISPLAY_ONLY and c.resolved_target is None

    def test_engine_use_cannot_be_changed(self):
        refused(ProgressionClaim, {**self.BASE, "engine_use": "SAFE_HARD_RULE"})

    def test_a_resolved_target_is_inference_with_evidence(self):
        target = {"qualification_id": "qual:TEST/Q9002", "evidence_id": ev(8)}
        c = ProgressionClaim.model_validate({**self.BASE, "resolved_target": target})
        assert c.resolved_target.evidence_class.value == "INFERENCE"
        refused(ProgressionClaim, {**self.BASE, "resolved_target": {**target, "evidence_class": "OFFICIAL"}})
        refused(ProgressionClaim, {**self.BASE, "resolved_target": {"qualification_id": "qual:TEST/Q9002"}})

    def test_claim_must_belong_to_its_qualification(self):
        refused(ProgressionClaim, {**self.BASE, "qualification_id": "qual:TEST/Q9002"}, "belong")


class TestEligibility:
    def test_spec_roundtrips_and_preserves_raw_text_verbatim(self):
        spec = EligibilitySpec.model_validate({"age_rule": age_rule(), "rows": [row(1), row(5)]})
        assert spec.rows[0].raw_text == "10th Grade pass work"  # the stray word of DQ-09 is preserved
        assert EligibilitySpec.model_validate_json(spec.model_dump_json()) == spec

    def test_rows_must_ascend_and_ids_must_match_s_no(self):
        refused(EligibilitySpec, {"age_rule": age_rule(), "rows": [row(2), row(1)]}, "ascending")
        refused(EligibilitySpec, {"age_rule": age_rule(), "rows": [row(1), row(1)]}, "ascending")
        refused(EligibilityRow, row(3, id=f"rule:{CODE}/E4"), "rule:<code>/E<s_no>")

    def test_age_rule_is_one_age_component(self):
        refused(AgeRule, {**age_rule(), "id": f"rule:{CODE}/E1"}, "/AGE")
        refused(AgeRule, {**age_rule(), "components": [component("EXPERIENCE_MIN_YEARS")]}, "AGE_MIN")
        refused(AgeRule, {**age_rule(), "components": [component(), component()]}, "exactly one")

    def test_rules_need_a_component_and_evidence(self):
        refused(EligibilityRow, row(1, components=[]))
        refused(EligibilityRow, {k: v for k, v in row(1).items() if k != "evidence_id"})

    def test_unmodelled_components_explain_themselves_and_are_never_safe(self):
        refused(Component, component("UNMODELLED"), "never safe")
        refused(Component, component("UNMODELLED", safe=False), "requires unknown_reason")
        assert Component.model_validate(component("UNMODELLED", safe=False, unknown_reason="LITERACY_NOT_MODELLED"))

    def test_named_parameters_are_required_numbers(self):
        for kind, key in (("AGE_MIN", "min_age"), ("PRIOR_NSQF_LEVEL", "level"), ("EXPERIENCE_MIN_YEARS", "years")):
            refused(Component, {**component(kind), "params": {}}, key)
            refused(Component, {**component(kind), "params": {key: "3"}}, key)
            refused(Component, {**component(kind), "params": {key: True}}, key)

    def test_relevance_applies_only_to_level_and_experience(self):
        assert Component.model_validate(component("PRIOR_NSQF_LEVEL", requires_relevance=True))
        refused(Component, component("AGE_MIN", requires_relevance=True), "requires_relevance")

    def test_no_component_type_models_equivalence_exemption_rpl_or_reduced_hours(self):
        names = {t.value for t in ComponentType}
        assert not any(w in n for n in names for w in ("EQUIV", "EXEMPT", "RPL", "REDUC", "HOUR"))


class TestOccupation:
    def test_verified_title_needs_evidence(self):
        data = {"id": "nco:8153.0101", "nco_code": "8153.0101", "title": "Sewing Machine Operator, General",
                "title_verification": "VERIFIED_IN_SOURCE", "evidence_id": ev(1)}
        assert Occupation.model_validate(data).title
        refused(Occupation, {**data, "evidence_id": None}, "requires the title and its evidence_id")
        refused(Occupation, {**data, "title": None}, "requires the title")

    @pytest.mark.parametrize("state", ["NOT_FOUND", "NOT_CHECKED"])
    def test_unverified_title_is_null_and_cannot_be_invented(self, state):
        data = {"id": "nco:3122.3551", "nco_code": "3122.3551", "title_verification": state}
        o = Occupation.model_validate(data)
        assert o.title is None and o.title_verification is TitleVerification(state)
        refused(Occupation, {**data, "title": "Production Supervisor"}, "title must be null")

    def test_levels_are_prefixes_of_the_code(self):
        o = Occupation.model_validate({"id": "nco:8153.0101", "nco_code": "8153.0101", "title_verification": "NOT_CHECKED"})
        assert o.nco_levels == NcoLevels(division="8", sub_division="81", group="815", family="8153")
        refused(Occupation, {"id": "nco:8153.0101", "nco_code": "8153.0101", "title_verification": "NOT_CHECKED",
                             "nco_levels": {"division": "7", "sub_division": "81", "group": "815", "family": "8153"}}, "prefixes")

    def test_id_must_match_code(self):
        refused(Occupation, {"id": "nco:8153.0103", "nco_code": "8153.0101", "title_verification": "NOT_CHECKED"}, "nco:<nco_code>")


class TestSourceDocument:
    BASE = {"id": "src:A5", "manifest_item_id": "A5", "title": "SSMO QF", "org": "AMHSSC", "sha256": SHA,
            "file_type": "pdf", "pages": 23, "validation_status": "PASS_WITH_DISCREPANCIES", "role": "PRIMARY",
            "retrieved_at": "2026-10-30T19:36:00+05:30"}

    def test_licence_defaults_to_unconfirmed(self):
        assert SourceDocument.model_validate(self.BASE).licence_status.value == "UNCONFIRMED"

    def test_role_is_never_defaulted(self):
        refused(SourceDocument, {k: v for k, v in self.BASE.items() if k != "role"})

    def test_available_source_requires_its_hash(self):
        refused(SourceDocument, {**self.BASE, "sha256": None}, "requires the sha256")

    @pytest.mark.parametrize("status", ["FAIL_HTTP", "NOT_FOUND"])
    def test_unavailable_source_cannot_carry_a_hash(self, status):
        refused(SourceDocument, {**self.BASE, "validation_status": status}, "sha256 must be null")
        doc = SourceDocument.model_validate({**self.BASE, "validation_status": status, "sha256": None})
        assert doc.has_local_file is False

    def test_id_must_be_src_plus_manifest_item_id(self):
        refused(SourceDocument, {**self.BASE, "id": "src:A4"}, "src:<manifest_item_id>")

    def test_timestamp_must_carry_a_timezone(self):
        refused(SourceDocument, {**self.BASE, "retrieved_at": "2026-10-30T19:36:00"})


class TestConflict:
    BASE = {"id": "conflict:OV-036", "subject": {"entity_id": "qual:AMH/Q2301", "field": "credits"},
            "values": [{"value": 12, "evidence_id": ev(1)}, {"value": 14, "evidence_id": ev(2)}],
            "status": "UNRESOLVED_SOURCE_CONFLICT", "overlay_ids": ["OV-038", "OV-036", "OV-037"],
            "decision_ref": "D1", "engine_effect": "NOT_USED"}

    def test_valid_conflict_holds_both_values_and_no_selection(self):
        c = Conflict.model_validate(self.BASE)
        assert [v.value for v in c.values] == [12, 14]
        banned = ("select", "resolv", "chosen", "choice", "prefer", "winner", "canonical", "final")
        assert not [n for n in Conflict.model_fields if any(b in n for b in banned)]
        assert {s.value for s in ConflictStatus} == {"UNRESOLVED_SOURCE_CONFLICT", "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE"}

    def test_selected_value_cannot_be_smuggled_in(self):
        refused(Conflict, {**self.BASE, "selected_value": 14})
        refused(Conflict, {**self.BASE, "status": "RESOLVED"})

    def test_a_conflict_needs_two_different_values(self):
        refused(Conflict, {**self.BASE, "values": [self.BASE["values"][0]]}, "two different")
        same = [{"value": 12, "evidence_id": ev(1)}, {"value": 12.0, "evidence_id": ev(2)}]
        refused(Conflict, {**self.BASE, "values": same}, "two different")

    def test_id_is_the_lowest_overlay_of_the_group(self):
        refused(Conflict, {**self.BASE, "id": "conflict:OV-037"}, "lowest overlay")
        refused(Conflict, {**self.BASE, "overlay_ids": []}, "lowest overlay")

    def test_engine_effect_cannot_be_safe(self):
        refused(Conflict, {**self.BASE, "engine_effect": "SAFE_HOURS"}, "safe")
        for ok in ("NOT_USED", "DISPLAY_ONLY", "UNKNOWN"):
            assert Conflict.model_validate({**self.BASE, "engine_effect": ok})

    def test_a_lead_with_an_unavailable_source_holds_no_conflicting_value(self):
        lead = {**self.BASE, "status": "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE", "values": [self.BASE["values"][0]]}
        assert Conflict.model_validate(lead)
        refused(Conflict, {**lead, "values": self.BASE["values"]}, "no conflicting local value")

    def test_subject_must_be_a_valid_entity_id(self):
        refused(Conflict, {**self.BASE, "subject": {"entity_id": "AMH/Q2301", "field": "credits"}})
