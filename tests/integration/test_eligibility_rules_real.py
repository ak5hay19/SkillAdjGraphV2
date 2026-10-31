"""P1.5 Checkpoint B against the real P1.4 output. Skips when the restricted data is absent.

The source rows come from a fresh build into a temporary directory (the protected inputs are hashed before and
after); ``config/overlay_approvals.yaml`` is never written. Numbers 1-11 are the Checkpoint B tests of TASKS.md.
The age rules are blocked on the unresolved decision P1.5-A1, and these tests assert exactly that.
"""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from skillgraph.curation import eligibility_rules as er
from skillgraph.curation.build import build
from skillgraph.curation.config import CURATION_CODE_VERSION, DEFAULTS_PATH
from skillgraph.curation.eligibility_rules import DELIMITER
from skillgraph.curation.overlay import APPROVALS_PATH
from skillgraph.model.eligibility import ComponentType, UnknownReasonCode
from skillgraph.model.evidence import SAFE_USES, EngineUse
from skillgraph.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
pytestmark = [
    pytest.mark.requires_local_data,
    pytest.mark.skipif(not (DATA / "raw" / "2026-10-30" / "MANIFEST.csv").is_file(), reason="local data not found"),
]

UNKNOWN_ROWS = {"AMH/Q0301/E2", "AMH/Q0301/E5", "AMH/Q2301/E1", "AMH/Q2301/E2", "AMH/Q2301/E3", "AMH/Q2301/E4",
                "AMH/Q2301/E5", "AMH/Q2301/E6"}


def protected_hashes() -> dict[str, str]:
    files = [p for d in ("raw", "processed") for p in (DATA / d).rglob("*") if p.is_file()]
    files += [REPO / APPROVALS_PATH, REPO / DEFAULTS_PATH, REPO / er.RULES_PATH]
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def run_build(out: Path, rules: Path | None = None):
    settings = load_settings(REPO / "config" / "default.yaml", DATA, environ={})
    return build(settings, approvals_path=REPO / APPROVALS_PATH, config_path=REPO / DEFAULTS_PATH,
                 rules_path=rules or REPO / er.RULES_PATH, out_root=out)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    before = protected_hashes()
    first = run_build(tmp_path_factory.mktemp("curated_a"))
    second = run_build(tmp_path_factory.mktemp("curated_b"))
    assert protected_hashes() == before, "a build changed a protected input"
    return first, second


@pytest.fixture(scope="module")
def source_path(built) -> Path:
    return built[0].path / "eligibility_source_rows.json"


@pytest.fixture(scope="module")
def source(source_path):
    return er.load_source_rows(source_path)


@pytest.fixture(scope="module")
def config():
    return er.load_rules_config(REPO / er.RULES_PATH)


@pytest.fixture(scope="module")
def structured(source, config):
    return er.structure_all(source, config, allow_blocked=True)


def comps(structured):
    out = {}
    for r in structured.rows:
        for n, c in enumerate(r.components, start=1):
            out[er.component_id(r.id, n)] = c
    for rid, cs in structured.age_components.items():
        for n, c in enumerate(cs, start=1):
            out[er.component_id(rid, n)] = c
    return out


def short(rule_id: str) -> str:
    return rule_id.removeprefix("rule:")


# ----------------------------------------------------------------------------------- the inputs are untouched
def test_the_real_approvals_file_is_still_empty_and_the_source_rows_are_immutable(built, source_path, source):
    assert yaml.safe_load((REPO / APPROVALS_PATH).read_text(encoding="utf-8")) == {"approved": []}
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    er.structure_all(source, er.load_rules_config(REPO / er.RULES_PATH), allow_blocked=True)
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == digest


def test_the_build_is_deterministic_and_the_build_identity_is_unchanged(built):
    first, second = built
    assert first.data_build_id == second.data_build_id
    for name in ("eligibility_source_rows.json", "qualifications.json", "evidence.json", "conflicts.json"):
        assert (first.path / name).read_bytes() == (second.path / name).read_bytes(), name
    assert CURATION_CODE_VERSION == "p1.5-1"  # Checkpoint C changes the curated output, so the version moved


