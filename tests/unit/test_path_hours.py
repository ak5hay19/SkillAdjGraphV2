"""O-5a: official hours on ``RawStep`` and their sum on ``RawPath`` (ARCHITECTURE §12; TASKS P3.6 O-5). Synthetic fixtures only.

Expected values are written out by hand from the documented rule, never taken from the code under test:

* a step's hours are the target qualification's own ``HoursBreakdown`` (five values, each with its evidence id, status, engine
  use and conflict id), copied unchanged; the stored total is NOT recomputed from the parts (the fixtures make them disagree);
* the path total is the sum of the full official totals of the steps (§12), a ``RULE_DERIVED`` figure, never a stored fact;
* credits are never hours (decision D1) and nothing here ranks, decides eligibility or chooses an API evidence id (O-5b).
"""

import ast
import inspect
import json

import pytest
from model_factory import ev, official
from pydantic import ValidationError
from test_graph_paths import EVIDENCE, LIMITS, SRC, code, enum, make, occupations, profile, qual

import skillgraph.graph.paths as paths_module
from skillgraph.graph import GraphError, RawPath, RawStep
from skillgraph.model.evidence import EngineUse, EvidenceClass, ValueStatus
from skillgraph.model.qualification import HoursBreakdown, Qualification
from skillgraph.registry import Registry

FIELDS = ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total")
CONFLICT = "conflict:OV-036"


def hrs(values: tuple[float, float, float, float, float], base: int, **over) -> dict:
    """A hours dict whose five values cite five distinct evidence ids ``ev(base) .. ev(base + 4)``; ``over`` replaces one value."""
    d = {f: official(v, base + i, engine_use="SAFE_HOURS") for i, (f, v) in enumerate(zip(FIELDS, values, strict=True))}
    return {**d, **over}


# Totals deliberately differ from the sum of the parts (10 + 20 + 3 + 4 = 37 != 100, ...): the code must not recompute them.
H = {1: (10.0, 20.0, 3.0, 4.0, 100.0), 2: (50.0, 60.0, 5.0, 6.0, 250.0), 3: (7.0, 8.0, 0.0, 0.0, 75.5)}
BASE = {1: 1, 2: 6, 3: 11}  # evidence id offsets: qualification n cites ev(BASE[n]) .. ev(BASE[n] + 4)


def world3(overrides: dict | None = None) -> Registry:
    """Three CURATED records TEST/Q9001..3 (all entry rules MET for the standard profile); ``overrides[n]`` replaces its hours."""
    return make([qual(n, "M", hours=(overrides or {}).get(n, hrs(H[n], BASE[n]))) for n in (1, 2, 3)])


def with_total(n: int, **update) -> Registry:
    """A registry whose record n has its total changed WITHOUT revalidation (``model_copy`` skips the validators), to reach the
    states that a corrupted or hand-built object could be in."""
    records = []
    for k in (1, 2, 3):
        q = Qualification.model_validate(qual(k, "M", hours=hrs(H[k], BASE[k])))
        if k == n:
            q = q.model_copy(update={"hours": q.hours.model_copy(update={"total": q.hours.total.model_copy(update=update)})})
        records.append(q)
    return Registry.from_records(qualifications=records, occupations=occupations(), evidence=EVIDENCE)


# ---- provenance: each step copies the registry's own breakdown ------------------------------------------------------------------


def test_every_step_carries_the_target_qualifications_own_hours_breakdown_unchanged():
    reg = world3()
    got = enum(reg, max_steps=3)
    assert got
    for p in got:
        for s in p.steps:
            assert s.official_hours == reg.qualification_by_code(s.target_code).hours
            assert isinstance(s.official_hours, HoursBreakdown)  # the existing model, not a duplicate schema


def test_all_five_values_and_their_five_distinct_evidence_ids_are_preserved():
    reg = world3()
    (p,) = [p for p in enum(reg, max_steps=1) if p.target_codes == (code(2),)]
    h = p.steps[0].official_hours
    assert [getattr(h, f).value for f in FIELDS] == [50.0, 60.0, 5.0, 6.0, 250.0]  # as stored; the total is not 50+60+5+6
    assert [getattr(h, f).evidence_id for f in FIELDS] == [ev(n) for n in range(6, 11)]
    assert len({getattr(h, f).evidence_id for f in FIELDS}) == 5
    assert all(getattr(h, f).engine_use.value == "SAFE_HOURS" and getattr(h, f).value_status.value == "TRANSCRIBED" for f in FIELDS)


