"""P3.1 registry: indexing, lookups, duplicates, immutability and determinism on in-memory synthetic records.

No file is read. Codes are TEST/…; nothing here is a real source value. File loading and build refusal are in
``tests/integration/test_registry_load.py``.
"""

import random

import pytest
from model_factory import catalogue_only, curated, membership, module, official

from skillgraph.model.conflict import Conflict
from skillgraph.model.ids import slug_of
from skillgraph.model.occupation import Occupation
from skillgraph.model.qualification import NosUnit, Qualification
from skillgraph.registry import BuildInvalidError, Registry, RegistryError, UnknownEntityError

NOS_SHARED = "nos:TEST/N9001"
NOS_ONLY_B = "nos:TEST/N9002"
NOS_UNUSED = "nos:TEST/N9003"


def qual(n: int, nos: tuple[str, ...] = (NOS_SHARED,)) -> Qualification:
    """Curated qualification TEST/Q900<n> whose NOS table lists ``nos``; eligibility omitted (allowed for CURATED)."""
    code, qid = f"TEST/Q900{n}", f"qual:TEST/Q900{n}"
    mods = [{**module(), "id": f"mod:{code}/S1", "qualification_id": qid}]
    members = [membership(nos_id=None, module_id=f"mod:{code}/S1", s_no=1, version=None, is_bridge=True,
                          qualification_id=qid)]
    members += [membership(nos_id=x, s_no=2 + i, qualification_id=qid) for i, x in enumerate(nos)]
    return Qualification.model_validate(curated(id=qid, code=code, slug=slug_of(qid), nos_memberships=members,
                                                modules=mods, eligibility=None))


def nos_unit(nos_id: str, *users: str) -> NosUnit:
    return NosUnit.model_validate({"id": nos_id, "code": nos_id[4:], "titles_by_source": {u: "Title" for u in users}})


def catalogue(n: int) -> Qualification:
    qid = f"qual:TEST/Q91{n:02d}"
    return Qualification.model_validate(catalogue_only(id=qid, code=qid[5:], slug=slug_of(qid), nqr_code=f"QG-{n}"))


def occupation(code: str = "8153.0101") -> Occupation:
    return Occupation.model_validate({"id": f"nco:{code}", "nco_code": code, "title_verification": "NOT_CHECKED"})


@pytest.fixture
def records():
    return {
        "qualifications": [qual(1, (NOS_SHARED,)), qual(2, (NOS_SHARED, NOS_ONLY_B)), catalogue(1)],
        "nos_units": [nos_unit(NOS_SHARED, "qual:TEST/Q9001", "qual:TEST/Q9002"), nos_unit(NOS_ONLY_B, "qual:TEST/Q9002"),
                      nos_unit(NOS_UNUSED, "qual:TEST/Q9002")],
        "occupations": [occupation()],
    }


@pytest.fixture
def reg(records) -> Registry:
    return Registry.from_records(**records)


# ---- identifier lookups -----------------------------------------------------------------------------------------------


def test_qualification_lookups_by_id_code_and_slug_agree(reg):
    for q in reg.qualifications():
        a, b, c = (reg.qualification_by_id(q.id), reg.qualification_by_code(q.code), reg.qualification_by_slug(q.slug))
        assert a == b == c == q
    assert reg.qualification_by_code("TEST/Q9001").slug == "TEST.Q9001"


def test_nos_lookups_by_id_code_and_slug_agree(reg):
    for n in reg.nos_units():
        assert reg.nos_by_id(n.id) == reg.nos_by_code(n.code) == reg.nos_by_slug(slug_of(n.id)) == n
    assert reg.nos_by_slug("TEST.N9001").id == NOS_SHARED


def test_occupation_lookups_by_id_and_nco_code_agree(reg):
    assert reg.occupation_by_id("nco:8153.0101") == reg.occupation_by_nco_code("8153.0101")


def test_catalogue_only_qualifications_are_indexed_like_curated_ones(reg):
    q = reg.qualification_by_code("TEST/Q9101")
    assert q.coverage.value == "CATALOGUE_ONLY" and reg.qualification_by_slug("TEST.Q9101") == q


@pytest.mark.parametrize("call", [
    lambda r: r.qualification_by_id("qual:TEST/Q0000"),
    lambda r: r.qualification_by_code("TEST/Q0000"),
    lambda r: r.qualification_by_slug("TEST.Q0000"),
    lambda r: r.nos_by_id("nos:TEST/N0000"),
    lambda r: r.nos_by_code("TEST/N0000"),
    lambda r: r.nos_by_slug("TEST.N0000"),
    lambda r: r.occupation_by_id("nco:0000.0000"),
    lambda r: r.occupation_by_nco_code("0000.0000"),
    lambda r: r.evidence_by_id("ev:0000000000000000"),
    lambda r: r.source_by_id("src:NONE"),
    lambda r: r.conflict_by_id("conflict:OV-999"),
    lambda r: r.qualification_ids_with_nos("nos:TEST/N0000"),
    lambda r: r.eligibility_source_rows("qual:TEST/Q0000"),
])
def test_unknown_key_raises_typed_error(reg, call):
    with pytest.raises(UnknownEntityError) as exc:
        call(reg)
    assert isinstance(exc.value, RegistryError) and isinstance(exc.value, LookupError)


