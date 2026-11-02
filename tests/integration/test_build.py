"""P1.4 against the real extraction, audit overlay and manifest. Skips when the restricted data is absent.

Approvals used here are written to temporary files only: ``config/overlay_approvals.yaml`` is the user's decision
(Q-2) and no test touches it.
"""

import csv
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from skillgraph.curation.build import build
from skillgraph.curation.config import DEFAULTS_PATH
from skillgraph.curation.overlay import APPROVALS_PATH, load_overlay, load_plan
from skillgraph.curation.targets import TargetKind, check_source_value, resolve_target
from skillgraph.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
EXTRACTED = DATA / "processed" / "extracted_2026-10-30"
OVERLAY = DATA / "processed" / "audit_2026-10-30_m1s1" / "corrections_overlay.csv"
pytestmark = [
    pytest.mark.requires_local_data,
    pytest.mark.skipif(not (DATA / "raw" / "2026-10-30" / "MANIFEST.csv").is_file(), reason="local data not found"),
]
SAFE = {"SAFE_HARD_RULE", "SAFE_WITH_CONSTRAINT", "SAFE_HOURS", "CONDITIONAL_ON_DECLARED_RELEVANCE",
        "CONDITIONAL_ON_DECLARED_RELEVANCE+LEVEL_CONFIG"}


def run(out: Path, approve: list[str] = (), tmp: Path | None = None):
    path = REPO / APPROVALS_PATH
    if approve:
        path = (tmp or out.parent) / "approvals.yaml"
        path.write_text(yaml.safe_dump({"approved": [
            {"overlay_id": o, "approved_by": "test-fixture", "approved_on": "2026-01-01", "note": ""} for o in approve]}),
            encoding="utf-8")
    return build(load_settings(REPO / "config" / "default.yaml", DATA, environ={}), approvals_path=path,
                 config_path=REPO / DEFAULTS_PATH, rules_path=REPO / "config" / "eligibility_rules.yaml", out_root=out)


def tree_hashes() -> dict[str, str]:
    files = [p for d in ("raw", "processed") for p in (DATA / d).rglob("*") if p.is_file()]
    files += [REPO / APPROVALS_PATH, REPO / DEFAULTS_PATH]
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("curated")
    before = tree_hashes()
    result = run(out)
    assert tree_hashes() == before, "a build changed an input"
    return result


def load(result, name):
    return json.loads((result.path / name).read_text(encoding="utf-8"))


def by_id(items):
    return {i["id"]: i for i in items}


def test_real_approvals_file_is_still_empty():
    assert yaml.safe_load((REPO / APPROVALS_PATH).read_text(encoding="utf-8")) == {"approved": []}


def test_every_overlay_target_resolves_exactly_and_matches_the_extraction():
    tables = {f.name: list(csv.DictReader(f.open(encoding="utf-8-sig", newline=""))) for f in EXTRACTED.glob("*.csv")}
    for t in tables.values():
        for i, r in enumerate(t, start=2):
            r["_line"] = str(i)
    kinds = {}
    for ov in load_overlay(OVERLAY):
        t = resolve_target(ov, tables)
        check_source_value(ov, t)
        kinds[ov.overlay_id] = t
    assert len(kinds) == 52
    assert {k for k, t in kinds.items() if t.kind is TargetKind.COMPOSITE} == {"OV-034", "OV-035"}
    assert kinds["OV-033"].kind is TargetKind.RANGE and len(kinds["OV-033"].rows) == 2
    assert kinds["OV-041"].kind is TargetKind.SEQUENCE
    assert kinds["OV-032"].kind is TargetKind.CELL
    for oid in ("OV-034", "OV-035"):
        bridge, nos = kinds[oid].rows
        assert bridge["is_bridge"] == "true" and bridge["nos_code"] == "" and bridge["credits"] == ""
        assert nos["credits"] != "" and int(nos["s_no"]) == int(bridge["s_no"]) + 1


