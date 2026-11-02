import pytest
from model_factory import ev, official
from pydantic import ValidationError

from skillgraph.model.evidence import (
    CreditValue,
    DisplayValued,
    EngineUse,
    Evidence,
    EvidenceClass,
    Valued,
)

SHA = "a" * 64


def valued(**kw):
    return Valued[float].model_validate({"value": 1.0, "evidence_class": "OFFICIAL", **kw})


class TestValued:
    def test_official_without_evidence_id_is_refused(self):
        with pytest.raises(ValidationError, match="requires evidence_id"):
            valued(value_status="TRANSCRIBED")

    def test_official_with_evidence_id_is_accepted(self):
        v = valued(evidence_id=ev(1), value_status="TRANSCRIBED")
        assert v.evidence_class is EvidenceClass.OFFICIAL and v.evidence_id == ev(1)

    def test_official_without_value_status_is_refused(self):
        with pytest.raises(ValidationError, match="value_status"):
            valued(evidence_id=ev(1))

    @pytest.mark.parametrize("cls", ["RULE_DERIVED", "INFERENCE"])
    def test_other_stored_classes_need_evidence(self, cls):
        with pytest.raises(ValidationError):
            Valued[float].model_validate({"value": 1.0, "evidence_class": cls})
        assert Valued[float].model_validate({"value": 1.0, "evidence_class": cls, "evidence_id": ev(1)})

    @pytest.mark.parametrize("cls", ["DECLARED", "CONFIG", "HYPOTHETICAL"])
    def test_request_scoped_classes_have_no_stored_record(self, cls):
        assert Valued[float].model_validate({"value": 1.0, "evidence_class": cls}).evidence_id is None

    def test_missing_printed_value_stays_null_but_still_cites_evidence(self):
        v = valued(value=None, evidence_id=ev(1), value_status="UNRESOLVED")
        assert v.value is None
        with pytest.raises(ValidationError):
            valued(value=None, value_status="UNRESOLVED")

    def test_value_field_is_required_not_defaulted(self):
        with pytest.raises(ValidationError):
            Valued[float].model_validate({"evidence_class": "OFFICIAL", "evidence_id": ev(1), "value_status": "TRANSCRIBED"})

    @pytest.mark.parametrize("bad", ["12", True, float("nan"), float("inf")])
    def test_numbers_are_never_coerced(self, bad):
        from skillgraph.model.qualification import HoursBreakdown

        with pytest.raises(ValidationError):
            HoursBreakdown.model_validate({"total": official(bad)})

    @pytest.mark.parametrize("use", ["SAFE_HARD_RULE", "SAFE_HOURS", "CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG"])
    def test_conflicted_value_cannot_be_used_safely(self, use):
        with pytest.raises(ValidationError, match="open conflict"):
            valued(evidence_id=ev(1), value_status="TRANSCRIBED", conflict_id="conflict:OV-036", engine_use=use)
        for ok in ("NOT_USED", "DISPLAY_ONLY", "UNKNOWN"):
            valued(evidence_id=ev(1), value_status="TRANSCRIBED", conflict_id="conflict:OV-036", engine_use=ok)

    def test_models_are_closed_and_immutable(self):
        v = valued(evidence_id=ev(1), value_status="TRANSCRIBED")
        with pytest.raises(ValidationError):
            Valued[float].model_validate({**v.model_dump(), "selected": 1})
        with pytest.raises(ValidationError):
            v.value = 2.0

    def test_display_valued_requires_display_only(self):
        base = {"value": "4.0", "evidence_class": "OFFICIAL", "evidence_id": ev(1), "value_status": "TRANSCRIBED"}
        assert DisplayValued[str].model_validate({**base, "engine_use": "DISPLAY_ONLY"})
        for use in (None, "SAFE_HOURS"):
            with pytest.raises(ValidationError):
                DisplayValued[str].model_validate({**base, "engine_use": use})


class TestCredits:
    def test_credits_must_be_not_used(self):
        assert CreditValue.model_validate(official(14.0, engine_use="NOT_USED")).engine_use is EngineUse.NOT_USED
        for use in (None, "SAFE_HOURS", "DISPLAY_ONLY", "SAFE_HARD_RULE"):
            with pytest.raises(ValidationError, match="NOT_USED"):
                CreditValue.model_validate(official(14.0, engine_use=use))

    def test_credits_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            CreditValue.model_validate(official(-1.0, engine_use="NOT_USED"))


class TestEvidence:
    OFFICIAL = {"id": ev(1), "evidence_class": "OFFICIAL", "source_id": "src:A5", "source_sha256": SHA, "page": "3-4"}

    def test_official_needs_source_hash_and_a_locator(self):
        assert Evidence.model_validate(self.OFFICIAL)
        assert Evidence.model_validate({**self.OFFICIAL, "page": None, "location": "catalogue row 1"})
        for missing in ("source_id", "source_sha256"):
            with pytest.raises(ValidationError, match="requires source_id"):
                Evidence.model_validate({**self.OFFICIAL, missing: None})
        with pytest.raises(ValidationError, match="page or a location"):
            Evidence.model_validate({**self.OFFICIAL, "page": None})

    def test_hash_must_be_lowercase_sha256(self):
        for bad in ("A" * 64, "a" * 63, "g" * 64):
            with pytest.raises(ValidationError):
                Evidence.model_validate({**self.OFFICIAL, "source_sha256": bad})

    def test_derived_classes_need_parents_and_carry_no_source(self):
        derived = {"id": ev(9), "evidence_class": "RULE_DERIVED", "derived_from": [ev(1), ev(2)], "method": "rule:sum"}
        assert Evidence.model_validate(derived)
        for cls in ("RULE_DERIVED", "INFERENCE"):
            with pytest.raises(ValidationError, match="requires derived_from"):
                Evidence.model_validate({"id": ev(9), "evidence_class": cls})
        with pytest.raises(ValidationError, match="must not carry"):
            Evidence.model_validate({**derived, "source_id": "src:A5", "source_sha256": SHA})
        with pytest.raises(ValidationError, match="distinct"):
            Evidence.model_validate({**derived, "derived_from": [ev(9)]})
        with pytest.raises(ValidationError, match="distinct"):
            Evidence.model_validate({**derived, "derived_from": [ev(1), ev(1)]})

    def test_class_specific_fields_do_not_leak_between_classes(self):
        with pytest.raises(ValidationError):
            Evidence.model_validate({**self.OFFICIAL, "derived_from": [ev(2)]})
        with pytest.raises(ValidationError):
            Evidence.model_validate({**self.OFFICIAL, "declared_field": "age_years"})
        with pytest.raises(ValidationError):
            Evidence.model_validate({**self.OFFICIAL, "config_key": "nsqf_level_match"})
        assert Evidence.model_validate({"id": ev(3), "evidence_class": "DECLARED", "declared_field": "age_years"})
        assert Evidence.model_validate({"id": ev(4), "evidence_class": "CONFIG", "config_key": "nsqf_level_match"})
        for cls in ("DECLARED", "CONFIG"):
            with pytest.raises(ValidationError):
                Evidence.model_validate({"id": ev(5), "evidence_class": cls})

    def test_overlay_and_decision_references_are_format_checked(self):
        assert Evidence.model_validate({**self.OFFICIAL, "overlay_ids": ["OV-019"], "decision_refs": ["D2", "A3"]})
        with pytest.raises(ValidationError):
            Evidence.model_validate({**self.OFFICIAL, "overlay_ids": ["OV-19"]})
        with pytest.raises(ValidationError):
            Evidence.model_validate({**self.OFFICIAL, "decision_refs": ["X1"]})