def test_a_repeated_structuring_gives_identical_results_whatever_the_input_order(source, config):
    def dump(rows):
        s = er.structure_all(rows, config, allow_blocked=True)
        return [m.model_dump_json() for m in s.rows], {k: [c.model_dump_json() for c in v] for k, v in s.age_components.items()}, s.blocked

    assert dump(source) == dump(source) == dump(list(reversed(source)))


# ------------------------------------------------------------------------------------ 1. count, 2. order, ids
def test_1_every_row_is_structured_with_one_component_per_printed_cell(structured, source):
    assert len(structured.rows) == 24 and len(structured.age_components) == 4
    assert all(len(r.components) == 2 for r in structured.rows)
    assert all(len(v) == 1 for v in structured.age_components.values())
    assert len(comps(structured)) == 52
    assert {r.id for r in structured.rows} | set(structured.age_components) == {s.id for s in source}


def test_2_components_follow_the_printed_cell_order(structured, source):
    by_id = {s.id: s for s in source}
    for r in structured.rows:
        s = by_id[r.id]
        assert [c.evidence_id for c in r.components] == [s.raw_academic_or_skill.evidence_id, s.raw_required_experience.evidence_id]
        assert r.evidence_id == s.raw_row_text.evidence_id
    for rid, (c,) in structured.age_components.items():
        assert c.type is ComponentType.AGE_MIN and c.evidence_id == by_id[rid].min_age.evidence_id
    ids = list(comps(structured))
    assert len(ids) == len(set(ids)) and all("#c" in i for i in ids)


# ----------------------------------------------------------------------------- 3. verbatim, 4. empty, 5. delimiter
def test_3_verbatim_round_trip_over_every_row(structured, source, config):
    by_id = {s.id: s for s in source}
    for r in structured.rows:
        s = by_id[r.id]
        academic, experience = er.split_cells(r.raw_text)
        assert (academic, experience) == (s.raw_academic_or_skill.value, s.raw_required_experience.value)
        assert academic + DELIMITER + experience == r.raw_text == s.raw_row_text.value
        cfg = config.get(r.id)
        assert [c.text for c in cfg.components] == [academic, experience]


def test_4_empty_experience_cells_keep_the_trailing_delimiter(structured):
    rows = {short(r.id): r for r in structured.rows}
    for key in ("AMH/Q2301/E2", "AMH/Q2301/E3", "AMH/Q2301/E4"):
        r = rows[key]
        assert r.raw_text.endswith(" || ") and er.split_cells(r.raw_text)[1] == ""
        experience = r.components[1]
        assert experience.type is ComponentType.UNMODELLED and not experience.safe
        assert experience.unknown_reason is UnknownReasonCode.OVERLAY_NOT_APPROVED
        assert experience.params == {}  # nothing is back-filled
    others = [r for k, r in rows.items() if k not in ("AMH/Q2301/E2", "AMH/Q2301/E3", "AMH/Q2301/E4")]
    assert all(er.split_cells(r.raw_text)[1] != "" for r in others)


def test_5_no_real_cell_contains_the_delimiter(source):
    for s in source:
        if s.raw_academic_or_skill:
            assert DELIMITER not in s.raw_academic_or_skill.value and DELIMITER not in s.raw_required_experience.value


