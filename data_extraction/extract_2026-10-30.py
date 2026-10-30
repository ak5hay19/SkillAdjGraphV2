"""Milestone 1, Step 1: structured extraction and reconciliation for 4 AMHSSC qualifications.

Read-only on data/raw and data/processed/acquisition_*; writes only to the new output
folder below.  Run with:  python -B -I data_extraction/extract_2026-10-30.py

Privacy: only items listed in the task scope are isolated by marker / column position;
other page text is never stored, logged or written.  Every value is screened for
email and phone patterns before it is written (a heuristic, not a guarantee).
"""
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber
import pypdf

RUN_ID = "2026-10-30"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "2026-10-30"
MANIFEST = RAW / "MANIFEST.csv"
CATALOGUE = ROOT / "data" / "processed" / "acquisition_2026-10-30" / "approved_qualifications_parsed.csv"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "processed" / f"extracted_{RUN_ID}"  # argv override: dry runs outside the project

QUALS = [
    dict(qp_code="AMH/Q0301", name="Sewing Machine Operator",
         qf="amhssc/qf/Q FILE Sewing Machine Operator.pdf", qp="amhssc/qp/Sewing Machine Operator.pdf",
         exp=dict(hours=300, credits=10, nco="8153.0101", level="2.5", age=18,
                  nos=["AMH/N0301", "AMH/N0302", "AMH/N0102", "AMH/N0103", "AMH/N0104", "DGT/VSQ/N0101"])),
    dict(qp_code="AMH/Q2301", name="Specialized Sewing Machine Operator",
         qf="amhssc/qf/Q FILE Specialized Sewing Machine Operator(1).pdf",
         qp="amhssc/qp/Specialized Sewing Machine Operator.pdf",
         exp=dict(hours=420, credits=14, nco="8153.0103", level="3.5", age=18,
                  nos=["AMH/N2301", "AMH/N2302", "AMH/N0310", "AMH/N0309", "DGT/VSQ/N0102"])),
    dict(qp_code="AMH/Q0103", name="Inline Checker - Sewing",
         qf="nqr/qf/Q FILE Inline Checker Sewing Version 4.0.pdf", qp="amhssc/qp/Inline Checker Sewing QP File.pdf",
         exp=dict(hours=420, credits=14, nco="7543.0301", level="3.5", age=18,
                  nos=["AMH/N0105", "AMH/N0106", "AMH/N0107", "AMH/N0309", "AMH/N0311", "DGT/VSQ/N0102"])),
    dict(qp_code="AMH/Q2101", name="Production Supervisor - Sewing",
         qf="amhssc/qf/Production Supervisor- Sewing V4_0.pdf", qp="amhssc/qp/Production Supervisor Sewing QP File.pdf",
         exp=dict(hours=570, credits=19, nco="3122.3551", level="5", age=20,
                  nos=["AMH/N2101", "AMH/N2102", "AMH/N2103", "AMH/N2104", "AMH/N0619", "AMH/N0620",
                       "AMH/N0621", "DGT/VSQ/N0102"])),
]
IC_SECONDARY_QF = "amhssc/qf/Inline Checker Sewing V4_0.pdf"

# ---------------------------------------------------------------- privacy screen
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RUN = re.compile(r"\+?\(?\d[\d\s()\-]{8,}\d")
MOBILE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
OMIT = "omitted — privacy screen"


def has_pii(s):
    s = str(s)
    if EMAIL.search(s) or MOBILE.search(s):
        return True
    return any(sum(c.isdigit() for c in m.group()) >= 10 for m in PHONE_RUN.finditer(s))


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- provenance helpers
PROV = ["source_file", "source_sha256", "page", "method", "extraction_status", "note"]
FACTS = []
_FACT_KEYS = set()


def prov(src, page, method, status="TRANSCRIBED", note=""):
    return dict(source_file=src["rel"], source_sha256=src["sha"], page=page, method=method,
                extraction_status=status, note=note)


def add_fact(qp_code, doc_type, field, value, src, page, method, status="TRANSCRIBED", note=""):
    key = (qp_code, doc_type, field, src["rel"])
    if key in _FACT_KEYS:
        raise RuntimeError(f"duplicate fact {key}")
    _FACT_KEYS.add(key)
    FACTS.append(dict(qp_code=qp_code, nqr_code="", doc_type=doc_type, field=field, value=value,
                      **prov(src, page, method, status, note)))


def unresolved(qp_code, doc_type, field, src, why, page=""):
    add_fact(qp_code, doc_type, field, "", src, page, "pdfplumber_words", "UNRESOLVED", why)


# ---------------------------------------------------------------- checksum gate
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_sources():
    man = {r["local_relative_path"]: r for r in csv.DictReader(open(MANIFEST, encoding="utf-8-sig"))}
    wanted = []
    for q in QUALS:
        wanted += [q["qf"], q["qp"]]
    wanted.append(IC_SECONDARY_QF)
    srcs, bad = {}, []
    for rel in wanted:
        p = RAW / rel
        key = f"data/raw/2026-10-30/{rel}"
        if not p.exists() or key not in man:
            bad.append((rel, "missing file or manifest row"))
            continue
        h = sha256(p)
        if h != man[key]["sha256"].lower():
            bad.append((rel, "checksum differs from manifest"))
            continue
        srcs[rel] = dict(rel=rel, path=p, sha=h)
    if bad:
        print("STOP: source verification failed:", bad)
        sys.exit(2)
    return srcs


# ---------------------------------------------------------------- generic geometry helpers
def covers(segs, a, b, tol=3.0):
    segs = sorted(segs)
    cur = None
    for x0, x1 in segs:
        if cur is None:
            cur = [x0, x1]
        elif x0 <= cur[1] + tol:
            cur[1] = max(cur[1], x1)
        else:
            if cur[0] <= a + tol and cur[1] >= b - tol:
                return True
            cur = [x0, x1]
    return cur is not None and cur[0] <= a + tol and cur[1] >= b - tol


def hrules(page, a, b, ymin=0.0, ymax=1e9):
    segs = defaultdict(list)
    for e in page.edges:
        if e["orientation"] == "h" and ymin <= e["top"] <= ymax:
            segs[round(e["top"])].append((e["x0"], e["x1"]))
    ys = [y for y in sorted(segs) if covers(segs[y], a, b)]
    groups = []
    for y in ys:
        if groups and y - groups[-1][-1] <= 2.5:
            groups[-1].append(y)
        else:
            groups.append([y])
    return [sum(g) / len(g) for g in groups]


def in_band(w, ya, yb):
    c = (w["top"] + w["bottom"]) / 2
    return ya < c < yb


def join_words(ws):
    ws = sorted(ws, key=lambda w: (round(w["top"] / 2.5), w["x0"]))
    out = ""
    for w in ws:
        t = w["text"]
        out = out + t if out.endswith("-") and not out.endswith(" -") else (out + " " + t if out else t)
    return clean(out)


# ---------------------------------------------------------------- QF section 1
CODE_RE = re.compile(r"^(?:AMH|DGT)/(?:VSQ/)?N\d{4}$")
CLEAN_EDU = re.compile(
    r"(?:\d+(?:st|nd|rd|th)?\s*(?:grade|class)(?:\s*pass)?|grade\s*\d+(?:\s*pass)?|UG Diploma or equivalent|"
    r"UG Certificate|12th or Equivalent|Ability to read and write)", re.I)
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def parse_exp(text):
    t = clean(text)
    if not t:
        return None, None, "experience cell empty"
    if re.fullmatch(r"no experience required", t, re.I):
        return 0.0, "none", ""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)[\s-]*years?\s+relevant\s+experience", t, re.I)
    if m:
        return float(m.group(1)), "relevant", ""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*months?\s+relevant\s+experience", t, re.I)
    if m:
        return round(float(m.group(1)) / 12, 4), "relevant", ""
    m = re.fullmatch(r"(one|two|three|four|five)\s+years?\s+relevant\s+experience(?:\s+required)?", t, re.I)
    if m:
        return float(WORDNUM[m.group(1).lower()]), "relevant", ""
    return None, None, "experience text not in a recognised pattern"