def test_every_evidence_id_resolves_to_an_official_evidence_record():
    reg = world3()
    for p in enum(reg, max_steps=3):
        for s in p.steps:
            for f in FIELDS:
                v = getattr(s.official_hours, f)
                assert v.evidence_class is EvidenceClass.OFFICIAL and v.evidence_id is not None
                assert reg.evidence_by_id(v.evidence_id).evidence_class is EvidenceClass.OFFICIAL


def test_value_status_engine_use_and_a_conflict_id_on_a_part_are_copied_not_resolved_or_stripped():
    d = hrs(H[2], BASE[2])
    d["ojt_recommended"] = official(6.0, 9, engine_use="UNKNOWN", status="PARSED_UNCERTAIN", conflict_id=CONFLICT)
    d["practical"] = official(60.0, 7, engine_use="SAFE_HOURS", status="CORROBORATED")
    reg = world3({2: d})
    (p,) = [p for p in enum(reg, max_steps=1) if p.target_codes == (code(2),)]
    h = p.steps[0].official_hours
    assert h.ojt_recommended.conflict_id == CONFLICT and h.ojt_recommended.value_status.value == "PARSED_UNCERTAIN"
    assert h.ojt_recommended.engine_use.value == "UNKNOWN" and h.ojt_recommended.value == 6.0  # not zeroed, not trusted
    assert h.practical.value_status.value == "CORROBORATED"
    assert h.total.conflict_id is None and h.total.value == 250.0
    assert h == reg.qualification_by_code(code(2)).hours


# ---- fail closed ----------------------------------------------------------------------------------------------------------------


UNUSABLE = [
    ({"value": None}, "absent"),
    ({"evidence_id": None}, "evidence id"),
    ({"conflict_id": CONFLICT, "engine_use": EngineUse.UNKNOWN}, "conflict"),
    ({"value_status": ValueStatus.UNRESOLVED}, "UNRESOLVED"),
    ({"value_status": ValueStatus.PARSED_UNCERTAIN}, "PARSED_UNCERTAIN"),
    ({"engine_use": EngineUse.DISPLAY_ONLY}, "DISPLAY_ONLY"),
    ({"engine_use": None}, "not SAFE_HOURS"),
]


@pytest.mark.parametrize(("update", "why"), UNUSABLE)
def test_an_unusable_total_raises_graph_error_and_is_never_zero_or_trusted(update, why):
    reg = with_total(2, **update)
    with pytest.raises(GraphError, match=why):
        enum(reg, max_steps=2)
    with pytest.raises(GraphError, match=code(2)):
        enum(reg, max_steps=1, target=code(1))  # the check is independent of the target and of the verdicts


@pytest.mark.parametrize(("update", "why"), UNUSABLE)
def test_a_step_with_an_unusable_total_cannot_be_constructed(update, why):
    p = enum(world3(), max_steps=1)[0]
    s = p.steps[0]
    bad = s.official_hours.model_copy(update={"total": s.official_hours.total.model_copy(update=update)})
    with pytest.raises(ValidationError, match=why):
        RawStep(index=1, from_state=s.from_state, target_code=s.target_code, eligibility=s.eligibility, official_hours=bad)


def test_the_hours_of_a_held_qualification_are_not_read_so_an_unusable_one_does_not_block_other_paths():
    reg = with_total(2, value=None)
    got = enum(reg, state=profile(held=(code(2),)), max_steps=2)
    assert got and all(code(2) not in p.target_codes for p in got)


def test_a_step_requires_the_official_hours_field():
    s = enum(world3(), max_steps=1)[0].steps[0]
    with pytest.raises(ValidationError):
        RawStep(index=1, from_state=s.from_state, target_code=s.target_code, eligibility=s.eligibility)  # type: ignore[call-arg]


# ---- the path total -------------------------------------------------------------------------------------------------------------


TOTALS = {code(1): 100.0, code(2): 250.0, code(3): 75.5}  # by hand, from H


