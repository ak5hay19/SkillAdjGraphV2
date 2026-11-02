"""P3.1 registry loader against installed curated builds.

Two sources: a synthetic build produced by the real builder (always runs; invalid variants are made by editing a
temporary copy and, where the test needs a later check to run, re-hashing the manifest) and the real installed build
(skips when absent; read-only). Nothing here writes into ``data/`` or touches ``config/``.
"""

import copy
import hashlib
import json
import shutil
import time
from pathlib import Path

import pytest
from synth_tree import Tree

from skillgraph.curation.build import MANIFEST_OUT, OUTPUT_FILES
from skillgraph.curation.config import CURATION_CODE_VERSION
from skillgraph.registry import (
    BuildInvalidError,
    BuildNotFoundError,
    Registry,
    RegistryError,
    UnknownEntityError,
    load,
)

REPO = Path(__file__).resolve().parents[2]


# ---- helpers ---------------------------------------------------------------------------------------------------------


def read(d: Path, name: str):
    return json.loads((d / name).read_text(encoding="utf-8"))


def rewrite(d: Path, name: str, data, *, counts: dict | None = None) -> None:
    """Replace one output file and keep the manifest's hash (and optionally counts) in step, so later checks run."""
    blob = json.dumps(data, sort_keys=True).encode("utf-8")
    (d / name).write_bytes(blob)
    m = read(d, MANIFEST_OUT)
    m["output_files"][name] = hashlib.sha256(blob).hexdigest()
    m["counts"].update(counts or {})
    (d / MANIFEST_OUT).write_text(json.dumps(m, sort_keys=True), encoding="utf-8")


def edit_manifest(d: Path, **changes) -> None:
    m = read(d, MANIFEST_OUT)
    m.update(changes)
    (d / MANIFEST_OUT).write_text(json.dumps(m, sort_keys=True), encoding="utf-8")


def refused(d: Path, needle: str) -> BuildInvalidError:
    with pytest.raises(BuildInvalidError) as exc:
        load(d)
    assert isinstance(exc.value, RegistryError) and exc.value.build_status == "INVALID"
    assert exc.value.problems and any(needle in p for p in exc.value.problems), exc.value.problems
    return exc.value


@pytest.fixture(scope="module")
def synthetic_build(tmp_path_factory) -> Path:
    return Tree(tmp_path_factory.mktemp("registry_synth")).build(approve=[]).path


@pytest.fixture
def build_copy(synthetic_build, tmp_path) -> Path:
    """A private copy that a test may damage; the directory name (the build id) is kept."""
    dest = tmp_path / synthetic_build.name
    shutil.copytree(synthetic_build, dest)
    return dest


# ---- a valid build -----------------------------------------------------------------------------------------------------


def test_a_valid_build_loads_and_describes_itself(synthetic_build):
    reg = load(synthetic_build)
    m = read(synthetic_build, MANIFEST_OUT)
    assert isinstance(reg, Registry) and reg.build.data_build_id == m["data_build_id"] == synthetic_build.name
    assert reg.build.status == "READY" and reg.build.curation_code_version == CURATION_CODE_VERSION
    assert reg.build.validation == "NOT_RUN" and dict(reg.build.counts) == m["counts"]
    assert reg.manifest() == m
    assert [q.id for q in reg.qualifications()] == sorted(q["id"] for q in read(synthetic_build, "qualifications.json"))


def test_load_accepts_a_string_path(synthetic_build):
    assert load(str(synthetic_build)).build.data_build_id == synthetic_build.name


def test_loading_twice_gives_equivalent_registries(synthetic_build):
    def snap(r):
        return ([q.model_dump(mode="json") for q in r.qualifications()], [n.model_dump(mode="json") for n in r.nos_units()],
                [c.model_dump(mode="json") for c in r.conflicts()], {n.id: r.qualification_ids_with_nos(n.id) for n in r.nos_units()})

    assert snap(load(synthetic_build)) == snap(load(synthetic_build))


def test_lookups_by_id_code_slug_and_nos_on_a_built_registry(synthetic_build):
    reg = load(synthetic_build)
    for q in reg.qualifications():
        assert reg.qualification_by_id(q.id) == reg.qualification_by_code(q.code) == reg.qualification_by_slug(q.slug)
    nos = reg.nos_units()
    assert nos and all(reg.nos_by_code(n.code) == reg.nos_by_slug(n.id[4:].replace("/", ".")) == n for n in nos)
    for n in nos:
        listed = {q.id for q in reg.qualifications() for m in q.nos_memberships if m.nos_id == n.id}
        assert set(reg.qualification_ids_with_nos(n.id)) == listed and listed
    assert reg.eligibility_source_rows("qual:TST/Q0001")
    assert all(r.qualification_id == "qual:TST/Q0001" for r in reg.eligibility_source_rows("qual:TST/Q0001"))
    with pytest.raises(UnknownEntityError):
        reg.qualification_by_code("TST/Q9999")