# --------------------------------------------------------------------------------------------- 6. stale tables
def test_6_a_changed_source_makes_the_structuring_fail(source, config):
    victim = next(s for s in source if s.id == "rule:AMH/Q0301/E5")
    cell = victim.raw_required_experience.model_copy(update={"value": "6 year relevant experience"})
    text = victim.raw_row_text.model_copy(update={"value": "Ability to read and write || 6 year relevant experience"})
    changed = victim.model_copy(update={"raw_required_experience": cell, "raw_row_text": text})
    with pytest.raises(er.EligibilityRulesError, match="row text changed|source cell is"):
        er.structure_row(changed, config.get(victim.id))
    with pytest.raises(er.EligibilityRulesError, match="no mapping for"):
        er.structure_all([s for s in source] + [source[0].model_copy(update={"id": "rule:AMH/Q0301/E8", "s_no": 8})], config)
    with pytest.raises(er.EligibilityRulesError, match="mapping without a source row"):
        er.structure_all(source[1:], config, allow_blocked=True)
    other_use = next(s for s in source if s.id == "rule:AMH/Q2301/E7").model_copy(update={"engine_use": EngineUse.UNKNOWN})
    with pytest.raises(er.EligibilityRulesError, match="engine_use"):
        er.structure_row(other_use, config.get(other_use.id))


# ------------------------------------------------------------------------------ 7. the safe/reason invariant
def test_7_safe_false_requires_a_reason_and_safe_true_has_none_for_every_component(structured):
    for key, c in comps(structured).items():
        er.check_component_invariant(c, key)
        assert c.safe == (c.unknown_reason is None), key
        if c.type is ComponentType.UNMODELLED:
            assert not c.safe


# ------------------------------------------------------------------------------------- 8. requires_relevance
def test_8_requires_relevance_is_a_separate_field_with_the_expected_extent(structured, source):
    by_id = {s.id: s for s in source}
    for r in structured.rows:
        s = by_id[r.id]
        academic = r.components[0]
        expected_academic = academic.type is ComponentType.PRIOR_NSQF_LEVEL
        assert academic.requires_relevance == expected_academic
        experience = r.components[1]
        if experience.type is ComponentType.EXPERIENCE_MIN_YEARS:
            text = s.raw_required_experience.value.lower()
            assert experience.requires_relevance == ("relevant" in text), r.id
    for c in comps(structured).values():
        assert "requires_relevance" not in c.params
        projected = er.response_params(c)
        assert ("requires_relevance" in projected) == c.requires_relevance
        assert {k: v for k, v in projected.items() if k != "requires_relevance"} == c.params


# ---------------------------------------------------------------------------------------- 9. pending overlays
def test_9_pending_overlays_are_not_applied_and_not_listed_as_overlay_ids(structured):
    rows = {short(r.id): r for r in structured.rows}
    for key, pending in (("AMH/Q2301/E2", "OV-002"), ("AMH/Q2301/E3", "OV-003"), ("AMH/Q2301/E4", "OV-004")):
        r = rows[key]
        assert pending not in r.overlay_ids
        assert any(f.code.value == "OVERLAY_PENDING_APPROVAL" and pending in f.refs for f in r.flags)
    for r in structured.rows:
        assert not {"OV-002", "OV-003", "OV-004"} & set(r.overlay_ids)


# ------------------------------------------------------------------------------------------ 10. no upgrades
def test_10_no_rule_or_component_is_upgraded(structured, source):
    by_id = {s.id: s for s in source}
    for r in structured.rows:
        s = by_id[r.id]
        assert r.engine_use is s.engine_use  # the rule keeps the source row's use
        safe = [c.safe for c in r.components]
        if s.engine_use in SAFE_USES:
            assert all(safe), r.id
        elif short(r.id) == "AMH/Q2301/E1":
            assert safe == [False, True]
        else:
            assert not any(safe), r.id  # no sibling and no pending overlay makes an UNKNOWN row evaluable


def test_10_the_unknown_rows_and_the_documented_exception(structured):
    unknown = {short(r.id) for r in structured.rows if r.engine_use.value == "UNKNOWN"}
    assert unknown == UNKNOWN_ROWS
    for r in structured.rows:
        has_unmodelled = any(c.type is ComponentType.UNMODELLED for c in r.components)
        if short(r.id) == "AMH/Q2301/E1":
            assert not has_unmodelled
            grade, years = r.components
            assert (grade.type, grade.params, grade.safe, grade.unknown_reason) == (
                ComponentType.SCHOOL_GRADE_MIN, {"grade": 11}, False, UnknownReasonCode.UNCERTAIN_EXTRACTION)
            assert (years.type, years.params, years.safe, years.requires_relevance) == (
                ComponentType.EXPERIENCE_MIN_YEARS, {"years": 0.0}, True, False)
        elif short(r.id) in UNKNOWN_ROWS:
            assert has_unmodelled, r.id