def test_lookups_are_exact_and_the_slug_is_not_a_code(reg):
    for wrong in (reg.qualification_by_code, reg.qualification_by_slug):
        for key in ("test/q9001", " TEST/Q9001", "TEST/Q9001 ", ""):
            with pytest.raises(UnknownEntityError):
                wrong(key)
    with pytest.raises(UnknownEntityError):
        reg.qualification_by_code("TEST.Q9001")  # slug in the code index
    with pytest.raises(UnknownEntityError):
        reg.qualification_by_slug("TEST/Q9001")  # code in the slug index
    with pytest.raises(UnknownEntityError):
        reg.qualification_by_id(["unhashable"])  # type: ignore[arg-type]


# ---- NOS lookup --------------------------------------------------------------------------------------------------------


def test_a_shared_nos_unit_returns_every_qualification_that_lists_it_ascending(reg):
    assert reg.qualification_ids_with_nos(NOS_SHARED) == ("qual:TEST/Q9001", "qual:TEST/Q9002")
    assert [q.id for q in reg.qualifications_with_nos(NOS_SHARED)] == ["qual:TEST/Q9001", "qual:TEST/Q9002"]


def test_a_nos_unit_listed_by_one_qualification_returns_only_it(reg):
    assert reg.qualification_ids_with_nos(NOS_ONLY_B) == ("qual:TEST/Q9002",)


def test_a_known_nos_unit_listed_by_nobody_returns_empty_not_an_error(reg):
    assert reg.qualification_ids_with_nos(NOS_UNUSED) == ()


def test_bridge_modules_are_not_nos_units(reg):
    users = {q for n in reg.nos_units() for q in reg.qualification_ids_with_nos(n.id)}
    assert users == {"qual:TEST/Q9001", "qual:TEST/Q9002"}
    with pytest.raises(UnknownEntityError):
        reg.qualification_ids_with_nos("mod:TEST/Q9001/S1")


# ---- duplicates and broken references ---------------------------------------------------------------------------------


def test_duplicate_qualification_id_makes_the_build_invalid(records):
    records["qualifications"].append(qual(1))
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records)
    assert exc.value.build_status == "INVALID" and any("duplicate qualification id" in p for p in exc.value.problems)


def test_duplicate_nos_and_occupation_ids_are_reported_together(records):
    records["nos_units"].append(nos_unit(NOS_SHARED, "qual:TEST/Q9001"))
    records["occupations"].append(occupation())
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records)
    text = " | ".join(exc.value.problems)
    assert "duplicate NOS id" in text and "duplicate occupation id" in text


def test_two_ids_with_one_slug_are_a_collision_not_a_silent_choice(records):
    other = records["qualifications"][0].model_copy(update={"id": "qual:TEST/Q9005", "code": "TEST/Q9005"})
    records["qualifications"].append(other)  # keeps slug TEST.Q9001 (the models forbid this; model_copy skips them)
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records)
    assert any("slug" in p and "TEST.Q9001" in p for p in exc.value.problems)


def test_two_ids_with_one_code_are_reported(records):
    other = records["qualifications"][0].model_copy(update={"id": "qual:TEST/Q9005", "slug": "TEST.Q9005"})
    records["qualifications"].append(other)
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records)
    assert any("duplicate qualification code: TEST/Q9001" in p for p in exc.value.problems)


def test_a_nos_table_entry_with_no_nos_unit_is_refused(records):
    records["nos_units"] = records["nos_units"][1:]  # drop the shared unit that both qualifications list
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records)
    assert any("unknown nos:TEST/N9001" in p for p in exc.value.problems)


def test_a_conflict_about_an_unknown_qualification_is_refused(records):
    c = Conflict.model_validate({
        "id": "conflict:OV-001", "subject": {"entity_id": "qual:TEST/Q0000", "field": "credits"},
        "values": [{"value": 1, "evidence_id": "ev:0000000000000001"}, {"value": 2, "evidence_id": "ev:0000000000000002"}],
        "status": "UNRESOLVED_SOURCE_CONFLICT", "overlay_ids": ["OV-001"], "engine_effect": "NOT_USED"})
    with pytest.raises(BuildInvalidError) as exc:
        Registry.from_records(**records, conflicts=[c])
    assert any("unknown subject qual:TEST/Q0000" in p for p in exc.value.problems)