def test_overlay_summary_with_empty_approvals(built):
    m = built.manifest
    assert m["overlays"] == {"applied": [], "pending": ["OV-002", "OV-003", "OV-004", "OV-034", "OV-035"],
                             "display_only": 11}
    assert m["overlay_classification_counts"] == {"APPLY": 0, "DISPLAY": 11, "IGNORE": 1, "INTERPRET": 35, "PENDING": 5}
    # classification counts and engine-use counts are different quantities
    assert m["overlay_engine_use_counts"]["DISPLAY_ONLY"] == 7 != m["overlays"]["display_only"]
    assert len(m["overlay_effects"]) == 52
    assert m["overlay_effects"]["OV-001"] == {"classification": "INTERPRET", "effect": "STATUS_UPGRADED"}
    assert m["overlay_effects"]["OV-028"]["classification"] == "INTERPRET"  # not "applied"
    assert m["inputs"]["approvals_digest"].startswith("sha256:")
    assert m["counts"] == {"qualifications_curated": 4, "qualifications_catalogue_only": 33, "nos_units": 22,
                           "occupations": 4, "eligibility_rows": 24, "age_rows": 4, "conflicts_open": 3}


def test_pending_rows_change_no_value(built):
    rows = by_id(load(built, "eligibility_source_rows.json"))
    for n in (2, 3, 4):
        r = rows[f"rule:AMH/Q2301/E{n}"]
        exp = r["raw_required_experience"]
        assert exp["value"] == "" and exp["value_status"] == "PARSED_UNCERTAIN" and exp["source_value"] is None
        assert r["pending_overlay_ids"] == [f"OV-00{n}"] and r["engine_use"] == "UNKNOWN"
    q = by_id(load(built, "qualifications.json"))
    assert q["qual:AMH/Q0301"]["credit_groups"] == [] and q["qual:AMH/Q2301"]["credit_groups"] == []


def test_every_official_value_has_evidence_with_source_sha_and_page(built):
    ev = by_id(load(built, "evidence.json"))
    src = by_id(load(built, "sources.json"))

    def walk(node):
        if isinstance(node, dict):
            if node.get("evidence_class") == "OFFICIAL" and "value" in node:
                e = ev[node["evidence_id"]]
                assert e["source_sha256"] == src[e["source_id"]]["sha256"] and e["source_sha256"]
                assert e["page"] or e["location"]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for name in ("qualifications.json", "eligibility_source_rows.json"):
        walk(load(built, name))
    assert all(e["evidence_class"] != "OFFICIAL" or e["page"] or e["location"] for e in ev.values())


def test_credits_are_only_ever_not_used(built):
    def walk(node, key=""):
        if isinstance(node, dict):
            if key.startswith("credits") and "engine_use" in node:
                assert node["engine_use"] == "NOT_USED", key
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)

    walk(load(built, "qualifications.json"))
    q = by_id(load(built, "qualifications.json"))["qual:AMH/Q2301"]
    assert not any(k for k in q["hours"] if q["hours"][k]["engine_use"] == "NOT_USED")


def test_dq01_and_dq02_conflicts_hold_no_selected_value(built):
    conflicts = by_id(load(built, "conflicts.json"))
    assert sorted(conflicts) == ["conflict:OV-036", "conflict:OV-038", "conflict:OV-040"]
    vals = {k: sorted(v["value"] for v in c["values"]) for k, c in conflicts.items()}
    assert vals == {"conflict:OV-036": [3.0, 5.0], "conflict:OV-038": [12.0, 14.0, 14.0],
                    "conflict:OV-040": [3.5, 4.0]}
    assert all(c["status"] == "UNRESOLVED_SOURCE_CONFLICT" for c in conflicts.values())
    assert conflicts["conflict:OV-036"]["overlay_ids"] == ["OV-036", "OV-037"]
    q = by_id(load(built, "qualifications.json"))["qual:AMH/Q2301"]
    assert q["credits"]["conflict_id"] == "conflict:OV-038"
    n2302 = next(m for m in q["nos_memberships"] if m["nos_id"] == "nos:AMH/N2302")
    assert n2302["credits"]["conflict_id"] == "conflict:OV-036" and n2302["credits"]["value"] == 3.0
    dgt = next(m for m in q["nos_memberships"] if m["nos_id"] == "nos:DGT/VSQ/N0102")
    assert dgt["nsqf_level"]["conflict_id"] == "conflict:OV-040" and dgt["nsqf_level"]["engine_use"] == "DISPLAY_ONLY"
    assert {"OV-036", "OV-037", "OV-038", "OV-039", "OV-040"} == {
        o for o, e in built.manifest["overlay_effects"].items() if e["effect"] == "CONFLICT_REGISTERED"}


