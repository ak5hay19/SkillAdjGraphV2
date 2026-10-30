"""Reconciliation tests over the extracted CSVs (they never open the PDFs).

Run:  python -B -I -m pytest -p no:cacheprovider data_extraction/test_reconcile_2026-10-30.py

A failing test is a finding about the sources or the extraction; the values are not edited to make it pass.
"""
import csv
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("EXTRACTED_DIR", ROOT / "data" / "processed" / "extracted_2026-10-30"))
CATALOGUE = ROOT / "data" / "processed" / "acquisition_2026-10-30" / "approved_qualifications_parsed.csv"
QPS = ["AMH/Q0301", "AMH/Q2301", "AMH/Q0103", "AMH/Q2101"]
CSVS = ["facts.csv", "qualifications.csv", "qf_nos.csv", "qp_nos_headers.csv", "eligibility_rows.csv", "progression_claims.csv"]


def load(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if str(x).strip() != "" else 0.0


def qf(rows):
    return [r for r in rows if r["doc_type"] == "QF"]


def test_outputs_exist_and_cover_four_qualifications():
    assert {r["qp_code"] for r in qf(load("qualifications.csv"))} == set(QPS)
    assert {r["qp_code"] for r in qf(load("qf_nos.csv"))} == set(QPS)


@pytest.mark.parametrize("qp", QPS)
def test_hours_sums_equal_item13_totals(qp):
    rows = [r for r in qf(load("qf_nos.csv")) if r["qp_code"] == qp]
    total = next(r for r in qf(load("qualifications.csv")) if r["qp_code"] == qp)["hours_total"]
    assert total != "", "item 13 total not extracted"
    assert sum(num(r["total_hours"]) for r in rows) == float(total)


@pytest.mark.parametrize("qp", QPS)
def test_credit_sums_equal_item10(qp):
    rows = [r for r in qf(load("qf_nos.csv")) if r["qp_code"] == qp]
    item10 = next(r for r in qf(load("qualifications.csv")) if r["qp_code"] == qp)["credits"]
    assert item10 != "", "item 10 not extracted"
    assert sum(num(r["credits"]) for r in rows) == float(item10)


@pytest.mark.parametrize("qp", QPS)
def test_item10_equals_catalogue_credits(qp):
    with open(CATALOGUE, encoding="utf-8-sig", newline="") as f:
        cat = {r["qp_code"]: r for r in csv.DictReader(f)}
    item10 = next(r for r in qf(load("qualifications.csv")) if r["qp_code"] == qp)["credits"]
    assert float(item10) == float(cat[qp]["credits"])


@pytest.mark.parametrize("qp", QPS)
def test_qp_and_qf_nos_code_sets_equal(qp):
    qf_codes = {r["nos_code"] for r in qf(load("qf_nos.csv")) if r["qp_code"] == qp and r["nos_code"]}
    qp_codes = {r["nos_code"] for r in load("qp_nos_headers.csv") if r["qp_code"] == qp and r["nos_code"]}
    assert qf_codes and qf_codes == qp_codes


@pytest.mark.parametrize("name", CSVS)
def test_every_row_has_sha_and_page_unless_unresolved(name):
    rows = load(name)
    assert rows
    for r in rows:
        if r["extraction_status"] == "UNRESOLVED":
            continue
        assert re.fullmatch(r"[0-9a-f]{64}", r["source_sha256"]), (name, r)
        assert r["page"].strip() != "", (name, r)


PII = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"(?<![\w.])\+?\d{1,3}[\s-]?\(?\d{2,5}\)?[\s-]?\d{3,5}[\s-]?\d{3,5}(?![\w.])"),
    re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),
]


def test_no_email_or_phone_patterns_in_any_output():
    hits = []
    for path in sorted(OUT.iterdir()):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\b[0-9a-f]{64}\b", "", text)  # SHA-256 hashes are not contact data
        for rx in PII:
            for m in rx.finditer(text):
                if sum(c.isdigit() for c in m.group()) >= 10 or "@" in m.group():
                    hits.append((path.name, rx.pattern[:20]))
    assert not hits, hits