def test_loading_does_not_write_into_the_build(synthetic_build):
    def digest():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(synthetic_build.iterdir())}

    before = digest()
    load(synthetic_build)
    assert digest() == before


def test_a_registry_built_from_a_loaded_one_through_records_is_equivalent(synthetic_build):
    reg = load(synthetic_build)
    again = Registry.from_records(
        qualifications=reg.qualifications(), nos_units=reg.nos_units(), occupations=reg.occupations(),
        sources=reg.sources(), conflicts=reg.conflicts(),
        eligibility_source_rows=[r for q in reg.qualification_ids() for r in reg.eligibility_source_rows(q)],
        evidence=[reg.evidence_by_id(e) for e in read(synthetic_build, "evidence.json") for e in [e["id"]]],
    )
    assert [q.model_dump(mode="json") for q in again.qualifications()] == [q.model_dump(mode="json") for q in reg.qualifications()]


# ---- the validation report ----------------------------------------------------------------------------------------------


def report(d: Path, **kw):
    body = {"schema_version": 1, "data_build_id": d.name, "checks_passed": 18, "checks_failed": 0, **kw}
    (d / "validation_report.json").write_text(json.dumps(body), encoding="utf-8")


def test_a_clean_validation_report_is_reported_as_passed(build_copy):
    report(build_copy)
    assert load(build_copy).build.validation == "PASSED"


def test_a_validation_report_with_failed_checks_makes_the_build_invalid(build_copy):
    report(build_copy, checks_failed=2)
    refused(build_copy, "records 2 failed check")


def test_a_validation_report_for_another_build_is_refused(build_copy):
    report(build_copy, data_build_id="cb-000000000000")
    refused(build_copy, "belongs to another build")


@pytest.mark.parametrize("body", ["{not json", "[]", json.dumps({"data_build_id": "x"})])
def test_a_malformed_validation_report_is_refused(build_copy, body):
    (build_copy / "validation_report.json").write_text(body, encoding="utf-8")
    with pytest.raises(BuildInvalidError):
        load(build_copy)


def test_a_report_with_a_non_numeric_failed_count_is_refused(build_copy):
    report(build_copy, checks_failed="0")
    refused(build_copy, "checks_failed is not a number")


# ---- a missing build ---------------------------------------------------------------------------------------------------


def test_a_missing_directory_raises_build_not_found(tmp_path):
    with pytest.raises(BuildNotFoundError) as exc:
        load(tmp_path / "cb-000000000000")
    assert exc.value.build_status == "NOT_BUILT" and isinstance(exc.value, RegistryError)
    assert "does not exist" in str(exc.value)


def test_a_directory_without_a_manifest_raises_build_not_found(tmp_path):
    (tmp_path / "cb-000000000000").mkdir()
    with pytest.raises(BuildNotFoundError, match="build_manifest.json is missing"):
        load(tmp_path / "cb-000000000000")


def test_a_file_path_is_not_a_build(synthetic_build):
    with pytest.raises(BuildNotFoundError):
        load(synthetic_build / MANIFEST_OUT)


def test_a_missing_build_is_never_replaced_by_a_valid_sibling(synthetic_build):
    parent = synthetic_build.parent
    assert (parent / synthetic_build.name).is_dir()
    with pytest.raises(BuildNotFoundError):
        load(parent / "cb-ffffffffffff")
    with pytest.raises(BuildNotFoundError):
        load(parent)  # the parent holds a valid build, but is not one


# ---- an invalid build --------------------------------------------------------------------------------------------------


def test_a_tampered_output_file_is_refused(build_copy):
    p = build_copy / "qualifications.json"
    p.write_bytes(p.read_bytes() + b" ")
    refused(build_copy, "qualifications.json: SHA-256 differs")


@pytest.mark.parametrize("name", OUTPUT_FILES)
def test_a_missing_output_file_is_refused(build_copy, name):
    (build_copy / name).unlink()
    refused(build_copy, f"{name}: missing")


def test_several_problems_are_listed_together(build_copy):
    (build_copy / "evidence.json").unlink()
    (build_copy / "sources.json").write_bytes(b"x")
    err = refused(build_copy, "evidence.json")
    assert len(err.problems) == 2 and "sources.json" in str(err)


def test_an_unparseable_manifest_is_refused(build_copy):
    (build_copy / MANIFEST_OUT).write_text("{broken", encoding="utf-8")
    refused(build_copy, "unreadable")


def test_a_manifest_that_is_not_an_object_is_refused(build_copy):
    (build_copy / MANIFEST_OUT).write_text("[]", encoding="utf-8")
    refused(build_copy, "not a JSON object")