def parse_eligibility(acad, exp):
    notes, status = [], "TRANSCRIBED"
    m = re.fullmatch(r"Previous relevant Qualification of NSQF Level\s*\(?(\d+(?:\.\d+)?)\)?", clean(acad), re.I)
    prior, minedu = "", ""
    if m:
        prior = m.group(1)
    else:
        minedu = clean(acad)
        if not CLEAN_EDU.fullmatch(minedu):
            status = "PARSED_UNCERTAIN"
            notes.append("academic text not a simple grade/qualification phrase")
    yrs, qual, why = parse_exp(exp)
    if why:
        status = "PARSED_UNCERTAIN"
        notes.append(why)
    return dict(min_education=minedu, prior_nsqf_level=prior,
                experience_years="" if yrs is None else yrs,
                relevance_qualifier=qual or ""), status, "; ".join(notes)


def extract_eligibility(pdf, src, q, doc_type, qp_code):
    rows = []
    p3 = pdf.pages[2]
    w3 = p3.extract_words()
    hy = next((w["top"] for w in w3 if w["text"].startswith("Eligibility")), None)
    ac = next((w for w in w3 if hy is not None and w["text"].startswith("Academic/Skill") and w["top"] > hy), None)
    rq = next((w for w in w3 if hy is not None and w["text"] == "Required" and w["top"] > hy), None)
    if not (ac and rq):
        unresolved(qp_code, doc_type, "item9_eligibility", src, "item 9 table header not found", 3)
        return rows
    vxs = sorted({round(e["x0"]) for e in p3.edges if e["orientation"] == "v" and e["top"] > hy - 5})
    acad_left = max((x for x in vxs if ac["x0"] - 120 <= x <= ac["x0"] - 3), default=None)
    req_left = max((x for x in vxs if rq["x0"] - 120 <= x <= rq["x0"] - 3), default=None)
    if acad_left is None or req_left is None:
        unresolved(qp_code, doc_type, "item9_eligibility", src, "item 9 column boundaries not found", 3)
        return rows
    n = 0
    for pn in (3, 4):
        page = pdf.pages[pn - 1]
        pw = page.extract_words()
        if pn == 3:
            ymin = hy
            ymax = next((w["top"] for w in pw if w["text"] == "Page" and w["top"] > hy), page.height)
        else:
            ymin = 0.0
            ymax = next((w["top"] for w in pw if w["text"] == "10." and w["x0"] < acad_left), None)
            if ymax is None:
                ymax = page.height
        ys = hrules(page, acad_left, req_left - 3, ymin, ymax + 3)  # rows are defined by the academic column's rules
        exp_rules = hrules(page, req_left, req_left + 60, ymin, ymax + 3)
        has_exp_rule = lambda y: any(abs(y - r) <= 2.5 for r in exp_rules)
        for ya, yb in zip(ys, ys[1:]):
            band = [w for w in pw if in_band(w, ya, yb) and w["x0"] >= acad_left - 60]
            sno = [w for w in band if w["x1"] <= acad_left + 1 and re.fullmatch(r"\d{1,2}", w["text"])]
            if not sno or any(w["text"] == "Age:" for w in band):
                continue
            acad = join_words([w for w in band if acad_left - 1 <= w["x0"] < req_left - 1])
            exp = join_words([w for w in band if w["x0"] >= req_left - 1])
            parsed, status, note = parse_eligibility(acad, exp)
            merged_below, merged_above = not has_exp_rule(yb), not has_exp_rule(ya)
            if merged_below or merged_above:
                status = "PARSED_UNCERTAIN"
                msg = ("experience cell is merged across eligibility rows; its text is printed once and is not copied to the other rows"
                       if exp else "experience cell is merged with an adjacent row and has no text of its own here")
                note = (note + "; " + msg).strip("; ")
            if len(sno) > 1:
                status, note = "PARSED_UNCERTAIN", (note + "; multiple S.No tokens in one row band").strip("; ")
            raw = f"{acad} || {exp}"
            n += 1
            rows.append(dict(qp_code=qp_code, nqr_code="", doc_type=doc_type, row_type="eligibility_row",
                             s_no=sno[0]["text"], raw_academic_or_skill=acad, raw_required_experience=exp,
                             raw_row_text=raw, **parsed, **prov(src, pn, "pdfplumber_words", status, note)))
    if n == 0:
        unresolved(qp_code, doc_type, "item9_eligibility_rows", src, "no eligibility rows isolated", 3)
    return rows


def table_rows(page):
    for t in page.extract_tables():
        for r in t:
            yield [(c or "") for c in r]