def test_10_smo_row_5_experience_is_unsafe_and_undecided_not_uncertain(structured):
    rows = {short(r.id): r for r in structured.rows}
    literacy, experience = rows["AMH/Q0301/E5"].components
    assert (literacy.type, literacy.unknown_reason) == (ComponentType.UNMODELLED, UnknownReasonCode.LITERACY_NOT_MODELLED)
    assert (experience.type, experience.params, experience.requires_relevance, experience.safe, experience.unknown_reason) == (
        ComponentType.EXPERIENCE_MIN_YEARS, {"years": 5.0}, True, False, UnknownReasonCode.ENGINE_USE_UNDECIDED)


def test_10_the_audit_review_request_cells_stay_capped(structured):
    cells = comps(structured)
    expected = {"rule:AMH/Q2301/E5#c2": UnknownReasonCode.UNCERTAIN_EXTRACTION,
                "rule:AMH/Q2301/E6#c2": UnknownReasonCode.UNCERTAIN_EXTRACTION,
                "rule:AMH/Q0301/E2#c2": UnknownReasonCode.UNCERTAIN_EXTRACTION,
                "rule:AMH/Q0301/E5#c2": UnknownReasonCode.ENGINE_USE_UNDECIDED}
    for key, reason in expected.items():
        assert cells[key].safe is False and cells[key].unknown_reason is reason, key


def test_10_equivalence_and_the_review_flag_conventions(structured):
    cells = comps(structured)
    assert {k for k, c in cells.items() if c.or_equivalent} == {"rule:AMH/Q2101/E1#c1", "rule:AMH/Q2101/E3#c1"}
    assert cells["rule:AMH/Q2101/E3#c1"].type is ComponentType.SCHOOL_GRADE_MIN
    assert cells["rule:AMH/Q2301/E5#c1"].unknown_reason is UnknownReasonCode.REVIEW_FLAG
    assert cells["rule:AMH/Q0301/E1#c1"].params == {"grade": 9, "below_required_verdict": "UNKNOWN"}
    assert cells["rule:AMH/Q2301/E6#c1"].or_equivalent is False
    assert cells["rule:AMH/Q2101/E1#c1"].params == {"credential": "UG_DIPLOMA"}
    assert cells["rule:AMH/Q2101/E2#c1"].params == {"credential": "UG_CERTIFICATE"}
    level_rows = {k: c.params["level"] for k, c in cells.items() if c.type is ComponentType.PRIOR_NSQF_LEVEL}
    assert len(level_rows) == 7 and all(isinstance(v, float) for v in level_rows.values())
    assert {v for v in level_rows.values()} == {1.0, 2.0, 2.5, 3.0, 4.0}


# --------------------------------------------------------------------------- 11. the age rules (A1, authorized Option 1)
AGE_TEXT = {"AMH/Q0301": "Age: 18 years", "AMH/Q2301": "Age: 18 years", "AMH/Q0103": "Age: 18 years",
            "AMH/Q2101": "Age: 20 years"}