@pytest.mark.parametrize("status", ["INVALID", "NOT_BUILT", "", None])
def test_a_manifest_that_is_not_ready_is_refused(build_copy, status):
    edit_manifest(build_copy, status=status)
    refused(build_copy, "not 'READY'")


def test_a_manifest_for_another_build_id_is_refused(build_copy, tmp_path):
    other = tmp_path / "renamed" / "cb-abcdefabcdef"
    other.parent.mkdir()
    shutil.copytree(build_copy, other)
    refused(other, "does not match the directory")


@pytest.mark.parametrize("bad", ["", "cb-xyz", "build-1", 7, None])
def test_a_manifest_with_a_malformed_build_id_is_refused(build_copy, bad):
    edit_manifest(build_copy, data_build_id=bad)
    refused(build_copy, "is not a build id")


def test_a_build_from_an_older_curation_code_version_is_refused(build_copy):
    edit_manifest(build_copy, curation_code_version="p0.0-0")
    refused(build_copy, "rebuild")


@pytest.mark.parametrize("key", ["output_files", "counts"])
def test_a_manifest_missing_a_required_section_is_refused(build_copy, key):
    m = read(build_copy, MANIFEST_OUT)
    del m[key]
    (build_copy / MANIFEST_OUT).write_text(json.dumps(m), encoding="utf-8")
    refused(build_copy, f"{key} missing")


def test_a_manifest_count_that_disagrees_with_the_data_is_refused(build_copy):
    m = read(build_copy, MANIFEST_OUT)
    edit_manifest(build_copy, counts={**m["counts"], "nos_units": m["counts"]["nos_units"] + 1})
    refused(build_copy, "counts.nos_units")


def test_a_manifest_missing_a_count_is_refused(build_copy):
    m = read(build_copy, MANIFEST_OUT)
    del m["counts"]["occupations"]
    (build_copy / MANIFEST_OUT).write_text(json.dumps(m), encoding="utf-8")
    refused(build_copy, "counts.occupations")


@pytest.mark.parametrize("name", OUTPUT_FILES)
def test_an_output_file_that_is_not_a_list_of_objects_is_refused(build_copy, name):
    rewrite(build_copy, name, {"not": "a list"})
    refused(build_copy, f"{name}: expected a JSON list")


def test_an_output_file_that_is_not_json_is_refused(build_copy):
    blob = b"\xff\xfenot json"
    (build_copy / "occupations.json").write_bytes(blob)
    m = read(build_copy, MANIFEST_OUT)
    m["output_files"]["occupations.json"] = hashlib.sha256(blob).hexdigest()
    (build_copy / MANIFEST_OUT).write_text(json.dumps(m), encoding="utf-8")
    refused(build_copy, "occupations.json: not valid JSON")


# ---- missing required fields and malformed data ------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "field"), [
    ("qualifications.json", "code"), ("qualifications.json", "hours"), ("qualifications.json", "titles"),
    ("nos_units.json", "code"), ("occupations.json", "nco_code"), ("sources.json", "role"),
    ("evidence.json", "source_sha256"), ("eligibility_source_rows.json", "qualification_id"),
])
def test_a_record_missing_a_required_field_is_refused(build_copy, name, field):
    data = read(build_copy, name)
    assert data and field in data[0]
    del data[0][field]
    rewrite(build_copy, name, data)
    err = refused(build_copy, f"{name}[0]")
    assert field in str(err)


def test_an_unknown_field_is_refused_not_dropped(build_copy):
    data = read(build_copy, "qualifications.json")
    data[0]["surprise"] = 1
    rewrite(build_copy, "qualifications.json", data)
    refused(build_copy, "surprise")


def test_a_wrongly_typed_value_is_refused(build_copy):
    data = read(build_copy, "qualifications.json")
    data[0]["coverage"] = "SOMETHING_ELSE"
    rewrite(build_copy, "qualifications.json", data)
    refused(build_copy, "coverage")


def test_a_malformed_identifier_is_refused(build_copy):
    data = read(build_copy, "nos_units.json")
    data[0]["id"] = "nos:lower/n1"
    rewrite(build_copy, "nos_units.json", data)
    refused(build_copy, "nos_units.json[0]")


def test_a_nos_table_entry_pointing_at_a_missing_nos_unit_is_refused(build_copy):
    nos = read(build_copy, "nos_units.json")
    rewrite(build_copy, "nos_units.json", nos[1:], counts={"nos_units": len(nos) - 1})
    refused(build_copy, "unknown nos:")


def test_a_dangling_evidence_reference_is_refused(build_copy):
    ev = read(build_copy, "evidence.json")
    rewrite(build_copy, "evidence.json", ev[1:])
    refused(build_copy, "reference check failed")


# ---- duplicates --------------------------------------------------------------------------------------------------------