def test_the_path_total_is_the_sum_of_the_step_totals_for_every_path():
    got = enum(world3(), max_steps=3)
    assert len(got) == 3 + 6 + 6
    for p in got:
        assert p.official_hours_total == sum(TOTALS[c] for c in p.target_codes)
        assert p.official_hours_total == sum(s.official_hours.total.value for s in p.steps)


def test_a_known_total_by_hand():
    by = {p.target_codes: p.official_hours_total for p in enum(world3(), max_steps=3)}
    assert by[(code(1),)] == 100.0 and by[(code(3),)] == 75.5
    assert by[(code(1), code(2))] == 350.0 and by[(code(2), code(1))] == 350.0  # order does not change a sum
    assert by[(code(1), code(2), code(3))] == 425.5


def test_the_total_is_the_full_official_total_whatever_the_credits():
    reg = world3()
    q = reg.qualification_by_code(code(2))
    assert q.credits.value != q.hours.total.value  # credits are a different quantity and are never read (D1)
    p = next(p for p in enum(reg, max_steps=1) if p.target_codes == (code(2),))
    assert p.official_hours_total == 250.0 == q.hours.total.value


def test_an_inconsistent_total_is_rejected_when_constructed():
    p = next(p for p in enum(world3(), max_steps=2) if len(p.steps) == 2)
    ok = p.official_hours_total
    RawPath(path_id=p.path_id, steps=p.steps, verdict=p.verdict, official_hours_total=ok)  # the consistent one is accepted
    for wrong in (ok + 1, ok - 1, 0.0, p.steps[0].official_hours.total.value, ok * 2):
        with pytest.raises(ValidationError, match="sum of the steps"):
            RawPath(path_id=p.path_id, steps=p.steps, verdict=p.verdict, official_hours_total=wrong)


def test_an_inconsistent_total_is_rejected_when_deserialised_and_the_good_one_round_trips():
    p = next(p for p in enum(world3(), max_steps=3) if len(p.steps) == 3)
    text = p.model_dump_json()
    assert RawPath.model_validate_json(text) == p
    assert RawPath.model_validate(json.loads(text)) == p
    data = json.loads(text)
    data["official_hours_total"] += 0.5
    with pytest.raises(ValidationError, match="sum of the steps"):
        RawPath.model_validate(data)
    with pytest.raises(ValidationError, match="sum of the steps"):
        RawPath.model_validate_json(json.dumps(data))
    data = json.loads(text)
    data["steps"][1]["official_hours"]["total"]["value"] += 1  # a step changed but the stored total left behind
    with pytest.raises(ValidationError, match="sum of the steps"):
        RawPath.model_validate(data)