def test_11_the_age_rules_are_built_from_the_verbatim_text_and_its_own_evidence(structured, source, config):
    ages = [s for s in source if s.id.endswith("/AGE")]
    assert len(ages) == 4 and structured.blocked == {} and len(structured.age_rules) == 4
    for row in ages:
        code = row.id.split(":", 1)[1].removesuffix("/AGE")
        text = row.raw_row_text
        assert text.value == AGE_TEXT[code]  # verbatim, without the item label "c."
        assert text.value_status.value == "TRANSCRIBED" and text.engine_use is EngineUse.UNKNOWN  # never geometry, never safe
        assert text.evidence_id is not None and text.evidence_id != row.min_age.evidence_id
        assert row.min_age.value_status.value == "CONFIRMED_BY_GEOMETRY" and row.min_age.engine_use is EngineUse.SAFE_HARD_RULE
        assert text.source_value is None and text.source_evidence_id is None
    for rule in structured.age_rules:
        code = rule.id.split(":", 1)[1].removesuffix("/AGE")
        row = next(r for r in ages if r.id == rule.id)
        assert rule.raw_text == AGE_TEXT[code] and rule.evidence_id == row.raw_row_text.evidence_id
        (component,) = rule.components  # the number keeps its own geometry-confirmed evidence
        assert component.type is ComponentType.AGE_MIN and component.safe and component.unknown_reason is None
        assert component.evidence_id == row.min_age.evidence_id
    assert len(er.structure_all(source, config).age_rules) == 4


# =============================================================================================================
# Checkpoint C: the build populates Qualification.eligibility
# =============================================================================================================
OLD_BUILD = DATA / "curated" / "cb-0e76c97bea00"  # the P1.4 build (code version p1.4-3); it must never be rewritten


def stored_quals(result) -> dict:
    data = json.loads((result.path / "qualifications.json").read_text(encoding="utf-8"))
    return {q["code"]: q for q in data}


def stored_rows(result) -> dict:
    return {r["id"]: r for q in stored_quals(result).values() if q.get("eligibility") for r in q["eligibility"]["rows"]}


def test_c1_every_curated_qualification_carries_its_structured_eligibility(built):
    quals = stored_quals(built[0])
    curated = {c: q for c, q in quals.items() if q["coverage"] == "CURATED"}
    assert sorted(curated) == ["AMH/Q0103", "AMH/Q0301", "AMH/Q2101", "AMH/Q2301"]
    assert all(q["eligibility"] is not None for q in curated.values())
    assert all(q["eligibility"] is None for c, q in quals.items() if c not in curated)  # catalogue-only: none
    assert {c: len(q["eligibility"]["rows"]) for c, q in curated.items()} == {
        "AMH/Q0103": 4, "AMH/Q0301": 7, "AMH/Q2101": 4, "AMH/Q2301": 9}
    for code, q in curated.items():
        numbers = [r["s_no"] for r in q["eligibility"]["rows"]]
        assert numbers == sorted(set(numbers))  # strictly ascending, as printed
        assert q["eligibility"]["age_rule"]["id"] == f"rule:{code}/AGE"


def test_c2_the_stored_eligibility_is_exactly_what_the_structuring_layer_gives(built, source, config):
    expected = er.assemble_specs(er.structure_all(source, config))
    for code, q in stored_quals(built[0]).items():
        if q["eligibility"] is not None:
            assert q["eligibility"] == expected[code].model_dump(mode="json")


def test_c3_the_age_rules_use_the_verbatim_text_and_keep_the_geometry_confirmed_value(built):
    texts = {"AMH/Q0301": "Age: 18 years", "AMH/Q2301": "Age: 18 years", "AMH/Q0103": "Age: 18 years",
             "AMH/Q2101": "Age: 20 years"}
    rows = {r["id"]: r for r in json.loads((built[0].path / "eligibility_source_rows.json").read_text(encoding="utf-8"))}
    for code, q in stored_quals(built[0]).items():
        if q["eligibility"] is None:
            continue
        age = q["eligibility"]["age_rule"]
        source_row = rows[f"rule:{code}/AGE"]
        assert age["raw_text"] == texts[code] and age["evidence_id"] == source_row["raw_row_text"]["evidence_id"]
        (component,) = age["components"]
        assert component["evidence_id"] == source_row["min_age"]["evidence_id"] != age["evidence_id"]
        assert component["safe"] is True and component["unknown_reason"] is None
        assert source_row["min_age"]["value_status"] == "CONFIRMED_BY_GEOMETRY"
        assert source_row["raw_row_text"]["value_status"] == "TRANSCRIBED"  # never upgraded to geometry-confirmed