def test_a_duplicate_qualification_in_the_build_is_refused_not_resolved(build_copy):
    quals = read(build_copy, "qualifications.json")
    rewrite(build_copy, "qualifications.json", quals + [copy.deepcopy(quals[0])],
            counts={"qualifications_catalogue_only": 0, "qualifications_curated": 0, **_cover(quals + [quals[0]])})
    refused(build_copy, f"duplicate qualification id: {quals[0]['id']}")


def _cover(quals):
    return {"qualifications_curated": sum(q["coverage"] == "CURATED" for q in quals),
            "qualifications_catalogue_only": sum(q["coverage"] == "CATALOGUE_ONLY" for q in quals)}


def test_a_duplicate_nos_unit_in_the_build_is_refused(build_copy):
    nos = read(build_copy, "nos_units.json")
    rewrite(build_copy, "nos_units.json", nos + [copy.deepcopy(nos[0])], counts={"nos_units": len(nos) + 1})
    refused(build_copy, f"duplicate NOS id: {nos[0]['id']}")


def test_an_eligibility_row_for_an_unknown_qualification_is_refused_from_records(synthetic_build):
    reg = load(synthetic_build)
    row = reg.eligibility_source_rows("qual:TST/Q0001")[0]
    stray = row.model_copy(update={"id": "rule:TST/Q0009/E1", "qualification_id": "qual:TST/Q0009"})
    with pytest.raises(BuildInvalidError, match="unknown qualification"):
        Registry.from_records(qualifications=reg.qualifications(), nos_units=reg.nos_units(),
                              eligibility_source_rows=[row, stray])


# ---- the real installed build (read-only) ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_build() -> Path:
    curated = REPO / "data" / "curated"
    found = []
    for m in curated.glob(f"cb-*/{MANIFEST_OUT}") if curated.is_dir() else []:
        data = json.loads(m.read_text(encoding="utf-8"))
        if data.get("curation_code_version") == CURATION_CODE_VERSION:
            found.append((data["built_at"], m.parent))
    if not found:
        pytest.skip(f"no installed curated build of code version {CURATION_CODE_VERSION}")
    return max(found)[1]


@pytest.mark.requires_local_data
def test_real_build_loads_in_under_one_second(real_build):
    load(real_build)  # warm the file cache; the requirement is about the load, not the first disk read
    runs = []
    for _ in range(5):
        t = time.perf_counter()
        load(real_build)
        runs.append(time.perf_counter() - t)
    assert min(runs) < 1.0 and max(runs) < 1.0, runs


@pytest.mark.requires_local_data
def test_real_build_counts_and_lookups_agree(real_build):
    reg = load(real_build)
    counts = read(real_build, MANIFEST_OUT)["counts"]
    quals = reg.qualifications()
    assert len(quals) == counts["qualifications_curated"] + counts["qualifications_catalogue_only"]
    assert len(reg.nos_units()) == counts["nos_units"] and len(reg.occupations()) == counts["occupations"]
    assert len(reg.conflicts()) == counts["conflicts_open"]
    for q in quals:
        assert reg.qualification_by_id(q.id) == reg.qualification_by_code(q.code) == reg.qualification_by_slug(q.slug) == q
    for n in reg.nos_units():
        assert reg.nos_by_id(n.id) == reg.nos_by_code(n.code)
        assert set(reg.qualification_ids_with_nos(n.id)) == {
            q.id for q in quals for m in q.nos_memberships if m.nos_id == n.id}


@pytest.mark.requires_local_data
def test_real_build_pilot_qualifications_are_present_and_curated(real_build):
    reg = load(real_build)
    for code in ("AMH/Q0301", "AMH/Q2301", "AMH/Q0103", "AMH/Q2101"):
        q = reg.qualification_by_code(code)
        assert q.coverage.value == "CURATED" and q.eligibility is not None


@pytest.mark.requires_local_data
def test_real_build_copy_with_a_conflict_missing_its_status_is_refused(real_build, tmp_path):
    d = tmp_path / real_build.name
    shutil.copytree(real_build, d)  # a temporary copy: the installed build is never edited
    data = read(d, "conflicts.json")
    del data[0]["status"]
    rewrite(d, "conflicts.json", data)
    refused(d, "conflicts.json[0]")


@pytest.mark.requires_local_data
def test_real_build_is_not_modified_by_loading(real_build):
    def digest():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(real_build.iterdir())}

    before = digest()
    load(real_build)
    assert digest() == before


@pytest.mark.requires_local_data
def test_real_build_older_code_versions_are_refused_and_not_substituted(real_build):
    for d in sorted(real_build.parent.glob("cb-*")):
        m = read(d, MANIFEST_OUT)
        if m["curation_code_version"] != CURATION_CODE_VERSION:
            with pytest.raises(BuildInvalidError, match="rebuild"):
                load(d)