def extract_qf_section1(pdf, src, q, doc_type):
    qp = q["qp_code"]
    res = dict(nqr="", level="", nco="", credits="", hours={}, prev_ref="", progression="")
    pages = {3: pdf.pages[2], 4: pdf.pages[3]}
    rows_by_item = {}
    for pn, page in pages.items():
        for r in table_rows(page):
            m = re.match(r"^\s*(3|5|10|13|14|15)\.\s*$", r[0])
            if m and m.group(1) not in rows_by_item:
                rows_by_item[m.group(1)] = (pn, r)
    # item 3: previous-version reference
    if "3" in rows_by_item:
        pn, r = rows_by_item["3"]
        cell = next((clean(c) for c in r if "existing/previous" in c and "NQR Code" in c), "")
        m = re.search(r"qualification:\s*(\S.*?)\s*,\s*Version\s*(\S+)", cell)
        if m:
            ref = re.sub(r"\s+", "", m.group(1))
            add_fact(qp, doc_type, "previous_version_ref", ref, src, pn, "pdfplumber_table", note="line-wrap joined; predecessor, not a conflict")
            add_fact(qp, doc_type, "previous_version_number", m.group(2), src, pn, "pdfplumber_table")
            res["prev_ref"] = ref
        else:
            unresolved(qp, doc_type, "previous_version_ref", src, "item 3 previous-version cell not parsed", pn)
    else:
        unresolved(qp, doc_type, "previous_version_ref", src, "item 3 row not found", 3)
    # item 5 / 6
    if "5" in rows_by_item:
        pn, r = rows_by_item["5"]
        txt = " ".join(clean(c) for c in r)
        m = re.search(r"QG-[A-Za-z0-9.\-]+?-AMHSSC", txt.replace(" ", ""))
        if m:
            res["nqr"] = m.group(0)
            add_fact(qp, doc_type, "nqr_code", m.group(0), src, pn, "pdfplumber_table")
        else:
            unresolved(qp, doc_type, "nqr_code", src, "NQR code pattern not found in item 5 row", pn)
        m = re.search(r"NCrF/NSQF Level:\s*(\d+(?:\.\d+)?)", txt)
        if m:
            res["level"] = m.group(1)
            add_fact(qp, doc_type, "nsqf_level", m.group(1), src, pn, "pdfplumber_table")
        else:
            unresolved(qp, doc_type, "nsqf_level", src, "item 6 level not found", pn)
        lines = (pages[pn].extract_text() or "").split("\n")
        ver = next((re.search(r"Version\s+(\d+(?:\.\d+)?)\s*$", l) for l in lines
                    if l.strip().startswith("(Will be issued after NSQC approval)")), None)
        if ver:
            add_fact(qp, doc_type, "item5_version", ver.group(1), src, pn, "regex_line",
                     "PARSED_UNCERTAIN", "version printed on the line below the NQR code cell; association with the code is by adjacency")
        else:
            unresolved(qp, doc_type, "item5_version", src, "item 5 version line not found", pn)
    else:
        for f in ("nqr_code", "nsqf_level", "item5_version"):
            unresolved(qp, doc_type, f, src, "item 5 row not found", 3)
    # item 10
    if "10" in rows_by_item:
        pn, r = rows_by_item["10"]
        v = next((clean(c) for c in r[1:] if re.fullmatch(r"\d+", clean(c))), "")
        if v:
            res["credits"] = int(v)
            add_fact(qp, doc_type, "item10_credits", int(v), src, pn, "pdfplumber_table")
        else:
            unresolved(qp, doc_type, "item10_credits", src, "credit value not found", pn)
    else:
        unresolved(qp, doc_type, "item10_credits", src, "item 10 row not found", 4)
    # item 13
    p4 = pages[4]
    hrow = next((r for r in table_rows(p4) if clean(r[0]).startswith("Classroom")), None)
    if hrow:
        nums = [clean(c) for c in hrow[1:] if clean(c)]
        names = ["theory", "practical", "ojt_mandatory", "ojt_recommended", "total"]
        if len(nums) == 5 and all(re.fullmatch(r"\d+", n) for n in nums):
            for nme, v in zip(names, nums):
                add_fact(qp, doc_type, f"item13_hours_{nme}", int(v), src, 4, "pdfplumber_table",
                         note="Classroom (offline) row; Online row is blank")
            res["hours"] = dict(zip(names, map(int, nums)))
        else:
            for nme in names:
                unresolved(qp, doc_type, f"item13_hours_{nme}", src, f"hours cells not 5 integers: {len(nums)} found", 4)
    else:
        for nme in ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total"):
            unresolved(qp, doc_type, f"item13_hours_{nme}", src, "hours table row not found", 4)
    # item 14
    if "14" in rows_by_item:
        pn, r = rows_by_item["14"]
        m = re.search(r"NCO-\d{4}/(\d{4}\.\d{4})", " ".join(clean(c) for c in r))
        if m:
            res["nco"] = m.group(1)
            add_fact(qp, doc_type, "nco_2015_code", m.group(1), src, pn, "pdfplumber_table", note=f"raw: {m.group(0)}")
        else:
            unresolved(qp, doc_type, "nco_2015_code", src, "NCO pattern not found", pn)
    else:
        unresolved(qp, doc_type, "nco_2015_code", src, "item 14 row not found", 4)
    # item 15 (verbatim)
    claims = []
    if "15" in rows_by_item:
        pn, r = rows_by_item["15"]
        cell = next((c for c in r[2:] if c.strip()), "")
        lines = [clean(l) for l in cell.split("\n") if clean(l)]
        res["progression"] = "\n".join(lines)
        add_fact(qp, doc_type, "item15_progression_text", "\n".join(lines), src, pn, "pdfplumber_table", note="verbatim; not mapped to any qualification")
        txt = " ".join(lines)
        parts = re.findall(r".+?\((?:Horizontal|Vertical)\)", txt)
        rest = clean(re.sub(r".+?\((?:Horizontal|Vertical)\)", "", txt))
        wrapped = len(parts) != len([l for l in lines if re.search(r"\((?:Horizontal|Vertical)\)", l)]) or any(
            not re.search(r"\((?:Horizontal|Vertical)\)$", l) and l not in rest for l in lines if parts)
        for i, part in enumerate(parts, 1):
            d = re.search(r"\((Horizontal|Vertical)\)", part).group(1)
            claims.append(dict(claim_no=i, claim_text_verbatim=clean(part), direction_label=d,
                               **prov(src, pn, "pdfplumber_table", "TRANSCRIBED", "")))
        if rest:
            claims.append(dict(claim_no=len(parts) + 1, claim_text_verbatim=rest, direction_label="UNLABELLED",
                               **prov(src, pn, "pdfplumber_table", "TRANSCRIBED", "no Horizontal/Vertical label in source text")))
    else:
        unresolved(qp, doc_type, "item15_progression_text", src, "item 15 row not found", 4)
    # age (9c)
    age = None
    for pn in (3, 4):
        for l in (pages[pn].extract_text() or "").split("\n"):
            m = re.match(r"^\s*c\.\s*Age:\s*(\d+)\s*years?\b", l)
            if m:
                age = (int(m.group(1)), pn)
    if age:
        add_fact(qp, doc_type, "item9c_min_age", age[0], src, age[1], "regex_line")
        res["age"] = age[0]
    else:
        unresolved(qp, doc_type, "item9c_min_age", src, "age line not found", 3)
    return res, claims


# ---------------------------------------------------------------- QF section 2 (NOS table)
NUMTOK = re.compile(r"^\d+(?:\.\d+)?%?$")
LABEL_TOK = re.compile(r"^(?:Core|Core/|Non-|Non-Core|Bridge/Core|Bridge/)$")
COLS = ["level", "credits", "theory", "practical", "ojt_mandatory", "ojt_recommended", "total_hours",
        "a_th", "a_pr", "a_proj", "a_viva", "a_total", "weight"]


def find_section2(pdf):
    for pn in (5, 6):
        ws = pdf.pages[pn - 1].extract_words()
        for i in range(len(ws) - 1):
            if ws[i]["text"] == "Section" and ws[i + 1]["text"] == "2:":
                return pn, ws[i]["top"]
    return None, None