def test_dq03_is_a_flag_and_an_open_lead_not_a_conflict(built):
    q = by_id(load(built, "qualifications.json"))["qual:AMH/Q2301"]
    flags = [f for f in q["quality_flags"] if f["code"] == "SOURCE_UNAVAILABLE"]
    assert len(flags) == 1 and flags[0]["refs"] == ["src:C3"]
    (lead,) = built.manifest["open_leads"]
    assert lead["id"] == "DQ-03" and lead["status"] == "UNRESOLVED_LEAD_SOURCE_UNAVAILABLE" and lead["source"] == "src:C3"
    assert not any("DQ-03" in json.dumps(c) for c in load(built, "conflicts.json"))
    assert {s["manifest_item_id"] for s in built.manifest["sources_unavailable"]} == {"C3", "C4", "D1", "D2"}


def test_nco_titles_are_present_only_when_verified(built):
    occ = by_id(load(built, "occupations.json"))
    ps = occ["nco:3122.3551"]
    assert ps["title"] is None and ps["title_verification"] == "NOT_FOUND" and ps["evidence_id"] is None
    assert occ["nco:7543.0301"]["title"] == "Measurement Checker"
    assert all(o["title_verification"] == "VERIFIED_IN_SOURCE" and o["evidence_id"] for k, o in occ.items() if k != "nco:3122.3551")
    q = by_id(load(built, "qualifications.json"))["qual:AMH/Q2101"]
    assert any(f["code"] == "NCO_TITLE_NOT_FOUND" and f["refs"] == ["nco:3122.3551"] for f in q["quality_flags"])


def test_dq05_alias_and_dq06_secondary_copy(built):
    q = by_id(load(built, "qualifications.json"))["qual:AMH/Q0103"]
    assert q["titles"]["qf"] == "Inline Checker - Sewing" and q["titles"]["qp"] == "Checker - Inline & Measurement"
    codes = [f["code"] for f in q["quality_flags"]]
    assert "TITLE_VARIANT" in codes and "SECONDARY_COPY_BINARY_DIFFERS" in codes
    src = by_id(load(built, "sources.json"))
    assert src["src:B2b"]["role"] == "SECONDARY" and src["src:B2"]["role"] == "PRIMARY"
    # the QP title is not confirmed against the PDF, so it has a caution flag and no OFFICIAL evidence record
    (flag,) = [f for f in q["quality_flags"] if f["code"] == "TITLE_VARIANT"]
    assert flag["refs"] == ["src:B1"] and flag["severity"] == "CAUTION" and "not independently verified" in flag["message"]
    assert not [e for e in load(built, "evidence.json") if e["method"] == "qp_cover_snippet"]


def test_catalogue_is_verified_against_a1_and_validation_json_is_not(built):
    m = built.manifest
    assert m["verified_derived_inputs"] == ["processed/acquisition_2026-10-30/approved_qualifications_parsed.csv"]
    assert m["unverified_inputs"] == ["raw/2026-10-30/VALIDATION.json"]
    methods = {e["method"] for e in load(built, "evidence.json") if e["source_id"] == "src:A1"}
    assert methods == {"html_table_parse_verified"}