def test_c4_the_unknown_rows_the_caps_and_the_pending_overlays_survive_the_build(built):
    rows = stored_rows(built[0])
    assert {short(i) for i, r in rows.items() if r["engine_use"] == "UNKNOWN"} == UNKNOWN_ROWS
    experience = rows["rule:AMH/Q0301/E5"]["components"][1]
    assert experience["safe"] is False and experience["unknown_reason"] == "ENGINE_USE_UNDECIDED"
    assert experience["params"] == {"years": 5.0} and experience["requires_relevance"] is True
    for rid in ("rule:AMH/Q2301/E5", "rule:AMH/Q2301/E6", "rule:AMH/Q0301/E2"):  # the P1.5-R1 cells stay capped
        assert rows[rid]["components"][1]["safe"] is False
    e1 = rows["rule:AMH/Q2301/E1"]["components"]
    assert (e1[0]["safe"], e1[0]["unknown_reason"]) == (False, "UNCERTAIN_EXTRACTION")
    assert (e1[1]["safe"], e1[1]["params"]) == (True, {"years": 0.0})
    for row in rows.values():
        assert not {"OV-002", "OV-003", "OV-004"} & set(row["overlay_ids"])
        for c in row["components"]:
            assert (c["unknown_reason"] is None) == c["safe"]  # the curated-data invariant
            assert "requires_relevance" not in c["params"]


def test_c5_the_new_build_has_its_own_identity_and_the_old_build_is_untouched(built):
    first, second = built
    assert first.data_build_id == second.data_build_id != "cb-0e76c97bea00"
    assert first.manifest["curation_code_version"] == "p1.5-1"
    assert first.manifest["eligibility_rules_digest"] == er.rules_digest(er.load_rules_config(REPO / er.RULES_PATH))
    for name in ("qualifications.json", "evidence.json", "eligibility_source_rows.json"):  # byte-identical rebuilds
        assert (first.path / name).read_bytes() == (second.path / name).read_bytes(), name
    if OLD_BUILD.is_dir():  # p1.4-3 stays as it was: no age text, no eligibility
        old = json.loads((OLD_BUILD / "build_manifest.json").read_text(encoding="utf-8"))
        assert old["curation_code_version"] == "p1.4-3" and "eligibility_rules_digest" not in old
        old_quals = json.loads((OLD_BUILD / "qualifications.json").read_text(encoding="utf-8"))
        assert all(q.get("eligibility") is None for q in old_quals)


def test_c6_a_changed_table_changes_the_build_identity_but_a_comment_does_not(built, tmp_path):
    text = (REPO / er.RULES_PATH).read_text(encoding="utf-8")
    commented = tmp_path / "commented.yaml"
    commented.write_text(text + "\n# a comment changes nothing\n", encoding="utf-8")
    assert run_build(tmp_path / "same", commented).data_build_id == built[0].data_build_id
    config = yaml.safe_load(text)
    config["rules"][0]["review_note"] = "changed wording"
    changed = tmp_path / "changed.yaml"
    changed.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert run_build(tmp_path / "other", changed).data_build_id != built[0].data_build_id