def extract_nos_table(pdf, src, q, doc_type):
    qp = q["qp_code"]
    pn0, y0 = find_section2(pdf)
    if pn0 is None:
        unresolved(qp, doc_type, "nos_table", src, "Section 2 heading not found on pages 5-6", 5)
        return [], {}
    bands = []   # (page_no, page, words, ya, yb)
    for pn in (pn0, pn0 + 1):
        page = pdf.pages[pn - 1]
        ws = [w for w in page.extract_words() if not EMAIL.search(w["text"])]
        top = y0 if pn == pn0 else 0.0
        foot = next((w["top"] for w in ws if w["text"] == "Page" and w["top"] > top + 100), page.height)
        ys = hrules(page, 40, 300, top, foot)  # name/code/label columns only: credit cells may sit across a merged border
        if pn > pn0 and (not ys or ys[0] > 50):
            ys = [45.0] + ys  # continuation page: no top rule; start just below the repeated page banner
        for ya, yb in zip(ys, ys[1:]):
            bands.append((pn, ws, ya, yb))
        # a Section-2 table that ends on this page does not continue
        if any(w["text"] == "Duration" and nxt["text"] == "(in" for w, nxt in zip(ws, ws[1:])):
            break
    # label / code geometry pooled over all bands
    label_x1 = [w["x1"] for pn, ws, ya, yb in bands for w in ws if in_band(w, ya, yb) and LABEL_TOK.match(w["text"])]
    label_x0 = [w["x0"] for pn, ws, ya, yb in bands for w in ws if in_band(w, ya, yb) and LABEL_TOK.match(w["text"])]
    code_x0 = [w["x0"] for pn, ws, ya, yb in bands for w in ws if in_band(w, ya, yb)
               and re.match(r"^(AMH|DGT)/", w["text"])]
    if not label_x1 or not code_x0:
        unresolved(qp, doc_type, "nos_table", src, "NOS column geometry not found", pn0)
        return [], {}
    num_left, label_left, code_left = max(label_x1) + 1, min(label_x0) - 1, min(code_x0) - 1

    def numtoks(ws, ya, yb):
        return [w for w in ws if in_band(w, ya, yb) and w["x0"] >= num_left and NUMTOK.match(w["text"])]

    # column centres from clean main lines (13 numeric tokens on one line)
    centres = defaultdict(list)
    for pn, ws, ya, yb in bands:
        lines = defaultdict(list)
        for w in numtoks(ws, ya, yb):
            lines[round(w["top"] / 3)].append(w)
        for ln in lines.values():
            if len(ln) == 13:
                for name, w in zip(COLS, sorted(ln, key=lambda w: w["x0"])):
                    centres[name].append((w["x0"] + w["x1"]) / 2)
    if len(centres) < 13:
        unresolved(qp, doc_type, "nos_table", src, "no clean row to calibrate numeric columns", pn0)
        return [], {}
    cen = {k: sorted(v)[len(v) // 2] for k, v in centres.items()}
    spacing = min(abs(cen[COLS[i + 1]] - cen[COLS[i]]) for i in range(len(COLS) - 1))
    tol = spacing * 0.6

    # numeric tokens in a band with too few numerics (e.g. a digit wrapped past a row rule) are attached to the
    # nearest numeric-bearing band on the same page (within 16 pt of its main line) and flagged
    main_top = {}
    for i, (pn, ws, ya, yb) in enumerate(bands):
        tops = sorted(w["top"] for w in numtoks(ws, ya, yb))
        if len(tops) >= 10:
            main_top[i] = tops[len(tops) // 2]
    attached = defaultdict(list)
    for i, (pn, ws, ya, yb) in enumerate(bands):
        if i in main_top:
            continue
        for w in numtoks(ws, ya, yb):
            near = [(abs(w["top"] - t), j) for j, t in main_top.items() if bands[j][0] == pn and abs(w["top"] - t) <= 16]
            if near:
                attached[min(near)[1]].append(dict(w, _att=True))

    credit_rules = {pn: hrules(pdf.pages[pn - 1], cen["credits"] - 8, cen["credits"] + 8)
                    for pn in {b_[0] for b_ in bands}}
    rows, totals = [], {}
    for bi, (pn, ws, ya, yb) in enumerate(bands):
        nt = numtoks(ws, ya, yb) + attached.get(bi, [])
        if len(nt) < 10:
            continue
        band_words = [w for w in ws if in_band(w, ya, yb)]
        cells = defaultdict(list)
        stray = []
        for w in nt:
            c = (w["x0"] + w["x1"]) / 2
            name = min(cen, key=lambda k: abs(cen[k] - c))
            (cells[name].append(w) if abs(cen[name] - c) <= tol else stray.append(w))
        vals, flags, notes = {}, [], []
        for name, toks_ in cells.items():
            if any(t.get("_att") for t in toks_):
                flags.append(name)
                notes.append(f"{name}: digit(s) printed outside the row rule were attached by vertical proximity")
            elif any(min(abs((t["top"] + t["bottom"]) / 2 - ya), abs((t["top"] + t["bottom"]) / 2 - yb)) < 6 for t in toks_):
                flags.append(name)
                notes.append(f"{name}: value printed within 6 pt of a row rule; assigned to the row containing its centre")
        for name in COLS:
            toks = sorted(cells.get(name, []), key=lambda w: (round(w["top"]), w["x0"]))
            if not toks:
                vals[name] = ""
            elif len(toks) == 1:
                vals[name] = toks[0]["text"]
            elif all(re.fullmatch(r"\d{1,3}", t["text"]) for t in toks) and len({round(t["top"]) for t in toks}) == len(toks):
                vals[name] = "".join(t["text"] for t in toks)
                flags.append(name)
                notes.append(f"{name}: digits stacked on {len(toks)} lines were concatenated ({'+'.join(t['text'] for t in toks)})")
            else:
                vals[name] = ""
                flags.append(name)
                notes.append(f"{name}: {len(toks)} conflicting tokens, left blank")
        if vals["credits"] != "" and "credits" not in flags:
            open_edges = [e for e in (ya, yb) if e != 45.0 and not any(abs(e - r) <= 2.5 for r in credit_rules[pn])]
            if open_edges:
                flags.append("credits")
                notes.append("credits: the credit cell has no ruling line on its row boundary (merged border); assigned by position")
        if stray:
            flags.append("stray_tokens")
            notes.append(f"{len(stray)} numeric token(s) outside any column")
        lbl_words = [w for w in band_words if label_left <= w["x0"] < num_left - 1 and not NUMTOK.match(w["text"])]
        is_total = any(w["text"] == "Duration" and nxt["text"] == "(in" for w, nxt in zip(band_words, band_words[1:])) and not vals["level"]
        if is_total:
            totals = dict(page=pn, **{k: vals[k] for k in COLS}, flags=flags, notes=notes)
            continue
        name_left = min((w["x0"] for w in band_words if w["x0"] < code_left and not re.fullmatch(r"\d+", w["text"])), default=code_left)
        sno = [w["text"] for w in band_words if w["x1"] <= name_left - 1 and re.fullmatch(r"\d{1,2}", w["text"])]
        name = join_words([w for w in band_words if name_left - 2 <= w["x0"] < code_left])
        codezone = join_words([w for w in band_words if code_left <= w["x0"] < label_left])
        label_raw = join_words(lbl_words)
        mver = re.search(r"\bV\s*(\d+(?:\.\d+)?)\s*$", codezone)
        code_text = clean(codezone[:mver.start()]) if mver else clean(codezone)
        code = re.sub(r"\s+", "", code_text)
        is_bridge = "bridge" in (name + " " + label_raw + " " + codezone).lower()
        status = "PARSED_UNCERTAIN" if flags else "TRANSCRIBED"
        if is_bridge and not CODE_RE.match(code):
            code_out, ver_out = "", ""
        elif CODE_RE.match(code):
            code_out, ver_out = code, mver.group(1) if mver else ""
            if not mver:
                notes.append("no version stated in the Code & Version cell of this row")
        else:
            code_out, ver_out = "", ""
            flags.append("code"); notes.append("NOS code not parsed"); status = "UNRESOLVED"
        core = "Non-Core" if re.search(r"non", label_raw, re.I) else ("Core" if re.search(r"core", label_raw, re.I) else "")
        nums = {k: (None if vals[k] == "" else float(vals[k].rstrip("%"))) for k in COLS}
        hrs = [nums["theory"], nums["practical"], nums["ojt_mandatory"], nums["ojt_recommended"]]
        row_ok = ""
        if nums["total_hours"] is not None and all(h is not None for h in hrs):
            row_ok = abs(sum(hrs) - nums["total_hours"]) < 1e-9
        elif any(h is None for h in hrs):
            flags.append("hours"); notes.append("one or more hour cells blank"); status = "PARSED_UNCERTAIN" if status == "TRANSCRIBED" else status
        if vals["credits"] == "":
            notes.append("credit cell empty in the credit column of this row")
        hz = []
        if is_bridge and vals["credits"] != "":
            hz.append("BRIDGE_ROW_HAS_CREDIT_VALUE")
        rows.append(dict(
            qp_code=qp, nqr_code="", doc_type=doc_type, s_no=sno[0] if sno else "", nos_module_name=name,
            nos_code=code_out, nos_version=ver_out, core_label_raw=label_raw, core_or_noncore=core,
            nsqf_level=vals["level"], credits=vals["credits"], theory=vals["theory"], practical=vals["practical"],
            ojt_mandatory=vals["ojt_mandatory"], ojt_recommended=vals["ojt_recommended"], total_hours=vals["total_hours"],
            is_bridge=str(is_bridge).lower(), row_sum_ok=str(row_ok).lower() if row_ok != "" else "",
            hazard_flags=";".join(hz), uncertain_cells=";".join(dict.fromkeys(flags)),
            **prov(src, pn, "pdfplumber_words", status, "; ".join(notes))))
    return rows, totals


# ---------------------------------------------------------------- QP
def extract_qp(pdf, src, q):
    qp = q["qp_code"]
    out = dict(ref="", headers=[], compulsory=[])
    texts = {}
    for pn in range(1, 6):
        texts[pn] = (pdf.pages[pn - 1].extract_text() or "").split("\n")

    def find(pn, rx):
        # page 1 is the cover; the other labels sit on the QP parameter pages (searched 3-5)
        for p_ in ([1] if pn == 1 else range(3, 6)):
            for l in texts[p_]:
                m = re.match(rx, l.strip())
                if m:
                    return m.group(1), p_
        return None

    specs = [("qp_code_header", 1, r"QP Code:\s*(\S+)"), ("qp_cover_version", 1, r"Version:\s*(\S+)"),
             ("qp_cover_nsqf_level", 1, r"NSQF Level:\s*(\S+)"),
             ("qp_nsqf_level", 4, r"NSQF Level\s+(\S+)"), ("qp_nco_alignment_line", 4, r"(Aligned to NCO/ISCO/ISIC Code\s+.+)"),
             ("qp_document_version", 4, r"Version\s+(\S+)$"), ("reference_code_on_nqr", 4, r"Reference code on NQR\s+(\S+)"),
             ("nqr_version", 4, r"NQR Version\s+(\S+)")]
    for field, pn, rx in specs:
        hit = find(pn, rx)
        if hit is None:
            unresolved(qp, "QP", field, src, f"label line not found on pages {'1' if pn == 1 else '3-5'}", pn)
        else:
            v, pg = hit
            add_fact(qp, "QP", field, v, src, pg, "regex_line")
            if field == "reference_code_on_nqr":
                out["ref"] = v
    # compulsory NOS list
    start = None
    for pn in range(1, 5):
        for i, l in enumerate(texts[pn]):
            if l.strip() == "Compulsory NOS:":
                start = (pn, i)
    if start:
        items, cur = [], None
        lines = []
        for pn in range(start[0], 5):
            lines += [(pn, l) for l in texts[pn][(start[1] + 1 if pn == start[0] else 0):]]
        for pn, l in lines:
            s = l.strip()
            if s.startswith("Qualification Pack (QP) Parameters") or s.startswith("Applicable National"):
                break
            m = re.match(r"^(\d+)\.\s*((?:AMH|DGT)/(?:VSQ/)?N\d{4})\s*:\s*(.*)$", s)
            if m:
                cur = dict(no=int(m.group(1)), code=m.group(2), title=m.group(3), page=pn, lines=1)
                items.append(cur)
            elif cur is not None and s and not s.startswith("NSQC Approved") and s != "Qualification Pack":
                cur["title"] += " " + s
                cur["lines"] += 1
        for it in items:
            add_fact(qp, "QP", f"compulsory_nos_{it['no']}", f"{it['code']} | {clean(it['title'])}", src, it["page"],
                     "regex_line", "TRANSCRIBED", "" if it["lines"] == 1 else "title wrapped across lines and re-joined")
            out["compulsory"].append(it["code"])
    else:
        unresolved(qp, "QP", "compulsory_nos", src, "'Compulsory NOS:' list not found on pages 1-4", 3)
    # NOS parameter blocks
    for pn in range(5, len(pdf.pages) + 1):
        page = pdf.pages[pn - 1]
        txt = page.extract_text() or ""
        if "National Occupational Standards (NOS) Parameters" not in txt:
            continue
        lines = [l.strip() for l in txt.split("\n")]
        i0 = next(i for i, l in enumerate(lines) if l.startswith("National Occupational Standards (NOS) Parameters"))
        blk = lines[i0 + 1:]
        code = name_parts = None
        mcode = next((re.match(r"^NOS Code\s+(\S+)", l) for l in blk if l.startswith("NOS Code")), None)
        ic = next((i for i, l in enumerate(blk) if l.startswith("NOS Code")), None)
        isec = next((i for i, l in enumerate(blk) if l.startswith("Sector") and i > (ic or 0)), None)
        if not mcode or ic is None or isec is None:
            out["headers"].append(dict(qp_code=qp, nqr_code="", doc_type="QP", nos_code="", nos_name="", nsqf_level="",
                                       credits="", version="", **prov(src, pn, "regex_line", "UNRESOLVED", "NOS parameter block not parsed")))
            continue
        name_lines = [re.sub(r"^NOS Name\s*", "", l) for l in blk[ic + 1:isec]]
        name_lines = [l for l in name_lines if l]
        def lab(rx):
            for l in blk[isec:]:
                m = re.match(rx, l)
                if m:
                    return m.group(1)
            return ""
        level, cred, ver = lab(r"^NSQF Level\s+(\S+)"), lab(r"^Credits\s+(\S+)"), lab(r"^Version\s+(\S+)")
        miss = [n for n, v in (("level", level), ("credits", cred), ("version", ver)) if not v]
        status = "TRANSCRIBED" if not miss else "PARSED_UNCERTAIN"
        if not name_lines:
            status = "UNRESOLVED"
        note = ""
        if len(name_lines) > 1:
            note = "NOS name wrapped across lines and re-joined"
        if miss:
            note += ("; " if note else "") + "missing " + ",".join(miss)
        out["headers"].append(dict(qp_code=qp, nqr_code="", doc_type="QP", nos_code=mcode.group(1),
                                   nos_name=clean(" ".join(name_lines)), nsqf_level=level, credits=cred, version=ver,
                                   **prov(src, pn, "regex_line", status, note)))
    return out


# ---------------------------------------------------------------- CSV writing with last-line privacy screen
def write_csv(path, rows, cols):
    n_omit = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            for k in cols:
                if k == "source_sha256" and re.fullmatch(r"[0-9a-f]{64}", str(r.get(k, ""))):
                    continue  # a verified hash, not free text
                if k in r and has_pii(r[k]):
                    r[k] = OMIT
                    r["note"] = (str(r.get("note", "")) + "; " + OMIT).strip("; ")
                    n_omit += 1
            w.writerow(r)
    return n_omit


# ---------------------------------------------------------------- main
def main():
    if OUT.exists():
        print("STOP: output folder already exists:", OUT)
        sys.exit(2)
    srcs = load_sources()
    catalogue = {r["qp_code"]: r for r in csv.DictReader(open(CATALOGUE, encoding="utf-8-sig"))}
    OUT.mkdir(parents=True)

    quals, elig, nos_rows, qp_headers, claims, qf_res, qp_res, totals = [], [], [], [], [], {}, {}, {}
    jobs = [(q, "QF", q["qf"]) for q in QUALS] + [(QUALS[2], "QF_SECONDARY", IC_SECONDARY_QF)]
    for q, doc_type, rel in jobs:
        src = srcs[rel]
        with pdfplumber.open(src["path"]) as pdf:
            res, cl = extract_qf_section1(pdf, src, q, doc_type)
            er = extract_eligibility(pdf, src, q, doc_type, q["qp_code"])
            nr, tot = extract_nos_table(pdf, src, q, doc_type)
        key = (q["qp_code"], doc_type)
        qf_res[key] = res
        totals[key] = tot
        for r in er + nr + cl:
            r["nqr_code"] = res["nqr"]
            r["doc_type"] = doc_type
            r["qp_code"] = q["qp_code"]
        elig += er
        nos_rows += nr
        claims += cl
        if tot:
            for k in ("credits", "theory", "practical", "ojt_mandatory", "ojt_recommended", "total_hours"):
                add_fact(q["qp_code"], doc_type, f"nos_table_total_{k}", tot[k], src, tot["page"], "pdfplumber_words",
                         "PARSED_UNCERTAIN" if k in tot["flags"] else "TRANSCRIBED",
                         "; ".join(n for n in tot["notes"] if n.startswith(k)))
        else:
            unresolved(q["qp_code"], doc_type, "nos_table_totals_row", src, "totals row not isolated")
        add_fact(q["qp_code"], doc_type, "nos_table_row_count", len(nr), src, 5, "pdfplumber_words")
    for q in QUALS:
        src = srcs[q["qp"]]
        with pdfplumber.open(src["path"]) as pdf:
            qr = extract_qp(pdf, src, q)
        qp_res[q["qp_code"]] = qr
        for h in qr["headers"]:
            h["nqr_code"] = qr["ref"]
        qp_headers += qr["headers"]

    # fill nqr_code on facts
    for f in FACTS:
        if f["doc_type"] == "QP":
            f["nqr_code"] = qp_res[f["qp_code"]]["ref"]
        else:
            f["nqr_code"] = qf_res[(f["qp_code"], f["doc_type"])]["nqr"]

    # qualifications.csv (Section 1 fields, one row per qualification per QF copy)
    for (qpc, dt_), r in qf_res.items():
        src = srcs[next(q for q in QUALS if q["qp_code"] == qpc)["qf"] if dt_ == "QF" else IC_SECONDARY_QF]
        st = "TRANSCRIBED" if all(r.get(k) not in ("", None) for k in ("nqr", "level", "credits", "nco", "hours", "progression")) else "UNRESOLVED"
        h = r["hours"] or {}
        quals.append(dict(
            qp_code=qpc, nqr_code=r["nqr"], doc_type=dt_, qualification_name=next(q["name"] for q in QUALS if q["qp_code"] == qpc),
            previous_version_ref=r["prev_ref"], nsqf_level=r["level"], min_age=r.get("age", ""), credits=r["credits"],
            hours_theory=h.get("theory", ""), hours_practical=h.get("practical", ""),
            hours_ojt_mandatory=h.get("ojt_mandatory", ""), hours_ojt_recommended=h.get("ojt_recommended", ""),
            hours_total=h.get("total", ""), nco_2015_code=r["nco"], progression_text=r["progression"],
            **prov(src, "3-4", "pdfplumber_table", st, "row-level status; per-field status is in facts.csv")))

    # ---------------- reconciliation
    rec = []

    def add_rec(check, qp, result, inputs, evidence, note=""):
        rec.append(dict(check=check, qp_code=qp, result=result, inputs=inputs, evidence=evidence, note=note))

    def fnum(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def vnum(s):
        try:
            return float(str(s).replace("V", "").strip())
        except ValueError:
            return None

    fact_idx = {(f["qp_code"], f["doc_type"], f["field"]): f for f in FACTS}
    ref = lambda qp, dt_, field: f"facts.csv:{qp}/{dt_}/{field}"
    for q in QUALS:
        qpc, exp = q["qp_code"], q["exp"]
        r = qf_res[(qpc, "QF")]
        rows = [x for x in nos_rows if x["qp_code"] == qpc and x["doc_type"] == "QF"]
        tot = totals[(qpc, "QF")]
        # 1 hours
        hsum = sum(fnum(x["total_hours"]) or 0 for x in rows)
        i13 = (r["hours"] or {}).get("total")
        res = "UNRESOLVED" if i13 is None else ("MATCH" if hsum == i13 else "MISMATCH")
        add_rec("nos_hours_sum_vs_item13_total", qpc, res,
                dict(nos_hours_sum_incl_bridge=hsum, item13_total=i13, nos_table_totals_row=tot.get("total_hours"), expected=exp["hours"]),
                ["qf_nos.csv", ref(qpc, "QF", "item13_hours_total")],
                f"expected total {exp['hours']}: " + ("matches" if i13 == exp["hours"] else f"item 13 shows {i13}"))
        # 2 credits
        cvals = [fnum(x["credits"]) for x in rows]
        csum = sum(c for c in cvals if c is not None)
        blanks = [x["s_no"] or x["nos_code"] for x, c in zip(rows, cvals) if c is None]
        i10 = r["credits"] if r["credits"] != "" else None
        res = "UNRESOLVED" if i10 is None else ("MATCH" if csum == i10 else "MISMATCH")
        add_rec("nos_credits_sum_vs_item10", qpc, res,
                dict(nos_credits_sum=csum, rows_with_blank_credit=blanks, item10=i10, nos_table_totals_row=tot.get("credits"), expected=exp["credits"]),
                ["qf_nos.csv", ref(qpc, "QF", "item10_credits")],
                "blank credit cells are not counted (not guessed); " + ("sum differs from item 10" if res == "MISMATCH" else ""))
        cat = catalogue.get(qpc, {})
        catc = fnum(cat.get("credits"))
        res = "UNRESOLVED" if i10 is None or catc is None else ("MATCH" if i10 == catc else "MISMATCH")
        add_rec("item10_vs_catalogue_credits", qpc, res, dict(item10=i10, catalogue=cat.get("credits"), expected=exp["credits"]),
                [ref(qpc, "QF", "item10_credits"), "approved_qualifications_parsed.csv"])
        # 3 row internal
        bad = [x["nos_code"] or x["s_no"] for x in rows if x["row_sum_ok"] == "false"]
        unk = [x["nos_code"] or x["s_no"] for x in rows if x["row_sum_ok"] == ""]
        res = "UNRESOLVED" if unk else ("MISMATCH" if bad else "MATCH")
        add_rec("row_internal_hours_sum", qpc, res, dict(rows=len(rows), failing_rows=bad, rows_not_checkable=unk), ["qf_nos.csv"])
        # item 13 internal
        h = r["hours"] or {}
        if h:
            s = h["theory"] + h["practical"] + h["ojt_mandatory"] + h["ojt_recommended"]
            add_rec("item13_internal_sum", qpc, "MATCH" if s == h["total"] else "MISMATCH", dict(sum=s, total=h["total"]), [ref(qpc, "QF", "item13_hours_total")])
        # 4 QP vs QF NOS sets
        qrow = qp_res[qpc]
        qf_codes = {x["nos_code"] for x in rows if x["nos_code"]}
        qp_codes = {h_["nos_code"] for h_ in qrow["headers"] if h_["nos_code"]}
        comp = set(qrow["compulsory"])
        res = "MATCH" if qf_codes == qp_codes else "MISMATCH"
        add_rec("qp_vs_qf_nos_code_sets", qpc, res,
                dict(qf_only=sorted(qf_codes - qp_codes), qp_headers_only=sorted(qp_codes - qf_codes),
                     qp_compulsory_list_vs_qf=dict(equal=comp == qf_codes, qf_only=sorted(qf_codes - comp), qp_only=sorted(comp - qf_codes)),
                     qp_compulsory_vs_qp_headers_equal=comp == qp_codes),
                ["qf_nos.csv", "qp_nos_headers.csv"])
        diffs = []
        for x in rows:
            hh = next((h_ for h_ in qrow["headers"] if h_["nos_code"] == x["nos_code"] and x["nos_code"]), None)
            if not hh:
                continue
            for fld_qf, fld_qp, conv in (("nos_version", "version", vnum), ("credits", "credits", fnum), ("nsqf_level", "nsqf_level", fnum)):
                a, b = conv(x[fld_qf]), conv(hh[fld_qp])
                if a is None or b is None:
                    diffs.append(dict(code=x["nos_code"], field=fld_qf, qf=x[fld_qf], qp=hh[fld_qp], issue="not stated in one source"))
                elif a != b:
                    diffs.append(dict(code=x["nos_code"], field=fld_qf, qf=x[fld_qf], qp=hh[fld_qp], issue="differs"))
        add_rec("qp_vs_qf_nos_attributes", qpc, "MISMATCH" if any(d["issue"] == "differs" for d in diffs) else ("UNRESOLVED" if diffs else "MATCH"),
                dict(differences=diffs), ["qf_nos.csv", "qp_nos_headers.csv"])
        # 5 catalogue
        g = lambda f: (fact_idx.get((qpc, "QP", f)) or {}).get("value")
        add_rec("catalogue_nqr_code", qpc,
                "MATCH" if cat.get("nqr_code") == r["nqr"] == qrow["ref"] else "MISMATCH",
                dict(catalogue=cat.get("nqr_code"), qf_item5=r["nqr"], qp_reference_code=qrow["ref"]), ["approved_qualifications_parsed.csv", ref(qpc, "QF", "nqr_code")])
        add_rec("catalogue_nsqf_level", qpc,
                "MATCH" if fnum(cat.get("nsqf_level")) == fnum(r["level"]) == fnum(g("qp_nsqf_level")) else "MISMATCH",
                dict(catalogue=cat.get("nsqf_level"), qf_item6=r["level"], qp=g("qp_nsqf_level")), ["approved_qualifications_parsed.csv"])
        add_rec("catalogue_notional_hours", qpc, "UNRESOLVED" if i13 is None else ("MATCH" if fnum(cat.get("notional_hours")) == i13 else "MISMATCH"),
                dict(catalogue=cat.get("notional_hours"), qf_item13_total=i13), ["approved_qualifications_parsed.csv"])
        add_rec("catalogue_qp_version", qpc, "SEMANTIC_AMBIGUITY",
                dict(catalogue_qp_version=cat.get("qp_version"), qp_document_version=g("qp_document_version"), qp_nqr_version=g("nqr_version"),
                     qf_item5_version=(fact_idx.get((qpc, "QF", "item5_version")) or {}).get("value")),
                ["approved_qualifications_parsed.csv", ref(qpc, "QP", "qp_document_version")],
                "catalogue 'QP Version' may denote the NQR version rather than the QP document version; neither match nor mismatch is asserted")
        # 7 lead values
        add_rec("lead_nco_code", qpc, "MATCH" if r["nco"] == exp["nco"] else ("UNRESOLVED" if not r["nco"] else f"MISMATCH (found {r['nco']})"),
                dict(expected=exp["nco"], found=r["nco"]), [ref(qpc, "QF", "nco_2015_code")])
        add_rec("lead_nsqf_level", qpc, "MATCH" if fnum(r["level"]) == fnum(exp["level"]) else ("UNRESOLVED" if not r["level"] else f"MISMATCH (found {r['level']})"),
                dict(expected=exp["level"], found=r["level"]), [ref(qpc, "QF", "nsqf_level")])
        a = r.get("age")
        add_rec("lead_min_age", qpc, "UNRESOLVED" if a is None else ("MATCH" if a == exp["age"] else f"MISMATCH (found {a})"),
                dict(expected=exp["age"], found=a), [ref(qpc, "QF", "item9c_min_age")])
        found = [x["nos_code"] for x in rows if x["nos_code"]]
        add_rec("lead_exact_nos_set", qpc, "MATCH" if set(found) == set(exp["nos"]) and len(found) == len(set(found)) else "MISMATCH",
                dict(expected=sorted(exp["nos"]), found_in_qf=sorted(found), missing=sorted(set(exp["nos"]) - set(found)), extra=sorted(set(found) - set(exp["nos"]))),
                ["qf_nos.csv"])
        pv = r["prev_ref"]
        add_rec("previous_version_ref_recorded", qpc, "MATCH" if pv else "UNRESOLVED", dict(previous_version_ref=pv, treatment="predecessor reference; not a conflict"),
                [ref(qpc, "QF", "previous_version_ref")])
    # specialised lead: N2301
    rows = [x for x in nos_rows if x["qp_code"] == "AMH/Q2301" and x["doc_type"] == "QF"]
    n2301 = next((x for x in rows if x["nos_code"] == "AMH/N2301"), None)
    bridge = next((x for x in rows if x["is_bridge"] == "true"), None)
    ok = bool(n2301 and bridge and fnum(n2301["total_hours"]) == 147 and fnum(bridge["total_hours"]) == 3)
    add_rec("lead_specialized_n2301_hours", "AMH/Q2301", "MATCH" if ok else "MISMATCH",
            dict(expected="147 h NOS + 3 h bridge", qf_n2301_total_hours=n2301 and n2301["total_hours"], qf_bridge_total_hours=bridge and bridge["total_hours"]),
            ["qf_nos.csv"], "reports what the QF shows")
    add_rec("lead_specialized_n2301_150h_conflict", "AMH/Q2301", "NOT PERFORMED — source unavailable",
            dict(note="NQR page with the competing 150 h figure was not acquired"), [])
    # hazards
    for qpc in [q["qp_code"] for q in QUALS]:
        rows = [x for x in nos_rows if x["qp_code"] == qpc and x["doc_type"] == "QF"]
        br = next((x for x in rows if x["is_bridge"] == "true"), None)
        nxt = rows[rows.index(br) + 1] if br and rows.index(br) + 1 < len(rows) else None
        stacked = [(x["nos_code"] or x["s_no"], x["uncertain_cells"]) for x in rows if x["uncertain_cells"]]
        add_rec("layout_hazards", qpc, "UNRESOLVED" if stacked else "MATCH",
                dict(bridge_row_present=br is not None,
                     bridge_row_credit_cell=(br["credits"] or "empty") if br else "n/a",
                     next_row_credit_cell=(nxt["credits"] or "empty") if nxt else "n/a",
                     rows_with_alignment_flags=stacked),
                ["qf_nos.csv"], "flag only; values not corrected. UNRESOLVED here means rows carry PARSED_UNCERTAIN cells that need human review")
    for q in QUALS:
        qpc = q["qp_code"]
        snos = [int(x["s_no"]) for x in nos_rows if x["qp_code"] == qpc and x["doc_type"] == "QF" and x["s_no"].isdigit()]
        gaps = sorted(set(range(1, max(snos) + 1)) - set(snos)) if snos else []
        add_rec("nos_table_sno_sequence", qpc, "UNRESOLVED" if gaps else "MATCH", dict(s_nos=snos, missing_s_nos=gaps),
                ["qf_nos.csv"], "S.No values are printed in the source; a gap is reported, not repaired" if gaps else "")
    # 6 IC copies
    ps = [(f["field"], f["value"]) for f in FACTS if f["qp_code"] == "AMH/Q0103" and f["doc_type"] == "QF"]
    ss = {f["field"]: f["value"] for f in FACTS if f["qp_code"] == "AMH/Q0103" and f["doc_type"] == "QF_SECONDARY"}
    diffs = [dict(field=k, nqr_copy=v, amhssc_copy=ss.get(k)) for k, v in ps if str(ss.get(k)) != str(v)]
    cols = ["nos_module_name", "nos_code", "nos_version", "core_or_noncore", "nsqf_level", "credits", "theory", "practical",
            "ojt_mandatory", "ojt_recommended", "total_hours", "is_bridge"]
    a_rows = [x for x in nos_rows if x["qp_code"] == "AMH/Q0103" and x["doc_type"] == "QF"]
    b_rows = [x for x in nos_rows if x["qp_code"] == "AMH/Q0103" and x["doc_type"] == "QF_SECONDARY"]
    if len(a_rows) != len(b_rows):
        diffs.append(dict(field="nos_row_count", nqr_copy=len(a_rows), amhssc_copy=len(b_rows)))
    for x, y in zip(a_rows, b_rows):
        diffs += [dict(field=f"nos_row[{x['s_no']}].{c}", nqr_copy=x[c], amhssc_copy=y[c]) for c in cols if x[c] != y[c]]
    ea = [(x["s_no"], x["raw_academic_or_skill"], x["raw_required_experience"]) for x in elig if x["qp_code"] == "AMH/Q0103" and x["doc_type"] == "QF"]
    eb = [(x["s_no"], x["raw_academic_or_skill"], x["raw_required_experience"]) for x in elig if x["qp_code"] == "AMH/Q0103" and x["doc_type"] == "QF_SECONDARY"]
    if ea != eb:
        diffs.append(dict(field="item9_eligibility_rows", nqr_copy=len(ea), amhssc_copy=len(eb)))
    add_rec("inline_checker_qf_copies_identical", "AMH/Q0103", "MATCH" if not diffs else "MISMATCH",
            dict(fields_compared=len(ps), nos_rows_compared=len(a_rows), differences=diffs),
            ["facts.csv", "qf_nos.csv", "eligibility_rows.csv"], "Section 1 and Section 2 values compared; SHA-256 of the two files differ by construction")

    # ---------------- write outputs
    n_omit = 0
    fact_cols = ["qp_code", "nqr_code", "doc_type", "field", "value"] + PROV
    n_omit += write_csv(OUT / "facts.csv", FACTS, fact_cols)
    n_omit += write_csv(OUT / "qualifications.csv", quals,
                        ["qp_code", "nqr_code", "doc_type", "qualification_name", "previous_version_ref", "nsqf_level", "min_age", "credits",
                         "hours_theory", "hours_practical", "hours_ojt_mandatory", "hours_ojt_recommended", "hours_total",
                         "nco_2015_code", "progression_text"] + PROV)
    n_omit += write_csv(OUT / "qf_nos.csv", nos_rows,
                        ["qp_code", "nqr_code", "doc_type", "s_no", "nos_module_name", "nos_code", "nos_version", "core_label_raw",
                         "core_or_noncore", "nsqf_level", "credits", "theory", "practical", "ojt_mandatory", "ojt_recommended",
                         "total_hours", "is_bridge", "row_sum_ok", "hazard_flags", "uncertain_cells"] + PROV)
    n_omit += write_csv(OUT / "qp_nos_headers.csv", qp_headers,
                        ["qp_code", "nqr_code", "doc_type", "nos_code", "nos_name", "nsqf_level", "credits", "version"] + PROV)
    age_rows = [dict(qp_code=f["qp_code"], nqr_code=f["nqr_code"], doc_type=f["doc_type"], row_type="age_9c", s_no="",
                     raw_academic_or_skill="", raw_required_experience="", raw_row_text=f"Age: {f['value']} years", min_education="",
                     prior_nsqf_level="", experience_years="", relevance_qualifier="", min_age=f["value"],
                     **{k: f[k] for k in PROV}) for f in FACTS if f["field"] == "item9c_min_age" and f["value"] != ""]
    n_omit += write_csv(OUT / "eligibility_rows.csv", elig + age_rows,
                        ["qp_code", "nqr_code", "doc_type", "row_type", "s_no", "raw_academic_or_skill", "raw_required_experience", "raw_row_text",
                         "min_education", "prior_nsqf_level", "experience_years", "relevance_qualifier", "min_age"] + PROV)
    n_omit += write_csv(OUT / "progression_claims.csv", claims,
                        ["qp_code", "nqr_code", "doc_type", "claim_no", "claim_text_verbatim", "direction_label"] + PROV)
    rec_json = json.dumps(dict(run_id=RUN_ID, checks=rec), indent=2, ensure_ascii=False, default=str)
    if has_pii(rec_json):
        rec_json = json.dumps(dict(run_id=RUN_ID, error=OMIT), indent=2)
        n_omit += 1
    (OUT / "reconciliation.json").write_text(rec_json, encoding="utf-8")

    # ---------------- report
    status_counts = defaultdict(lambda: defaultdict(int))
    for rows_ in (FACTS, nos_rows, elig, qp_headers, claims, quals):
        for r_ in rows_:
            if r_.get("doc_type") != "QF_SECONDARY":
                status_counts[r_["qp_code"]][r_["extraction_status"]] += 1
    write_report(rec, status_counts, srcs, n_omit)
    for q in QUALS:
        c = status_counts[q["qp_code"]]
        print(f"{q['qp_code']}: TRANSCRIBED={c['TRANSCRIBED']} PARSED_UNCERTAIN={c['PARSED_UNCERTAIN']} UNRESOLVED={c['UNRESOLVED']}")
    print("privacy-screen omissions:", n_omit)
    print("outputs:", OUT)


def write_report(rec, counts, srcs, n_omit):
    quals = [q["qp_code"] for q in QUALS]
    short = lambda c: c.split("/")[-1]
    by = defaultdict(list)
    for r in rec:
        by[r["check"]].append(r)
    confirmed, discrep, review = [], [], []
    for check, rs in by.items():
        ok = [short(r["qp_code"]) for r in rs if r["result"] == "MATCH"]
        if ok:
            confirmed.append(f"- `{check}`: MATCH for {', '.join(ok)}" + (" (all 4)" if len(ok) == len(quals) else ""))
        for r in rs:
            res = r["result"]
            if res.startswith("MISMATCH"):
                inp = json.dumps(r["inputs"], ensure_ascii=False, default=str)
                discrep.append(f"- `{check}` ({short(r['qp_code'])}): {res} — {inp[:420]}")
            elif res != "MATCH":
                extra = f" — {r['note']}" if r["note"] else ""
                if check in ("layout_hazards", "nos_table_sno_sequence"):
                    extra = " — " + json.dumps(r["inputs"], ensure_ascii=False, default=str)[:260] + (f"; {r['note']}" if r["note"] else "")
                review.append(f"- `{check}` ({short(r['qp_code'])}): {res}{extra}")
    md = [f"# Reconciliation report — extraction run {RUN_ID}", "",
          "Four AMHSSC qualifications (QF Sections 1-2, QP headers and NOS parameter blocks). Competency/PC/KU/GS text, matching and graph logic are out of scope. "
          "Nothing below has been resolved, corrected or chosen between; discrepancies are reported as found.", "",
          "| QP | TRANSCRIBED | PARSED_UNCERTAIN | UNRESOLVED |", "|---|---|---|---|"]
    md += [f"| {c} | {counts[c]['TRANSCRIBED']} | {counts[c]['PARSED_UNCERTAIN']} | {counts[c]['UNRESOLVED']} |" for c in quals]
    md += ["", "(Counts are rows across all output CSVs, excluding the secondary Inline Checker QF copy.)", "",
           "## Confirmed facts", *confirmed, "",
           "## Discrepancies", *(discrep or ["- none"]), "",
           "## Unresolved or needs review", *review, "",
           "## Tools, method and limits",
           f"- Python {sys.version.split()[0]}; pdfplumber {pdfplumber.__version__} (tables, words and ruling lines) did all extraction; pypdf {pypdf.__version__} was present but not needed, so no fact used `pypdf_layout`. "
           "No package was installed. All 9 source PDFs matched their MANIFEST SHA-256 before use. Run with `-B -I`; no bytecode written.",
           "- `PARSED_UNCERTAIN` = heuristic or ambiguous alignment (reason in `note`). Digits wrapped across lines, credits printed on a row rule and merged eligibility cells are flagged, not repaired.",
           f"- Privacy: the extraction script opens only QF pages 3-6 (Section 1, Section 2) and the QP cover, pages 2-5 and NOS-parameter pages; QF pages 1-2, item 22 and annexures are never read for values. "
           f"Every output value was screened for email/phone patterns ({n_omit} omission(s)). The screen is heuristic and is not a guarantee.",
           "- During parser development, a one-off page map scanned every QF/QP page in memory for heading markers (printing only marker names and page numbers), and short in-scope table windows plus QP pages 1-5 lines (including one page of PC text) were viewed on the console with email/phone lines filtered out. None of that text is stored in any output.",
           "- Outputs are local-only and untracked. Reuse and redistribution permissions for the source documents are unresolved; do not publish or commit.",
           ]
    (OUT / "RECONCILIATION_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
