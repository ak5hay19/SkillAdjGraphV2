"""The schemas must be able to represent the real source records. Nothing here builds curated data: it only checks
that identifiers, enum values and numeric ranges that occur in the evidence are accepted, and that the known
awkward cases (error-page hashes, blank cells) are handled as designed. Reads data/ only; never writes."""

import csv
import glob
from datetime import datetime

import pytest
from pydantic import ValidationError

from skillgraph.model.base import Hours, NsqfLevel
from skillgraph.model.evidence import CreditValue, EngineUse, OfficialValued, ValueStatus
from skillgraph.model.ids import IdKind, make_id, slug_of
from skillgraph.model.source import SourceDocument

pytestmark = pytest.mark.requires_local_data


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def tables(repo_data):
    processed = repo_data / "processed"
    extracted = {p.replace("\\", "/").rsplit("/", 1)[1]: read(p) for p in glob.glob(str(processed / "extracted_2026-10-30" / "*.csv"))}
    return {
        "extracted": extracted,
        "overlay": read(processed / "audit_2026-10-30_m1s1" / "corrections_overlay.csv"),
        "catalogue": read(processed / "acquisition_2026-10-30" / "approved_qualifications_parsed.csv"),
        "manifest": read(repo_data / "raw" / "2026-10-30" / "MANIFEST.csv"),
    }


def test_every_real_code_is_a_valid_identifier_with_a_unique_slug(tables):
    qual = {r["qp_code"] for rows in tables["extracted"].values() for r in rows if r.get("qp_code")}
    qual |= {r["qp_code"] for r in tables["catalogue"]}
    nos = {r["nos_code"] for r in tables["extracted"]["qf_nos.csv"] + tables["extracted"]["qp_nos_headers.csv"] if r["nos_code"]}
    nco = {r["nco_2015_code"] for r in tables["extracted"]["qualifications.csv"]}
    src = {r["item_id"] for r in tables["manifest"]}
    ov = {r["overlay_id"] for r in tables["overlay"]}
    assert len(qual) == 37 and nos and len(nco) == 4 and len(src) == 22 and len(ov) == 52
    ids = [make_id(k, c) for k, codes in ((IdKind.QUAL, qual), (IdKind.NOS, nos), (IdKind.NCO, nco), (IdKind.SRC, src),
                                          (IdKind.CONFLICT, ov))
           for c in sorted(codes)]
    slugs = [slug_of(i) for i in ids if slug_of(i)]
    assert len(slugs) == len(set(slugs))  # no collision across the real evidence


def test_real_enum_values_are_all_representable(tables):
    statuses = {r["extraction_status"] for rows in tables["extracted"].values() for r in rows}
    assert statuses <= {s.value for s in ValueStatus}
    uses = {r["engine_use"] for r in tables["overlay"]}
    assert uses <= {u.value for u in EngineUse}


def official(value, **extra):
    return {"value": value, "evidence_class": "OFFICIAL", "evidence_id": "ev:" + "0" * 16, "value_status": "TRANSCRIBED",
            **extra}


def test_real_numbers_fit_the_numeric_types(tables):
    qf = tables["extracted"]["qf_nos.csv"] + tables["extracted"]["qualifications.csv"]
    for r in tables["extracted"]["qualifications.csv"]:
        for col in ("hours_theory", "hours_practical", "hours_ojt_mandatory", "hours_ojt_recommended", "hours_total"):
            OfficialValued[Hours].model_validate(official(float(r[col]), engine_use="SAFE_HOURS"))
        CreditValue.model_validate(official(float(r["credits"]), engine_use="NOT_USED"))
    for r in qf:
        if r["nsqf_level"]:
            OfficialValued[NsqfLevel].model_validate(official(float(r["nsqf_level"])))
    for r in tables["catalogue"]:
        OfficialValued[NsqfLevel].model_validate(official(float(r["nsqf_level"])))
        OfficialValued[Hours].model_validate(official(float(r["notional_hours"]), engine_use="SAFE_HOURS"))
        CreditValue.model_validate(official(float(r["credits"]), engine_use="NOT_USED"))


def source_from(row, *, keep_hash=True):
    return {
        "id": f"src:{row['item_id']}", "manifest_item_id": row["item_id"], "title": row["item_name"],
        "org": row["source_org"], "url": row["source_url"] or None,
        "retrieved_at": datetime.fromisoformat(row["retrieved_at"]) if row["retrieved_at"] else None,
        "sha256": (row["sha256"] or None) if keep_hash or row["local_relative_path"] else None,
        "file_type": row["file_type"] or None, "pages": int(row["pdf_pages"]) if row["pdf_pages"] else None,
        "validation_status": row["validation_status"], "role": "PRIMARY",
    }


def test_every_manifest_item_is_representable_when_unavailable_items_carry_no_hash(tables):
    for row in tables["manifest"]:
        doc = SourceDocument.model_validate(source_from(row, keep_hash=False))
        assert doc.has_local_file == bool(row["local_relative_path"])
        assert doc.licence_status.value == "UNCONFIRMED"


def test_a_manifest_hash_recorded_for_an_unavailable_item_is_refused(tables):
    unavailable_with_hash = [r for r in tables["manifest"] if not r["local_relative_path"] and r["sha256"]]
    assert {r["item_id"] for r in unavailable_with_hash} == {"C3", "D1"}  # the error-page hashes
    for row in unavailable_with_hash:
        with pytest.raises(ValidationError, match="sha256 must be null"):
            SourceDocument.model_validate(source_from(row, keep_hash=True))