def test_c7_a_stale_or_incomplete_table_fails_the_build_and_installs_nothing(tmp_path):
    config = yaml.safe_load((REPO / er.RULES_PATH).read_text(encoding="utf-8"))
    use = config["rules"][0]["expect"]["row_engine_use"]
    config["rules"][0]["expect"]["row_engine_use"] = "NOT_USED" if use != "NOT_USED" else "UNKNOWN"
    stale = tmp_path / "stale.yaml"
    stale.write_text(yaml.safe_dump(config), encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(er.EligibilityRulesError):
        run_build(out, stale)
    assert not out.exists() or list(out.iterdir()) == []
    missing = yaml.safe_load((REPO / er.RULES_PATH).read_text(encoding="utf-8"))
    missing["rules"] = missing["rules"][1:]  # a source row without a mapping
    path = tmp_path / "missing.yaml"
    path.write_text(yaml.safe_dump(missing), encoding="utf-8")
    out2 = tmp_path / "out2"
    with pytest.raises(er.EligibilityRulesError, match="no mapping"):
        run_build(out2, path)
    assert not out2.exists() or list(out2.iterdir()) == []


def test_c8_an_applied_correction_fails_the_build_closed_under_a2(tmp_path):
    approvals = tmp_path / "approvals.yaml"
    approvals.write_text(yaml.safe_dump({"approved": [
        {"overlay_id": "OV-002", "approved_by": "test-fixture", "approved_on": "2026-01-01", "note": ""}]}), encoding="utf-8")
    out = tmp_path / "out"
    settings = load_settings(REPO / "config" / "default.yaml", DATA, environ={})
    before = protected_hashes()
    with pytest.raises(er.CorrectionNotSupported, match="P1.5-A2"):
        build(settings, approvals_path=approvals, config_path=REPO / DEFAULTS_PATH,
              rules_path=REPO / er.RULES_PATH, out_root=out)
    assert not out.exists() or list(out.iterdir()) == []
    assert protected_hashes() == before
    assert yaml.safe_load((REPO / APPROVALS_PATH).read_text(encoding="utf-8")) == {"approved": []}


def test_c9_the_api_projection_follows_the_documented_contract(built):
    from skillgraph.model.eligibility import EligibilitySpec

    quals = stored_quals(built[0])
    smo = er.project_spec(EligibilitySpec.model_validate(quals["AMH/Q0301"]["eligibility"]))
    assert smo["age"]["rule_id"] == "rule:AMH/Q0301/AGE"
    (age_component,) = smo["age"]["components"]
    assert {k: v for k, v in age_component.items() if k != "evidence_ids"} == {
        "component_id": "rule:AMH/Q0301/AGE#c1", "type": "AGE_MIN", "requirement_text": "Age: 18 years",
        "params": {"min_age": 18}}
    rows = {r["s_no"]: r for r in smo["rows"]}
    assert [r["s_no"] for r in smo["rows"]] == sorted(rows)
    e5 = rows[5]["components"]
    assert [c["component_id"] for c in e5] == ["rule:AMH/Q0301/E5#c1", "rule:AMH/Q0301/E5#c2"]
    assert e5[1]["params"] == {"years": 5.0, "requires_relevance": True}  # projected only because the field is true
    assert rows[5]["raw_text"].split(" || ")[1] == e5[1]["requirement_text"]  # the verbatim cell, nothing paraphrased
    for rule in [smo["age"], *smo["rows"]]:
        for c in rule["components"]:
            assert set(c) == {"component_id", "type", "requirement_text", "params", "evidence_ids"}  # no internals
    ssmo = {r["rule_id"]: r for r in er.project_spec(EligibilitySpec.model_validate(quals["AMH/Q2301"]["eligibility"]))["rows"]}
    assert [f["code"] for f in ssmo["rule:AMH/Q2301/E1"]["flags"]] == ["UNCERTAIN_EXTRACTION"]
    pending = [f for f in ssmo["rule:AMH/Q2301/E2"]["flags"] if f["code"] == "OVERLAY_PENDING_APPROVAL"]
    assert [f["refs"] for f in pending] == [["OV-002"]] and ssmo["rule:AMH/Q2301/E2"]["overlay_ids"] != ["OV-002"]
    assert all(set(r) == {"rule_id", "s_no", "raw_text", "engine_use", "overlay_ids", "flags", "components"} for r in smo["rows"])
    assert set(smo["age"]) == {"rule_id", "raw_text", "engine_use", "overlay_ids", "flags", "components"}
    ps = er.project_spec(EligibilitySpec.model_validate(quals["AMH/Q2101"]["eligibility"]))
    for rule in ps["rows"]:
        for c in rule["components"]:
            if c["type"] not in ("PRIOR_NSQF_LEVEL", "EXPERIENCE_MIN_YEARS"):
                assert "requires_relevance" not in c["params"]
