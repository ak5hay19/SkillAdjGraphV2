"""O-5a golden tests: official hours on the paths of the REAL curated build (skipped when absent).

The expected hours are the figures documented independently in ARCHITECTURE §8.4 (QF item 13, as recorded in the existing
extraction artifacts), written out here by hand and never read from the code under test:

====================  ======  =========  =========  ===========
qualification         theory  practical  OJT mand.  total
====================  ======  =========  =========  ===========
AMH/Q0301 (SMO)         90       210         0         300
AMH/Q2301 (SSMO)       150       270         0         420
AMH/Q0103 (IC)         150       240        30         420
AMH/Q2101 (PS)         180       330        60         570
====================  ======  =========  =========  ===========

What these tests do and do not prove. Each hours value cites an evidence id; the tests check that every id resolves through
``registry.evidence_by_id`` to an ``OFFICIAL`` record with a source, a source hash that equals the registered source document's hash
and a page or location. That shows the provenance LINKAGE. It does not prove that the cited document contains the number: the
number is checked against the independently documented figures above, and the page/location is compared with what the build
recorded, not re-read from the PDF. Nothing here is a claim about employment, equivalence, exemption, RPL or a reduced route.

``ojt_recommended`` is not listed in ARCHITECTURE §8.4, so only its provenance is checked, not its value.
"""

import itertools

import pytest
from test_graph_paths_pilot import IC, PILOTS, PS, SMO, SSMO, P, _registry, limits, paths, reg  # noqa: F401

from skillgraph.eligibility.evaluate import ProfileState
from skillgraph.graph import RawPath
from skillgraph.model.evidence import EngineUse, EvidenceClass, ValueStatus
from skillgraph.registry import Registry

FIELDS = ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total")
DOCUMENTED = {  # ARCHITECTURE §8.4: theory / practical / OJT mandatory / total
    SMO: (90.0, 210.0, 0.0, 300.0),
    SSMO: (150.0, 270.0, 0.0, 420.0),
    IC: (150.0, 240.0, 30.0, 420.0),
    PS: (180.0, 330.0, 60.0, 570.0),
}
TOTAL = {c: v[3] for c, v in DOCUMENTED.items()}


def all_paths(reg, limits, max_steps=3):
    return paths(reg, limits, ProfileState(), max_steps=max_steps, match=None)  # nothing can be NOT_MET: every pilot enters


def single(reg, limits, code) -> RawPath:
    (p,) = [p for p in all_paths(reg, limits, 1) if p.target_codes == (code,)]
    return p


def copy_with(reg: Registry, **per_qual) -> Registry:
    """A copy of the real registry whose qualifications are changed by ``per_qual`` (a function of the Qualification returning
    the update dict); everything else is carried over. The real registry and the build on disk are never touched."""
    quals = []
    for q in reg.qualifications():
        update = per_qual["update"](q)
        quals.append(q.model_copy(update=update) if update else q)
    return Registry.from_records(
        qualifications=quals, nos_units=reg.nos_units(), occupations=reg.occupations(), sources=reg.sources(),
        conflicts=reg.conflicts(),
        eligibility_source_rows=[r for q in reg.qualifications() for r in reg.eligibility_source_rows(q.id)])


# ---- the documented figures -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", PILOTS)
def test_the_hours_on_a_single_step_path_are_the_documented_figures(reg, limits, code):
    h = single(reg, limits, code).steps[0].official_hours
    theory, practical, ojt, total = DOCUMENTED[code]
    assert (h.theory.value, h.practical.value, h.ojt_mandatory.value, h.total.value) == (theory, practical, ojt, total)
    assert h.ojt_recommended is not None and h.is_complete


@pytest.mark.parametrize("code", PILOTS)
def test_the_step_hours_are_exactly_the_registrys_breakdown_for_that_qualification(reg, limits, code):
    step = single(reg, limits, code).steps[0]
    assert step.target_code == code
    assert step.official_hours == reg.qualification_by_code(code).hours  # all five values and every piece of metadata


@pytest.mark.parametrize("code", PILOTS)
def test_every_one_of_the_five_values_has_resolvable_official_provenance_and_no_open_conflict(reg, limits, code):
    h = single(reg, limits, code).steps[0].official_hours
    ids = []
    for f in FIELDS:
        v = getattr(h, f)
        assert v.evidence_class is EvidenceClass.OFFICIAL
        assert v.value_status is ValueStatus.TRANSCRIBED and v.engine_use is EngineUse.SAFE_HOURS
        assert v.conflict_id is None  # none of the pilot hours is in a recorded conflict; DQ-01 concerns credits, not hours
        e = reg.evidence_by_id(v.evidence_id)
        assert e.evidence_class is EvidenceClass.OFFICIAL
        src = reg.source_by_id(e.source_id)
        assert e.source_sha256 == src.sha256 and e.source_sha256
        assert e.page or e.location
        ids.append(v.evidence_id)
    assert len(ids) == 5 and all(ids)  # five values, five evidence ids retained on the step (the API picks none: O-5b)