def test_the_total_field_is_required_a_number_and_not_negative():
    p = enum(world3(), max_steps=1)[0]
    with pytest.raises(ValidationError):
        RawPath(path_id=p.path_id, steps=p.steps, verdict=p.verdict)  # type: ignore[call-arg]
    for bad in (None, "100", True, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            RawPath(path_id=p.path_id, steps=p.steps, verdict=p.verdict, official_hours_total=bad)  # type: ignore[arg-type]


def test_an_empty_path_is_still_refused_whatever_the_total():
    """No authoritative rule gives an empty path a total (API_SPEC §4 'min_length 1' stands), so none is invented: an empty
    path stays invalid, with a total of 0 or of anything else."""
    p = enum(world3(), max_steps=1)[0]
    for total in (0, 0.0, 1.0):
        with pytest.raises(ValidationError):
            RawPath(path_id=p.path_id, steps=(), verdict=p.verdict, official_hours_total=total)


def test_a_missing_total_value_is_an_error_in_the_sum_not_a_zero():
    p = enum(world3(), max_steps=1)[0]
    s = p.steps[0]
    hollow = s.official_hours.model_copy(update={"total": s.official_hours.total.model_copy(update={"value": None})})
    forced = s.model_copy(update={"official_hours": hollow})  # model_copy skips the validators
    with pytest.raises(ValueError, match="absent"):
        paths_module._sum_totals((forced,))


# ---- regression protection ------------------------------------------------------------------------------------------------------


def _mutate(*, credits=None, hours_total=None) -> Registry:
    records = []
    for k in (1, 2, 3):
        q = Qualification.model_validate(qual(k, "M", hours=hrs(H[k], BASE[k])))
        update = {}
        if credits is not None:
            update["credits"] = q.credits.model_copy(update={"value": credits})
        if hours_total is not None:
            update["hours"] = q.hours.model_copy(update={"total": q.hours.total.model_copy(update={"value": hours_total + k})})
        records.append(q.model_copy(update=update))
    return Registry.from_records(qualifications=records, occupations=occupations(), evidence=EVIDENCE)


def test_changing_qualification_credits_in_a_copied_registry_changes_no_hours():
    base = enum(world3(), max_steps=3)
    for value in (0.0, 4.0, 100.0, 250.0, 9999.0):  # includes values equal to real totals: credits are never hours (D1)
        got = enum(_mutate(credits=value), max_steps=3)
        assert [p.model_dump_json() for p in got] == [p.model_dump_json() for p in base]
        assert [p.official_hours_total for p in got] == [p.official_hours_total for p in base]


def test_the_hours_change_the_hours_and_nothing_else_ids_verdicts_order_and_membership_are_identical():
    a = enum(world3(), max_steps=3)
    b = enum(_mutate(hours_total=1000.0), max_steps=3)
    assert [p.path_id for p in a] == [p.path_id for p in b]  # the identity excludes hours (API_SPEC §4 A-6)
    assert [p.target_codes for p in a] == [p.target_codes for p in b]
    assert [p.verdict for p in a] == [p.verdict for p in b]
    assert [[(s.index, s.from_state, s.eligibility) for s in p.steps] for p in a] == [
        [(s.index, s.from_state, s.eligibility) for s in p.steps] for p in b]
    assert [p.official_hours_total for p in a] != [p.official_hours_total for p in b]  # and the hours did change
    assert [p.official_hours_total for p in b] == [sum(1000.0 + int(c[-1]) for c in p.target_codes) for p in b]


def test_enumeration_order_is_still_depth_first_pre_order_with_ascending_ids():
    got = enum(world3(), max_steps=3)
    digits_ = [tuple(int(c[-1]) for c in p.target_codes) for p in got]
    expected = []

    def walk(prefix):
        for n in (1, 2, 3):
            if n in prefix:
                continue
            new = (*prefix, n)
            expected.append(new)
            walk(new)

    walk(())
    assert digits_ == expected


def test_the_new_fields_are_exactly_the_two_documented_ones_and_no_later_stage_field_crept_in():
    assert set(RawStep.model_fields) == {"index", "from_state", "target_code", "eligibility", "official_hours"}
    assert set(RawPath.model_fields) == {"path_id", "steps", "verdict", "official_hours_total"}
    later = {"rank", "totals", "assumption_count", "quality_flag_count", "quality_flags", "shared_nos_with_held",
             "progression_claim", "evidence_classes_present", "is_hypothetical", "official_hours_evidence_id",
             "hypothetical_incremental_hours", "evidence_backed_incremental_hours", "sort_values", "explanation"}
    assert not later & (set(RawStep.model_fields) | set(RawPath.model_fields))


def test_the_module_still_reads_no_credit_and_imports_only_the_allowed_internal_packages():
    tree = ast.parse((SRC / "graph" / "paths.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree)
                                                                        if isinstance(n, ast.Attribute)}
    assert "credits" not in names and "credit_groups" not in names and "nos_memberships" not in names
    internal = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("skillgraph"):
            internal.add(n.module)
        assert not (isinstance(n, ast.ImportFrom) and n.level)  # no relative import
    assert internal == {"skillgraph.eligibility.evaluate", "skillgraph.eligibility.logic", "skillgraph.graph.edges",
                        "skillgraph.model.base", "skillgraph.model.eligibility", "skillgraph.model.evidence",
                        "skillgraph.model.ids", "skillgraph.model.qualification", "skillgraph.registry"}


def test_enumeration_arguments_and_limits_are_unchanged():
    # the signature of the public function is exactly what O-1/O-2/A-6 fixed; O-5a added no argument
    params = inspect.signature(paths_module.enumerate_paths).parameters
    assert list(params) == ["state", "registry", "config", "scenario", "max_steps", "target_code", "max_expansions",
                            "max_steps_limit", "profile_digest"]
    assert set(LIMITS) == {"max_expansions", "max_steps_limit", "profile_digest"}