def test_q2301_e1_row_level_use_is_not_safer_than_its_row_text(built):
    rows = by_id(load(built, "eligibility_source_rows.json"))
    e1 = rows["rule:AMH/Q2301/E1"]
    assert e1["engine_use"] == "UNKNOWN" and e1["raw_row_text"]["engine_use"] == "UNKNOWN"
    assert e1["raw_required_experience"]["engine_use"] == "SAFE_HARD_RULE"  # the cell keeps its own audit classification
    assert e1["raw_academic_or_skill"]["engine_use"] == "UNKNOWN" and e1["extraction_status"] == "PARSED_UNCERTAIN"
    assert [(h["overlay_id"], h["field"], h["engine_use"]) for h in e1["audit_hints"]] == [
        ("OV-001", "raw_required_experience", "SAFE_HARD_RULE")]
    assert [r["id"] for r in rows.values() if r["audit_hints"]] == ["rule:AMH/Q2301/E1"]  # no other row has one
    for r in rows.values():
        comp = r["min_age"] if r["kind"] == "AGE_9C" else r["raw_row_text"]
        if r["engine_use"] not in ("UNKNOWN", "DISPLAY_ONLY", "NOT_USED"):
            assert comp["engine_use"] == r["engine_use"], r["id"]
    # unrelated rows keep the audit's row-level decisions
    assert rows["rule:AMH/Q0301/E1"]["engine_use"] == "SAFE_WITH_CONSTRAINT"
    assert rows["rule:AMH/Q2301/AGE"]["engine_use"] == "SAFE_HARD_RULE"
    assert rows["rule:AMH/Q2301/E7"]["engine_use"] == "CONDITIONAL_ON_DECLARED_RELEVANCE"


def test_status_upgrades_carry_the_overlays_own_confirmation_evidence(built):
    ov = {o.overlay_id: o for o in load_overlay(OVERLAY)}
    ev = by_id(load(built, "evidence.json"))
    upgraded = [i for i, o in ov.items() if o.status.value in ("CONFIRMED_BY_GEOMETRY", "CORROBORATED")]
    assert len(upgraded) == 12
    found = {}
    for e in ev.values():
        for oid in e["overlay_ids"]:
            if oid in upgraded and e["value_status"] in ("CONFIRMED_BY_GEOMETRY", "CORROBORATED"):
                found[oid] = e
    assert sorted(found) == sorted(upgraded)
    for oid, e in found.items():
        assert e["method"] == ov[oid].method and e["location"] == ov[oid].evidence_location, oid
        assert e["page"] == ov[oid].evidence_page and e["method"] != "pdfplumber_words", oid


def test_ov033_is_recorded_only(built):
    assert built.manifest["overlay_effects"]["OV-033"] == {"classification": "IGNORE", "effect": "NO_RELATIONSHIP_ASSERTED"}
    claims = by_id(load(built, "qualifications.json"))["qual:AMH/Q0301"]["progression_claims"]
    assert {c["id"] for c in claims} == {"claim:AMH/Q0301/P1", "claim:AMH/Q0301/P2"}
    assert all(c["resolved_target"] is None and c["engine_use"] == "DISPLAY_ONLY" for c in claims)


def test_non_ascii_catalogue_title_is_preserved_and_flagged(built):
    quals = load(built, "qualifications.json")
    only = [q for q in quals if q["coverage"] == "CATALOGUE_ONLY"]
    assert len(only) == 33
    (bad,) = [q for q in only if any(ord(c) > 127 for c in q["titles"]["catalogue"])]
    assert bad["code"] == "AMH/Q0911" and bad["titles"]["catalogue"] == "Merchandiser – Apparel, Made-Ups & Home Furnishings"
    flag = next(f for f in bad["quality_flags"] if "U+2013" in f["message"])
    assert "as printed in A1" in flag["message"] and "artifact" not in flag["message"]  # an en dash in A1 itself
    assert "–".encode() in (built.path / "qualifications.json").read_bytes()  # UTF-8, not escaped or "fixed"