def test_hours_evidence_comes_from_the_qualifications_own_sources_not_from_a_credit_or_other_record(reg, limits):
    for code in PILOTS:
        h = single(reg, limits, code).steps[0].official_hours
        q = reg.qualification_by_code(code)
        assert h.total.evidence_id != q.credits.evidence_id  # credits cite their own evidence and are NOT_USED
        assert q.credits.engine_use is EngineUse.NOT_USED


# ---- path totals ----------------------------------------------------------------------------------------------------------------


def test_the_total_of_every_path_of_up_to_four_steps_is_the_sum_of_the_documented_totals(reg, limits):
    got = all_paths(reg, limits, 4)
    assert len(got) == 4 + 12 + 24 + 24 == 64
    for p in got:
        assert p.official_hours_total == sum(TOTAL[c] for c in p.target_codes)
    by = {p.target_codes: p.official_hours_total for p in got}
    assert by[(SMO,)] == 300.0 and by[(PS,)] == 570.0
    assert by[(SMO, SSMO)] == 720.0 and by[(SSMO, SMO)] == 720.0
    assert by[(SMO, SSMO, PS)] == 1290.0
    assert by[tuple(sorted(PILOTS))] == 300.0 + 420.0 + 420.0 + 570.0 == 1710.0


def test_the_path_total_does_not_depend_on_the_order_of_the_steps(reg, limits):
    by = {p.target_codes: p.official_hours_total for p in all_paths(reg, limits, 4) if len(p.steps) == 4}
    assert len(by) == 24 and set(by.values()) == {1710.0}
    for perm in itertools.permutations(PILOTS):
        assert by[perm] == 1710.0


def test_a_real_profile_gives_the_same_totals_as_the_documented_sum(reg, limits):
    state = P(age=24, grade=10, creds=[], held=[SMO], ext=())
    got = paths(reg, limits, state, max_steps=2)
    assert got and all(SMO not in p.target_codes for p in got)  # a held qualification is never a step, so never in the total
    for p in got:
        assert p.official_hours_total == sum(TOTAL[c] for c in p.target_codes)


def test_real_paths_serialise_and_deserialise_and_a_wrong_total_is_rejected(reg, limits):
    from pydantic import ValidationError

    for p in all_paths(reg, limits, 3)[:12]:
        assert RawPath.model_validate_json(p.model_dump_json()) == p
        with pytest.raises(ValidationError, match="sum of the steps"):
            RawPath(path_id=p.path_id, steps=p.steps, verdict=p.verdict, official_hours_total=p.official_hours_total + 1)


# ---- regression protection ------------------------------------------------------------------------------------------------------


def test_changing_credits_in_a_copied_real_registry_changes_neither_hours_nor_totals_ids_verdicts_or_order(reg, limits):
    mutated = copy_with(reg, update=lambda q: {"credits": q.credits.model_copy(update={"value": 12345.0})})
    assert mutated.qualification_by_code(SMO).credits.value == 12345.0 != reg.qualification_by_code(SMO).credits.value
    before, after = all_paths(reg, limits, 4), all_paths(mutated, limits, 4)
    assert [p.model_dump_json() for p in after] == [p.model_dump_json() for p in before]


def test_credits_equal_to_a_total_are_still_not_hours(reg, limits):
    """The most tempting confusion: set every credit to its own total of hours. Nothing may move, and a hours value changed in
    another copy must move only the hours."""
    same = copy_with(reg, update=lambda q: {"credits": q.credits.model_copy(update={"value": q.hours.total.value})})
    assert [p.model_dump_json() for p in all_paths(same, limits, 3)] == [p.model_dump_json() for p in all_paths(reg, limits, 3)]


def test_changing_the_official_hours_changes_only_the_hours_never_ids_verdicts_order_or_membership(reg, limits):
    mutated = copy_with(reg, update=lambda q: (
        {"hours": q.hours.model_copy(update={"total": q.hours.total.model_copy(update={"value": q.hours.total.value + 1000.0})})}
        if q.coverage.value == "CURATED" else None))
    a, b = all_paths(reg, limits, 4), all_paths(mutated, limits, 4)
    assert [p.path_id for p in a] == [p.path_id for p in b]
    assert [p.target_codes for p in a] == [p.target_codes for p in b]
    assert [p.verdict for p in a] == [p.verdict for p in b]
    assert [[s.eligibility for s in p.steps] for p in a] == [[s.eligibility for s in p.steps] for p in b]
    assert all(pb.official_hours_total == pa.official_hours_total + 1000.0 * len(pa.steps) for pa, pb in zip(a, b, strict=True))


def test_enumeration_for_the_e07_profile_keeps_pre_order_and_unique_ids_with_the_new_data_attached(reg, limits):
    state = P(age=24, grade=10, creds=[], held=[SMO], ext=())
    got = paths(reg, limits, state, max_steps=3)
    codes = [p.target_codes for p in got]
    assert codes == sorted(codes) and len(codes) == len(set(codes))  # pre-order over ascending ids, no duplicate
    assert all(p.path_id.startswith("p-") and len(p.path_id) == 14 for p in got)
