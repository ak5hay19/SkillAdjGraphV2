"""A small, internally consistent synthetic data tree for the P1.4 build tests.

Codes are TST/…; nothing here is a real source value. The tree mirrors the real layout (raw/2026-10-30,
processed/extracted_2026-10-30, processed/audit_2026-10-30_m1s1, processed/acquisition_2026-10-30) so that the real
``verify_sources`` runs unchanged. CSV fixtures are written at test time (``*.csv`` is gitignored).
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from skillgraph.curation.build import build
from skillgraph.curation.config import DEFAULTS_PATH
from skillgraph.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
QP = "TST/Q0001"
PDF = b"%PDF-1.4 synthetic qualification file\n" * 20
PDF2 = b"%PDF-1.4 another synthetic file\n" * 20
CAT_HEADER = ["S.No.", "QP Name", "QP Code", "NQR Code", "QP Version", "NSQF Level", "Notional Hours", "Credits", "CCN"]
CAT_KEYS = ["sno", "qp_name", "qp_code", "nqr_code", "qp_version", "nsqf_level", "notional_hours", "credits", "ccn"]


def a1_html(rows: list[dict]) -> bytes:
    """A catalogue page shaped like the real A1: a table with the nine data columns and two download columns."""
    head = "".join(f"<th>{h}</th>" for h in CAT_HEADER + ["Download (QP)", "Download (Q File)"])
    body = "".join("<tr>" + "".join(f"<td>{r[k]}</td>" for k in CAT_KEYS) + "<td><a href='/qp'>QP</a></td><td>"
                   "<a href='/qf'>QF</a></td></tr>" for r in rows)
    return f"<html><body><table><tr>{head}</tr>{body}</table></body></html>".encode()

MANIFEST_COLS = ["item_id", "item_name", "phase", "required_for_gate", "source_org", "source_url", "catalogue_url_raw",
                 "final_url", "local_relative_path", "retrieved_at", "http_status", "content_type", "size_bytes",
                 "sha256", "file_type", "pdf_pages", "validation_status", "reason", "notes"]
QUAL_COLS = ["qp_code", "nqr_code", "doc_type", "qualification_name", "previous_version_ref", "nsqf_level", "min_age",
             "credits", "hours_theory", "hours_practical", "hours_ojt_mandatory", "hours_ojt_recommended", "hours_total",
             "nco_2015_code", "progression_text", "source_file", "source_sha256", "page", "method", "extraction_status",
             "note"]
QFNOS_COLS = ["qp_code", "nqr_code", "doc_type", "s_no", "nos_module_name", "nos_code", "nos_version", "core_label_raw",
              "core_or_noncore", "nsqf_level", "credits", "theory", "practical", "ojt_mandatory", "ojt_recommended",
              "total_hours", "is_bridge", "row_sum_ok", "hazard_flags", "uncertain_cells", "source_file", "source_sha256",
              "page", "method", "extraction_status", "note"]
QPNOS_COLS = ["qp_code", "nqr_code", "doc_type", "nos_code", "nos_name", "nsqf_level", "credits", "version",
              "source_file", "source_sha256", "page", "method", "extraction_status", "note"]
ELIG_COLS = ["qp_code", "nqr_code", "doc_type", "row_type", "s_no", "raw_academic_or_skill", "raw_required_experience",
             "raw_row_text", "min_education", "prior_nsqf_level", "experience_years", "relevance_qualifier", "min_age",
             "source_file", "source_sha256", "page", "method", "extraction_status", "note"]
FACT_COLS = ["qp_code", "nqr_code", "doc_type", "field", "value", "source_file", "source_sha256", "page", "method",
             "extraction_status", "note"]
CLAIM_COLS = ["qp_code", "nqr_code", "doc_type", "claim_no", "claim_text_verbatim", "direction_label", "source_file",
              "source_sha256", "page", "method", "extraction_status", "note"]
OV_COLS = ["overlay_id", "category", "qp_code", "target_file", "target_row_key", "target_field", "source_value",
           "overlay_value", "evidence_source_file", "evidence_sha256", "evidence_page", "evidence_location", "method",
           "status", "rationale", "engine_use", "engine_constraint", "decision_ref"]
CAT_COLS = ["sno", "qp_name", "qp_code", "nqr_code", "qp_version", "nsqf_level", "notional_hours", "credits", "ccn",
            "qp_href_raw", "qf_href_raw", "qp_url_resolved", "qf_url_resolved", "link_mapping"]

SHA1 = hashlib.sha256(PDF).hexdigest()
SHA2 = hashlib.sha256(PDF2).hexdigest()
SRC = "qf/synthetic.pdf"
SRC2 = "qf/other.pdf"


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def src(**kw) -> dict:
    return {"source_file": SRC, "source_sha256": SHA1, "page": "3", "method": "pdfplumber_words",
            "extraction_status": "TRANSCRIBED", "note": "", "nqr_code": "QG-TEST", "doc_type": "QF", "qp_code": QP, **kw}


def ov(oid: str, key: str, fld: str, status: str, use: str, *, file="eligibility_rows.csv", src_val="", ov_val="",
       cat="ELIGIBILITY_INTERPRETATION", page="3", sha=SHA1, sfile=SRC, decision="A3") -> dict:
    return {"overlay_id": oid, "category": cat, "qp_code": QP, "target_file": file, "target_row_key": key,
            "target_field": fld, "source_value": src_val, "overlay_value": ov_val, "evidence_source_file": sfile,
            "evidence_sha256": sha, "evidence_page": page, "evidence_location": "synthetic location", "method": "synthetic",
            "status": status, "rationale": "synthetic", "engine_use": use, "engine_constraint": "", "decision_ref": decision}


class Tree:
    """Write the tree, then ``build`` it; every input is mutable before the build."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = root / "data"
        self.raw = self.data / "raw" / "2026-10-30"
        self.ext = self.data / "processed" / "extracted_2026-10-30"
        self.aud = self.data / "processed" / "audit_2026-10-30_m1s1"
        self.acq = self.data / "processed" / "acquisition_2026-10-30"
        self.out = root / "out"
        self.approvals = root / "approvals.yaml"
        self.config = root / "curation.yaml"
        self.manifest = [
            self.m("S1", SRC, PDF, "pdf", 20), self.m("S2", SRC2, PDF2, "pdf", 5),
            self.m("A1", "catalogue/page.html", b"placeholder", "html", None),
            {"item_id": "C3", "item_name": "Unavailable record", "source_org": "NQR", "validation_status": "FAIL_HTTP",
             "http_status": "404", "sha256": "0" * 64},
        ]
        self.qual = [src(qualification_name="Synthetic Operator", nsqf_level="3", min_age="18", credits="4",
                         hours_theory="20", hours_practical="80", hours_ojt_mandatory="0", hours_ojt_recommended="0",
                         hours_total="100", nco_2015_code="8153.0101", page="3-4")]
        self.qfnos = [
            src(s_no="1", nos_module_name="Introduction (Bridge Module)", nos_code="", nos_version="",
                core_or_noncore="Core", nsqf_level="3", credits="", theory="3", practical="0", ojt_mandatory="0",
                ojt_recommended="0", total_hours="3", is_bridge="true", page="5", note="credit cell empty"),
            src(s_no="2", nos_module_name="Do the work", nos_code="TST/N0001", nos_version="4.0", core_or_noncore="Core",
                nsqf_level="3", credits="4", theory="12", practical="85", ojt_mandatory="0", ojt_recommended="0",
                total_hours="97", is_bridge="false", uncertain_cells="credits", page="5",
                extraction_status="PARSED_UNCERTAIN", note="credits: assigned by position"),
        ]
        self.qpnos = [src(doc_type="QP", nos_code="TST/N0001", nos_name="Do the work", nsqf_level="3", credits="9",
                          version="4.0", page="14")]
        self.elig = [
            src(row_type="eligibility_row", s_no="1", raw_academic_or_skill="11th Grade pass",
                raw_required_experience="No Experience required", raw_row_text="11th Grade pass | No Experience required",
                extraction_status="PARSED_UNCERTAIN", note="merged experience cell"),
            src(row_type="eligibility_row", s_no="2", raw_academic_or_skill="Completed 1st year of diploma",
                raw_required_experience="", raw_row_text="Completed 1st year of diploma | ",
                extraction_status="PARSED_UNCERTAIN", note="experience cell empty"),
            src(row_type="age_9c", min_age="18", page="4"),
        ]
        self.facts = [src(field="item5_version", value="4.0", extraction_status="PARSED_UNCERTAIN", page="3")]
        self.claims = [src(claim_no="1", claim_text_verbatim="Senior Operator(Vertical)", direction_label="Vertical", page="4")]
        self.overlay = [
            ov("OV-001", f"{QP}|QF|eligibility_row|1", "raw_required_experience", "CONFIRMED_BY_GEOMETRY",
               "SAFE_HARD_RULE", src_val="No Experience required"),
            ov("OV-002", f"{QP}|QF|eligibility_row|2", "raw_required_experience", "PROPOSED_CORRECTION", "UNKNOWN",
               src_val="", ov_val="No Experience required", cat="CORRECTION_PROPOSED"),
            ov("OV-003", f"{QP}|QF|bridge(s_no 1)+TST/N0001", "credits", "PROPOSED_REPRESENTATION", "NOT_USED",
               file="qf_nos.csv", src_val="bridge=''; TST/N0001='4'",
               ov_val="credit_group: one value '4' for bridge + TST/N0001 combined", cat="CREDIT_GROUP", page="5"),
            ov("OV-004", f"{QP}|QF|eligibility_row|2", "raw_row_text", "UNRESOLVED", "UNKNOWN",
               src_val="Completed 1st year of diploma | "),
            ov("OV-005", f"{QP}|QF|age_9c", "min_age", "CONFIRMED_BY_GEOMETRY", "SAFE_HARD_RULE", src_val="18", page="4"),
            ov("OV-006", f"{QP}|QF|item5_version", "value", "PARSED_UNCERTAIN_RETAINED", "DISPLAY_ONLY", file="facts.csv",
               src_val="4.0", cat="REVIEW_FLAG"),
            ov("OV-007", f"{QP}|QF|claim 1", "claim_text_verbatim", "NO_OFFICIAL_RELATIONSHIP", "NOT_USED",
               file="progression_claims.csv", src_val="Senior Operator(Vertical)", cat="NO_INFERENCE", page="4"),
        ]
        self.catalogue = [
            {"sno": "1", "qp_name": "Synthetic Operator", "qp_code": QP, "nqr_code": "QG-TEST", "qp_version": "4",
             "nsqf_level": "3", "notional_hours": "100", "credits": "4", "ccn": "1"},
            {"sno": "2", "qp_name": "Other – Role", "qp_code": "TST/Q0002", "nqr_code": "QG-T2", "qp_version": "1",
             "nsqf_level": "4", "notional_hours": "240", "credits": "8", "ccn": "1"},
            {"sno": "3", "qp_name": "Third Role", "qp_code": "TST/Q0003", "nqr_code": "QG-T3", "qp_version": "2",
             "nsqf_level": "2", "notional_hours": "120", "credits": "4", "ccn": "1"},
        ]
        self.set_a1(a1_html(self.catalogue))
        self.validation = {"nco": {"8153.0101": {"outcome": "NOT_FOUND"}}, "items": {}}
        self.curation = yaml.safe_load((REPO / DEFAULTS_PATH).read_text(encoding="utf-8"))
        self.curation.update(conflict_groups=[], open_leads=[], title_aliases=[], pilot_qualifications=[QP],
                             expected_catalogue_only=2, expected_overlay_rows=7)
        self.approved: list[str] = []

    def set_a1(self, content: bytes) -> None:
        """Replace the A1 page (and its manifest hash) so that the integrity check still passes."""
        self.manifest[2] = self.m("A1", "catalogue/page.html", content, "html", None)

    @staticmethod
    def m(item, rel, content, ftype, pages) -> dict:
        return {"item_id": item, "item_name": f"Synthetic {item}", "source_org": "TST",
                "local_relative_path": f"data/raw/2026-10-30/{rel}", "sha256": hashlib.sha256(content).hexdigest(),
                "file_type": ftype, "pdf_pages": "" if pages is None else str(pages), "validation_status": "PASS",
                "retrieved_at": "2026-10-30T10:00:00+05:30", "_content": content, "_rel": rel}

    def write(self) -> Tree:
        for m in self.manifest:
            if "_rel" in m:
                p = self.raw / m["_rel"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(m["_content"])
        _write(self.raw / "MANIFEST.csv", MANIFEST_COLS, [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.manifest])
        (self.raw / "VALIDATION.json").write_text(json.dumps(self.validation), encoding="utf-8")
        _write(self.ext / "qualifications.csv", QUAL_COLS, self.qual)
        _write(self.ext / "qf_nos.csv", QFNOS_COLS, self.qfnos)
        _write(self.ext / "qp_nos_headers.csv", QPNOS_COLS, self.qpnos)
        _write(self.ext / "eligibility_rows.csv", ELIG_COLS, self.elig)
        _write(self.ext / "facts.csv", FACT_COLS, self.facts)
        _write(self.ext / "progression_claims.csv", CLAIM_COLS, self.claims)
        _write(self.aud / "corrections_overlay.csv", OV_COLS, self.overlay)
        _write(self.acq / "approved_qualifications_parsed.csv", CAT_COLS, self.catalogue)
        self.config.write_text(yaml.safe_dump(self.curation), encoding="utf-8")
        self.approvals.write_text(yaml.safe_dump({"approved": [
            {"overlay_id": o, "approved_by": "test-fixture", "approved_on": "2026-01-01", "note": ""}
            for o in self.approved]}), encoding="utf-8")
        return self

    def settings(self):
        return load_settings(REPO / "config" / "default.yaml", self.data, environ={})

    def build(self, *, approve: list[str] | None = None, **kw):
        if approve is not None:
            self.approved = approve
        self.write()
        return build(self.settings(), approvals_path=self.approvals, config_path=self.config, out_root=self.out, **kw)

    def snapshot(self) -> dict[str, str]:
        files = [p for p in self.root.rglob("*") if p.is_file() and self.out not in p.parents]
        return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

    def installed(self) -> list[str]:
        return sorted(p.name for p in self.out.iterdir()) if self.out.exists() else []


def load(result, name: str):
    return json.loads((result.path / name).read_text(encoding="utf-8"))