def test_no_pii_in_curated_output(built):
    text = Path(REPO / "data_extraction" / "test_reconcile_2026-10-30.py").read_text(encoding="utf-8")
    block = re.search(r"^PII = \[(.*?)^\]", text, re.S | re.M).group(1)
    patterns = [eval(line.strip().rstrip(","), {"re": re}) for line in block.splitlines() if line.strip().startswith("re.compile")]
    assert len(patterns) == 3
    for p in sorted(built.path.glob("*.json")):
        # Hash and identifier hex runs (SHA-256, ev:/cb- ids) can contain ten digits by chance; they are not contact data.
        content = re.sub(r"[0-9a-f]{12,}", "", p.read_text(encoding="utf-8"))
        for rx in patterns:
            assert not rx.search(content), f"{p.name}: {rx.pattern}"


@pytest.mark.usefixtures("p14_only")  # an applied correction on an eligibility cell is fail-closed under P1.5-A2
def test_hypothetical_approval_of_ov002_and_ov034_in_memory_only(tmp_path):
    before = tree_hashes()
    r = run(tmp_path / "o", ["OV-002", "OV-034"], tmp_path)
    assert tree_hashes() == before  # the real approvals file and all data are untouched
    assert r.manifest["overlays"]["applied"] == ["OV-002", "OV-034"]
    assert r.manifest["overlays"]["pending"] == ["OV-003", "OV-004", "OV-035"]
    rows = by_id(load(r, "eligibility_source_rows.json"))
    e2 = rows["rule:AMH/Q2301/E2"]
    exp = e2["raw_required_experience"]
    assert (exp["value"], exp["source_value"], exp["value_status"]) == ("No Experience required", "", "CORRECTION_APPLIED")
    assert exp["engine_use"] == "UNKNOWN" and e2["engine_use"] == "UNKNOWN"
    assert e2["raw_academic_or_skill"]["value_status"] == "PARSED_UNCERTAIN" and e2["extraction_status"] == "PARSED_UNCERTAIN"
    assert rows["rule:AMH/Q2301/E3"]["raw_required_experience"]["value"] == ""
    ev = by_id(load(r, "evidence.json"))
    new, old = ev[exp["evidence_id"]], ev[exp["source_evidence_id"]]
    assert new["source_id"] == old["source_id"] == "src:A5" and new["page"] == "3"
    assert new["overlay_ids"] == ["OV-002"] and new["id"] != old["id"]
    smo = by_id(load(r, "qualifications.json"))["qual:AMH/Q0301"]
    (g,) = smo["credit_groups"]
    assert g["member_s_nos"] == [1, 2] and g["credits"]["value"] == 4.0 and g["credits"]["value_status"] == "PARSED_UNCERTAIN"
    members = {m["s_no"]: m["credits"]["value"] for m in smo["nos_memberships"][:2]}
    assert members == {1: None, 2: 4.0}
    ssmo = by_id(load(r, "qualifications.json"))["qual:AMH/Q2301"]
    assert ssmo["credit_groups"] == []  # OV-035 is still pending


@pytest.mark.usefixtures("p14_only")
def test_approving_all_three_corrections_and_both_groups(tmp_path):
    r = run(tmp_path / "o", ["OV-002", "OV-003", "OV-004", "OV-034", "OV-035"], tmp_path)
    assert r.manifest["overlays"]["pending"] == [] and len(r.manifest["overlays"]["applied"]) == 5
    rows = load(r, "eligibility_source_rows.json")
    for row in rows:
        for fld in ("raw_academic_or_skill", "raw_required_experience", "raw_row_text"):
            v = row.get(fld)
            if v and row["id"] in {f"rule:AMH/Q2301/E{n}" for n in (2, 3, 4)}:
                assert v["engine_use"] == "UNKNOWN"  # an approval never makes anything safe
    assert all(len(q["credit_groups"]) == 1 for q in load(r, "qualifications.json") if q["code"] in ("AMH/Q0301", "AMH/Q2301"))