def test_records_of_the_wrong_type_are_a_programming_error(records):
    with pytest.raises(TypeError):
        Registry.from_records(qualifications=[records["nos_units"][0]])


def test_an_empty_registry_is_valid_and_answers_every_lookup_with_unknown():
    r = Registry.from_records()
    assert r.qualifications() == () and r.build is None and r.manifest() == {}
    with pytest.raises(UnknownEntityError):
        r.qualification_by_code("TEST/Q9001")


# ---- immutability ------------------------------------------------------------------------------------------------------


def test_the_registry_rejects_assignment_deletion_and_direct_construction(reg):
    with pytest.raises(AttributeError):
        reg.anything = 1
    with pytest.raises(AttributeError):
        reg._qual = {}
    with pytest.raises(AttributeError):
        del reg._qual
    with pytest.raises(TypeError):
        Registry()


def test_the_public_surface_has_no_mutator():
    banned = ("set", "add", "remove", "update", "delete", "clear", "put", "pop", "append", "insert")
    public = [n for n in dir(Registry) if not n.startswith("_")]
    assert public and not [n for n in public if n.split("_")[0] in banned]


def test_mutating_a_returned_record_never_changes_the_registry(reg):
    before = reg.qualification_by_code("TEST/Q9002").model_dump(mode="json")
    q = reg.qualification_by_code("TEST/Q9002")
    q.nos_memberships.clear()  # a frozen model still holds a mutable list
    q.modules.append(q.modules[0])
    q.version_info["x"] = None
    for lst in (reg.qualifications(), reg.qualifications_with_nos(NOS_SHARED)):
        for item in lst:
            item.nos_memberships.clear()
    n = reg.nos_by_id(NOS_SHARED)
    n.titles_by_source.clear()
    assert reg.qualification_by_code("TEST/Q9002").model_dump(mode="json") == before
    assert reg.nos_by_id(NOS_SHARED).titles_by_source
    assert reg.qualification_ids_with_nos(NOS_SHARED) == ("qual:TEST/Q9001", "qual:TEST/Q9002")


def test_every_access_returns_a_distinct_object(reg):
    assert reg.qualification_by_code("TEST/Q9001") is not reg.qualification_by_code("TEST/Q9001")
    assert reg.qualifications()[0] is not reg.qualifications()[0]


def test_mutating_the_input_after_construction_never_changes_the_registry(records):
    r = Registry.from_records(**records)
    snapshot = [q.model_dump(mode="json") for q in r.qualifications()]
    for q in records["qualifications"]:
        q.nos_memberships.clear()
    records["qualifications"].clear()
    records["nos_units"][0].titles_by_source.clear()
    assert [q.model_dump(mode="json") for q in r.qualifications()] == snapshot
    assert r.nos_by_id(NOS_SHARED).titles_by_source


def test_collections_are_tuples_not_lists(reg):
    assert all(isinstance(x, tuple) for x in (reg.qualifications(), reg.nos_units(), reg.occupations(), reg.sources(),
                                              reg.conflicts(), reg.qualification_ids(),
                                              reg.qualification_ids_with_nos(NOS_SHARED)))


def test_manifest_is_a_copy():
    r = Registry.from_records(manifest={"a": {"b": [1]}})
    r.manifest()["a"]["b"].append(2)
    assert r.manifest() == {"a": {"b": [1]}}


# ---- deterministic indexing -------------------------------------------------------------------------------------------


def _fingerprint(r: Registry):
    return (
        [q.model_dump(mode="json") for q in r.qualifications()],
        [n.model_dump(mode="json") for n in r.nos_units()],
        [o.model_dump(mode="json") for o in r.occupations()],
        {n.id: r.qualification_ids_with_nos(n.id) for n in r.nos_units()},
    )


def test_input_order_never_changes_any_result(records):
    base = _fingerprint(Registry.from_records(**records))
    for seed in range(5):
        shuffled = {k: random.Random(seed).sample(v, len(v)) for k, v in records.items()}
        assert _fingerprint(Registry.from_records(**shuffled)) == base


def test_listings_are_ascending_by_id(reg):
    ids = [q.id for q in reg.qualifications()]
    assert ids == sorted(ids) == list(reg.qualification_ids())
    assert [n.id for n in reg.nos_units()] == sorted(n.id for n in reg.nos_units())


def test_two_registries_from_the_same_records_are_equivalent(records):
    assert _fingerprint(Registry.from_records(**records)) == _fingerprint(Registry.from_records(**records))


def test_official_values_are_passed_through_unchanged(reg):
    q = reg.qualification_by_code("TEST/Q9001")
    assert q.nsqf_level.value == official(2.5)["value"] and q.credits.engine_use.value == "NOT_USED"