def test_engine_use_is_never_raised_by_curation(built):
    plan = load_plan(OVERLAY, REPO / APPROVALS_PATH)
    allowed = {c.row.engine_use.value for c in plan.rows}
    cfg = yaml.safe_load((REPO / DEFAULTS_PATH).read_text(encoding="utf-8"))
    allowed |= {d["engine_use"] for d in cfg["engine_use_defaults"]}
    for r in load(built, "eligibility_source_rows.json"):
        assert r["engine_use"] in allowed | {"UNKNOWN"}
        for fld in ("raw_academic_or_skill", "raw_required_experience", "raw_row_text", "min_age"):
            v = r.get(fld)
            if v and v["engine_use"] in SAFE:
                assert v["engine_use"] in {c.row.engine_use.value for c in plan.rows}, (r["id"], fld)


def test_two_builds_have_the_same_id_and_identical_json(built, tmp_path):
    second = run(tmp_path / "again")
    assert second.data_build_id == built.data_build_id
    for p in sorted(built.path.glob("*.json")):
        if p.name != "build_manifest.json":
            assert p.read_bytes() == (second.path / p.name).read_bytes(), p.name
    assert json.loads((built.path / "build_manifest.json").read_text())["data_build_id"] == built.data_build_id


def test_curated_output_roundtrips_through_the_models(built):
    from skillgraph.model.conflict import Conflict
    from skillgraph.model.eligibility import EligibilitySourceRow
    from skillgraph.model.evidence import Evidence
    from skillgraph.model.occupation import Occupation
    from skillgraph.model.qualification import NosUnit, Qualification
    from skillgraph.model.source import SourceDocument

    for name, model in (("qualifications.json", Qualification), ("nos_units.json", NosUnit),
                        ("occupations.json", Occupation), ("sources.json", SourceDocument), ("evidence.json", Evidence),
                        ("conflicts.json", Conflict), ("eligibility_source_rows.json", EligibilitySourceRow)):
        for item in load(built, name):
            assert json.loads(model.model_validate(item).model_dump_json()) == item


def test_engine_constraints_reach_the_curated_rows_verbatim(built):
    plan = {c.row.overlay_id: c.row for c in load_plan(OVERLAY, REPO / APPROVALS_PATH).rows}
    rows = load(built, "eligibility_source_rows.json")
    with_wording = {r["id"]: r["engine_constraint"] for r in rows if r["engine_constraint"]}
    assert len(rows) == 28
    for r in rows:
        own = "min_age" if r["kind"] == "AGE_9C" else "raw_row_text"
        decided = [plan[o] for o in r["overlay_ids"]
                   if plan[o].target_field == own and plan[o].engine_constraint.strip() and o not in {"OV-002", "OV-003", "OV-004"}]
        assert r["engine_constraint"] == (decided[0].engine_constraint if decided else None), r["id"]
    assert with_wording["rule:AMH/Q0301/E1"] == plan["OV-005"].engine_constraint  # SAFE_WITH_CONSTRAINT keeps its wording
    assert all(r["engine_constraint"] for r in rows if r["engine_use"] == "SAFE_WITH_CONSTRAINT")
    assert all(r["engine_constraint"] for r in rows if r["engine_use"] not in ("UNKNOWN",) and r["engine_use"] != "DISPLAY_ONLY")
    # Q2301/E1: whole row stays UNKNOWN with no row wording; the experience-cell wording is only an audit hint
    e1 = next(r for r in rows if r["id"] == "rule:AMH/Q2301/E1")
    assert e1["engine_use"] == "UNKNOWN" and e1["engine_constraint"] is None
    assert e1["audit_hints"][0]["engine_constraint"] == plan["OV-001"].engine_constraint


def test_curated_rows_round_trip_with_constraints(built):
    from skillgraph.model.eligibility import EligibilitySourceRow

    for item in load(built, "eligibility_source_rows.json"):
        m = EligibilitySourceRow.model_validate(item)
        assert json.loads(m.model_dump_json()) == item
