"""Skill Adjacency Graph - official source acquisition helper (run 2026-10-30).

Phased CLI: p1 | parse | p2 | cross | p3 | outputs.  State lives in the run dir (_state.json).
Extracted text is held in memory only; never written to disk or printed.
Run with: python -B -I acquire_2026-10-30.py <phase>
"""
import sys
sys.dont_write_bytecode = True
import os, re, csv, json, time, hashlib, datetime, zoneinfo, functools
import urllib.parse as up
import urllib.robotparser as rp
import httpx
from pypdf import PdfReader
from bs4 import BeautifulSoup

UA = "SkillAdjacencyGraph-research/0.1 (hackathon data acquisition; contact: local user)"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUN_ID = os.path.basename(__file__)[len("acquire_"):-3]
RAW = os.path.join(ROOT, "data", "raw", RUN_ID)
PROC = os.path.join(ROOT, "data", "processed", "acquisition_" + RUN_ID)
STATE_PATH = os.path.join(RAW, "_state.json")
A1_BASE = "https://www.sscamh.com/en/approved-qualification"
SC = "https://www.sscamh.com/public/backend-assets/js/ckfinder/files/"
HOSTS = {"sscamh": "https://www.sscamh.com", "nqr": "https://www.nqr.gov.in", "dge": "https://dge.gov.in"}

EXP = {
    "SMO": dict(name="sewing machine operator", qp="AMH/Q0301", nqr="QG-2.5-AP-01866-2024-V1.1-AMHSSC", ver="4.0",
                nsqf=2.5, hours=300, parts=[90, 210], credits=10, nco="8153.0101", age=18),
    "SSMO": dict(name="specialized sewing machine operator", qp="AMH/Q2301", nqr="QG-3.5-AP-01871-2024-V1.1-AMHSSC",
                 ver="4.0", nsqf=3.5, hours=420, parts=[150, 270], credits=14, nco="8153.0103", age=18),
    "IC": dict(name="inline checker", qp="AMH/Q0103", nqr="QG-3.5-AP-03570-2025-V2-AMHSSC", ver="4.0", nsqf=3.5,
               hours=420, parts=[150, 240, 30], credits=14, nco="7543.0301", age=18),
    "PS": dict(name="production supervisor", qp="AMH/Q2101", nqr="QG-05-AP-01777-2024-V2-AMHSSC", ver="4.0", nsqf=5.0,
               hours=570, parts=[180, 330, 60], credits=19, nco="3122.3551", age=20),
}
# id, name, phase, gate, org, url, subdir, kind(pdf|html), qual, doctype(QP|QF|-), catalogue (qp code, link col)
ITEMS = [
    ("A1", "AMHSSC Approved Qualifications page", 1, "yes", "AMHSSC", A1_BASE, "amhssc/catalogue", "html", None, "-", None),
    ("A1b", "AMHSSC Approved Qualification List PDF", 1, "optional", "AMHSSC", SC + "Approved%20Qualification%20List.pdf", "amhssc/catalogue", "pdf", None, "LIST", None),
    ("A2", "Sewing Machine Operator QP", 1, "yes", "AMHSSC", SC + "Sewing%20Machine%20Operator.pdf", "amhssc/qp", "pdf", "SMO", "QP", ("AMH/Q0301", "qp")),
    ("A3", "Sewing Machine Operator QF", 1, "yes", "AMHSSC", SC + "Q%20FILE%20Sewing%20Machine%20Operator.pdf", "amhssc/qf", "pdf", "SMO", "QF", ("AMH/Q0301", "qf")),
    ("A4", "Specialized Sewing Machine Operator QP", 1, "yes", "AMHSSC", SC + "Specialized%20Sewing%20Machine%20Operator.pdf", "amhssc/qp", "pdf", "SSMO", "QP", ("AMH/Q2301", "qp")),
    ("A5", "Specialized Sewing Machine Operator QF", 1, "yes", "AMHSSC", SC + "Q%20FILE%20Specialized%20Sewing%20Machine%20Operator%281%29.pdf", "amhssc/qf", "pdf", "SSMO", "QF", ("AMH/Q2301", "qf")),
    ("B1", "Inline Checker Sewing QP", 2, "no", "AMHSSC", SC + "Model%20Curriculum/Model%20Curriculum%201/Model%20Curriculum%202/Qualification%20Pack/Inline%20Checker%20Sewing%20QP%20File.pdf", "amhssc/qp", "pdf", "IC", "QP", ("AMH/Q0103", "qp")),
    ("B2", "Inline Checker Sewing QF v4.0 (NQR copy)", 2, "no", "NQR", "https://www.nqr.gov.in/qualification/file/Q%20FILE%20Inline%20Checker%20Sewing%20Version%204.0.pdf", "nqr/qf", "pdf", "IC", "QF", None),
    ("B2b", "Inline Checker QF (AMHSSC copy)", 2, "optional", "AMHSSC", SC + "Inline%20Checker%20Sewing%20V4_0.pdf", "amhssc/qf", "pdf", "IC", "QF", ("AMH/Q0103", "qf")),
    ("B3", "Production Supervisor Sewing QP", 2, "no", "AMHSSC", SC + "Model%20Curriculum/Model%20Curriculum%201/Model%20Curriculum%202/Qualification%20Pack/Qualification%20Pack%201/Production%20Supervisor%20Sewing%20QP%20File.pdf", "amhssc/qp", "pdf", "PS", "QP", ("AMH/Q2101", "qp")),
    ("B4", "Production Supervisor Sewing QF v4.0", 2, "no", "AMHSSC", SC + "Production%20Supervisor-%20Sewing%20V4_0.pdf", "amhssc/qf", "pdf", "PS", "QF", ("AMH/Q2101", "qf")),
    ("C1", "NQR record Inline Checker", 2, "no", "NQR", "https://www.nqr.gov.in/qualifications/13152", "nqr/html", "html", "IC", "NQR", None),
    ("C2", "NQR record Production Supervisor", 2, "no", "NQR", "https://www.nqr.gov.in/qualifications/12774", "nqr/html", "html", "PS", "NQR", None),
    ("C3", "NQR record Specialized Sewing Machine Operator", 2, "no", "NQR", "https://www.nqr.gov.in/public/qualifications/10424", "nqr/html", "html", "SSMO", "NQR", None),
    ("D1", "NCO-2015 Vol I PDF", 3, "no", "DGE", "https://dge.gov.in/dge/sites/default/files/2022-07/National_Classification_of_Occupations_Vol_I-2015.pdf", "dge/nco", "pdf", None, "NCO", None),
    ("D1-src", "DGE NCO-2015 landing page", 3, "no", "DGE", "https://dge.gov.in/nco-2015", "dge/nco", "html", None, "-", None),
]
NCO_TARGETS = ["8153.0101", "8153.0103", "7543.0301", "3122.3551"]
NQR_CODE_RE = re.compile(r"QG-[\d.]+-[A-Z]+-\d+-\d{4}-V[\d.]+-[A-Z]+")
PRIV_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?:\+91[\s-]?|0)?\d{10}\b|\b(?:\+91|0)[\s-]?\d{2,5}[\s-]\d{6,8}\b|spoc|contact|mobile|e-?mail|phone|tel\b", re.I)

# ---------------------------------------------------------------- state
def now_iso():
    return datetime.datetime.now(IST).isoformat(timespec="seconds")

def load():
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH, encoding="utf-8"))
    return {"items": {}, "last_req": {}, "c4_requests": 0, "gates": {}, "nco": {}, "run_notes": []}

def save(st):
    json.dump(st, open(STATE_PATH, "w", encoding="utf-8"), indent=1, default=str)

def say(*a):
    print(*a, flush=True)

# ---------------------------------------------------------------- http
def throttle(st, host):
    last = st["last_req"].get(host, 0)
    gap = time.time() - last
    if gap < 2.1:
        time.sleep(2.1 - gap)

def chain(st, client, url, counter=None):
    """One request plus manual redirect hops; every hop throttled per host."""
    nreq = 0
    cur = url
    for _ in range(6):
        host = up.urlsplit(cur).netloc.lower()
        throttle(st, host)
        try:
            r = client.get(cur)
        except Exception as e:  # timeout / connection error
            st["last_req"][host] = time.time()
            nreq += 1
            if counter is not None:
                st[counter] += 1
            return dict(error=type(e).__name__ + ": " + str(e)[:150], status=None, final_url=cur, nreq=nreq)
        st["last_req"][host] = time.time()
        nreq += 1
        if counter is not None:
            st[counter] += 1
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            cur = up.urljoin(cur, r.headers["location"])
            continue
        return dict(error=None, status=r.status_code, final_url=cur, ctype=r.headers.get("content-type", ""),
                    body=r.content, nreq=nreq)
    return dict(error="too many redirects", status=None, final_url=cur, nreq=nreq)

def http_get(st, url, counter=None, cap=None):
    delays = [5, 15, 45]
    total = 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=False) as c:
        for attempt in range(4):
            if cap is not None and st[counter] >= cap:
                return dict(error="request cap reached", status=None, final_url=url, nreq=total, total_requests=total)
            res = chain(st, c, url, counter)
            total += res["nreq"]
            retry = res["error"] or (res["status"] is not None and (res["status"] >= 500 or res["status"] == 429))
            if retry and attempt < 3:
                time.sleep(delays[attempt])
                continue
            res["total_requests"] = total
            return res

# ---------------------------------------------------------------- files
def safe_name(url):
    n = up.unquote(up.urlsplit(url).path.rsplit("/", 1)[-1]) or "index"
    n = re.sub(r'[<>:"/\\|?*]', "_", n)
    return n

def save_file(subdir, name, data):
    d = os.path.join(RAW, *subdir.split("/"))
    os.makedirs(d, exist_ok=True)
    base, ext = os.path.splitext(name)
    p, i = os.path.join(d, name), 2
    while os.path.exists(p):
        p = os.path.join(d, f"{base}__{i}{ext}")
        i += 1
    with open(p, "xb") as f:
        f.write(data)
    return p

def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")

@functools.lru_cache(maxsize=8)
def pdf_pages(path):
    rd = PdfReader(path)
    out = []
    for pg in rd.pages:
        try:
            out.append(pg.extract_text() or "")
        except Exception:
            out.append("")
    return out

def pdf_open(path):
    return len(PdfReader(path).pages)

def html_text(path):
    soup = BeautifulSoup(open(path, "rb").read(), "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return title, soup.get_text(" ", strip=True)

def norm(t):
    t = re.sub(r"\s+", " ", t).lower()
    return t

def norm_codes(t):
    t = re.sub(r"\s*/\s*", "/", t)
    t = re.sub(r"\s*-\s*", "-", t)
    return t

def words(t):
    return re.sub(r"[^a-z0-9. ]+", " ", t.lower()).replace("  ", " ")

def snippet(text, needle, w=40):
    i = text.lower().find(needle.lower())
    if i < 0:
        return None
    s = re.sub(r"\s+", " ", text[max(0, i - w): i + len(needle) + w])[:200]
    if PRIV_RE.search(s):
        return "snippet omitted - privacy screen"
    return s

# ---------------------------------------------------------------- robots
def robots_step(st):
    for key, base in HOSTS.items():
        rid = "R-" + key
        if rid in st["items"]:
            continue
        url = base + "/robots.txt"
        res = http_get(st, url)
        it = new_item(rid, f"robots.txt {key}", 0, "no", key.upper(), url, "robots")
        fill_transport(it, res)
        if res.get("status") in (404, 410):
            it.update(status_override="PASS", reason="absent - treated as no restrictions (standard convention)")
        elif res.get("status") and 200 <= res["status"] < 300:
            p = save_file("robots", f"{key}__robots.txt", res["body"])
            it["local"] = rel(p)
            it.update(status_override="PASS", reason="retrieved and parsed")
        else:
            it.update(status_override="FAIL_HTTP", reason="robots.txt unverifiable")
        st["items"][rid] = it
        say(rid, it["status_override"], it["http_status"])
        save(st)

def robots_allows(st, url):
    host = up.urlsplit(url).netloc.lower()
    key = {"www.sscamh.com": "sscamh", "www.nqr.gov.in": "nqr", "dge.gov.in": "dge"}[host]
    r = st["items"].get("R-" + key)
    if not r or r["status_override"] == "FAIL_HTTP":
        return False, "robots.txt unverifiable"
    if not r.get("local"):
        return True, ""
    p = rp.RobotFileParser()
    p.parse(open(os.path.join(ROOT, r["local"]), encoding="utf-8", errors="replace").read().splitlines())
    ok = p.can_fetch(UA, url)
    return ok, "" if ok else "disallowed by robots.txt"

# ---------------------------------------------------------------- items
def new_item(iid, name, phase, gate, org, url, sub, kind=None, qual=None, doctype="-", cat=None):
    return dict(item_id=iid, name=name, phase=phase, gate=gate, org=org, url=url, subdir=sub, kind=kind, qual=qual,
                doctype=doctype, cat=cat, catalogue_raw=None, final_url="", local="", retrieved_at=now_iso(),
                http_status="", ctype="", size="", sha="", pages="", status_override=None, reason="", notes="",
                checks={}, extra_disc=[], xchecks={}, snippets=[], limitations=[], identity=None, readable=None,
                catalogue_xcheck=None)

def fill_transport(it, res):
    it["retrieved_at"] = now_iso()
    it["final_url"] = res.get("final_url", "")
    it["http_status"] = res.get("status") or ""
    it["ctype"] = res.get("ctype", "")
    it["requests_used"] = res.get("total_requests")
    if res.get("error"):
        it["notes"] = res["error"]
    b = res.get("body")
    if b is not None:
        it["size"] = len(b)
        it["sha"] = hashlib.sha256(b).hexdigest()

def acquire(st, spec):
    iid, name, phase, gate, org, url, sub, kind, qual, dt, cat = spec
    if iid in st["items"]:
        return
    it = new_item(iid, name, phase, gate, org, url, sub, kind, qual, dt, cat)
    st["items"][iid] = it
    ok, why = robots_allows(st, url)
    if not ok:
        it.update(status_override="SKIPPED", reason=why)
        say(iid, "SKIPPED", why)
        return save(st)
    res = http_get(st, url)
    fill_transport(it, res)
    s = res.get("status")
    if res.get("error") or s is None or not (200 <= s < 300):
        it.update(status_override="FAIL_HTTP", reason=res.get("error") or f"HTTP {s}")
        say(iid, "FAIL_HTTP", it["reason"])
        return save(st)
    body = res["body"]
    if len(body) == 0:
        it.update(status_override="FAIL_UNREADABLE", reason="0-byte response")
        return save(st)
    if kind == "pdf" and not body.startswith(b"%PDF-"):
        p = save_file(sub, os.path.splitext(safe_name(url))[0] + "__invalid_response.html", body)
        it.update(status_override="FAIL_NOT_PDF", reason="response is not a PDF (saved as invalid_response)",
                  local=rel(p), file_type="html")
        say(iid, "FAIL_NOT_PDF")
        return save(st)
    p = save_file(sub, safe_name(url) + ("" if safe_name(url).lower().endswith((".pdf", ".html", ".htm")) or kind == "pdf" else ".html"), body)
    it["local"] = rel(p)
    it["file_type"] = kind
    validate(st, it)
    say(iid, final_status(it), it["http_status"], it["pages"])
    save(st)

# ---------------------------------------------------------------- validation
def vals(rx, t, cast=float):
    out = []
    for m in re.finditer(rx, t):
        try:
            out.append(cast(m.group(1)))
        except ValueError:
            pass
    return out

def near_hour(t, n, w=150):
    for m in re.finditer(r"(?<![\d.])" + str(n) + r"(?![\d])", t):
        if "hour" in t[max(0, m.start() - w): m.end() + w] or "hrs" in t[max(0, m.start() - w): m.end() + w]:
            return True
    return False

def setcheck(it, field, expected, found, ok, required, extraction_ok, note=""):
    if ok:
        r = "MATCH"
    elif found:
        r = "MISMATCH"
    else:
        r = "NOT FOUND"
    it["checks"][field] = dict(expected=expected, result=r, found=found, required=required,
                               extraction_ok=extraction_ok, note=note)

def validate(st, it):
    path = os.path.join(ROOT, it["local"])
    kind, dt = it["kind"], it["doctype"]
    it["identity"], it["readable"] = None, True
    if kind == "pdf":
        try:
            it["pages"] = pdf_open(path)
            pages = pdf_pages(path)
        except Exception as e:
            it["readable"] = False
            it["notes"] += f" pdf open/parse failed: {type(e).__name__}"
            return
        it["page_chars_1_5"] = [len(x) for x in pages[:5]]
        full = "\n".join(pages)
        extraction_ok = sum(it["page_chars_1_5"]) > 200
        it["extraction_ok"] = extraction_ok
        if kind == "pdf" and dt in ("LIST", "NCO"):
            if dt == "LIST":
                t = norm_codes(norm(full)).upper()
                ok = "AMH/Q0301" in t and "AMH/Q2301" in t
                it["identity"] = "confirmed" if ok else "unconfirmed"
                it["notes"] += " list PDF: codes AMH/Q0301 & AMH/Q2301 present=" + str(ok)
            else:
                it["identity"] = "confirmed" if "occupation" in full.lower() else "unconfirmed"
            return
        t = norm_codes(norm(full))
        w = words(t)
        e = EXP[it["qual"]]
        codes = set(re.findall(r"amh/q\d{4}", t))
        has_qp = e["qp"].lower() in t
        has_name = e["name"] in w or (it["qual"] == "IC" and "in line checker" in w)
        if dt == "QF":  # QFs identify by NQR code, not QP code
            qfn = set(m.upper() for m in re.findall(r"qg-[\d.]+-[a-z]+-\d+-\d{4}-v[\d.]+-[a-z]+", t))
            has_qp = e["nqr"].lower() in t
            codes = qfn if not has_qp else set()
            it["notes"] += " QF identity via NQR code+name (QF does not state QP code)"
        if not extraction_ok and not has_qp:
            it["identity"] = "unconfirmed"
        elif not has_qp and codes:
            it["identity"] = "wrong"
            it["notes"] += " other QP codes found: " + ",".join(sorted(c.upper() for c in codes))
        elif has_qp and (has_name or dt == "QP"):  # QP: code is the identity anchor; name difference is recorded as discrepancy
            it["identity"] = "confirmed"
        else:
            it["identity"] = "unconfirmed"
        it["snippets"] = [s for s in (snippet(full, e["qp"]),) if s]
        pdf_field_checks(it, t, w, e, extraction_ok, dt)
        if dt == "QF":
            qs = set(c for c in NQR_CODE_RE.findall(full.replace("\n", " ")))
            it["found_nqr_codes"] = sorted(qs)
    else:
        title, text = html_text(path)
        t = norm_codes(norm(text))
        it["page_chars"] = len(text)
        bad = re.search(r"\b(404|not found|error|access denied)\b", norm(title))
        if bad and len(text) < 800:
            it["readable"] = False
            it["notes"] += " looks like an error page"
            return
        if it["item_id"] == "A1":
            ok = "amh/q0301" in t and "amh/q2301" in t
            it["identity"] = "confirmed" if ok else "unconfirmed"
            if not ok:
                it["notes"] += " raw HTML lacks expected QP codes (JS-rendered?)"
        elif it["doctype"] == "NQR":
            e = EXP[it["qual"]]
            found = set(NQR_CODE_RE.findall(text))
            it["found_nqr_codes"] = sorted(found)
            if e["nqr"].lower() in t or e["name"] in words(t):
                it["identity"] = "confirmed"
            elif found:
                it["identity"] = "wrong"
            else:
                it["identity"] = "unconfirmed"
                it["notes"] += " raw HTML lacks qualification content (possibly JS-rendered)"
                it["limitations"].append("Playwright not used - per-host rate limit not enforceable / not needed for plain items; raw HTML has no qualification content")
            if it["identity"] == "confirmed":
                setcheck(it, "nqr_code", e["nqr"], sorted(found), e["nqr"].lower() in t, True, True)
                setcheck(it, "nsqf", e["nsqf"], sorted(set(vals(r"nsqf\s*level\D{0,40}?(\d(?:\.\d)?)", t))),
                         e["nsqf"] in vals(r"nsqf\s*level\D{0,40}?(\d(?:\.\d)?)", t), True, True)
        else:  # D1-src
            it["identity"] = "confirmed" if ("nco" in t or "occupation" in t) else "unconfirmed"

def pdf_field_checks(it, t, w, e, ex_ok, dt):
    qf = dt == "QF"
    nq = set(m.upper() for m in re.findall(r"qg-[\d.]+-[a-z]+-\d+-\d{4}-v[\d.]+-[a-z]+", t))
    setcheck(it, "nqr_code", e["nqr"], sorted(nq), e["nqr"].lower() in t, qf, ex_ok)
    vs = sorted(set(str(x) for x in vals(r"version\s*[:\-]?\s*v?(\d+(?:\.\d+)?)", t)))
    vs_norm = sorted(set(f"{float(x):.1f}" for x in vs))
    setcheck(it, "version", e["ver"], vs_norm, e["ver"] in vs_norm, True, ex_ok)
    lv = vals(r"nsqf\s*level\D{0,40}?(\d(?:\.\d)?)", t)
    setcheck(it, "nsqf", e["nsqf"], sorted(set(lv)), e["nsqf"] in lv, True, ex_ok)
    setcheck(it, "notional_hours", e["hours"], None, near_hour(t, e["hours"]), qf, ex_ok)
    for n in e["parts"]:
        it["checks"]["notional_hours"].setdefault("parts", {})[str(n)] = near_hour(t, n)
    cr = vals(r"credits?\D{0,40}?(\d{1,2})\b", t, int)
    setcheck(it, "credits", e["credits"], sorted(set(cr)), e["credits"] in cr, qf, ex_ok)
    nco = sorted(set(re.findall(r"\b\d{4}\.\d{4}\b", t)))
    setcheck(it, "nco_2015", e["nco"], nco, e["nco"] in nco, True, ex_ok)
    ag = vals(r"(?:minimum|job entry)[^.]{0,30}?age\D{0,60}?(\d{2})\b", t, int) + vals(r"\bage\s*:\s*(\d{2})\s*years", t, int)
    setcheck(it, "min_age", e["age"], sorted(set(ag)), e["age"] in ag, True, ex_ok)
    if qf:
        has = e["qp"].lower() in t
        it["checks"]["qp_code"] = dict(expected=e["qp"], result="MATCH" if has else "NOT FOUND", found=None, required=True,
                                       extraction_ok=ex_ok, note="" if has else "QF text does not state the QP code")
    it["checks"]["name"] = dict(expected=e["name"], result="MATCH" if (e["name"] in w or (it["qual"] == "IC" and "in line checker" in w)) else "NOT FOUND", found=None,
                                required=(dt == "QP"), extraction_ok=ex_ok)

# ---------------------------------------------------------------- status
def disc_list(it):
    d = []
    for f, c in it["checks"].items():
        if c.get("required") and c["result"] != "MATCH":
            d.append(f"{f}: {c['result']}" + (f" (found {c['found']})" if c.get("found") else ""))
    d += it.get("extra_disc", [])
    return d

def final_status(it):
    if it["status_override"]:
        return it["status_override"]
    if it["readable"] is False or it["identity"] in (None, "unconfirmed"):
        return "FAIL_UNREADABLE"
    if it["identity"] == "wrong":
        return "FAIL_WRONG_DOCUMENT"
    return "PASS_WITH_DISCREPANCIES" if disc_list(it) else "PASS"

# ---------------------------------------------------------------- A1 parse
def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def pu(u):
    s = up.urlsplit(u)
    return up.urlunsplit((s.scheme.lower(), s.netloc.lower(), up.quote(up.unquote(s.path), safe="/:()"), "", ""))

def parse_a1(st):
    it = st["items"]["A1"]
    path = os.path.join(ROOT, it["local"])
    soup = BeautifulSoup(open(path, "rb").read(), "html.parser")
    rows_out, tbl_found, hdr = [], False, []
    for tbl in soup.find_all("table"):
        trs = tbl.find_all("tr")
        if not trs:
            continue
        h = [norm(c.get_text(" ")) for c in trs[0].find_all(["th", "td"])]
        if not any("qp" in x and "code" in x for x in h):
            continue
        tbl_found, hdr = True, h
        def col(*keys, excl=()):
            for i, x in enumerate(h):
                if all(k in x for k in keys) and not any(k in x for k in excl):
                    return i
        idx = dict(sno=col("s.no") if col("s.no") is not None else col("sr"), name=col("name"),
                   qp_code=col("qp", "code"), nqr=col("nqr"), ver=col("version"), nsqf=col("nsqf"),
                   hours=col("hour"), credits=col("credit"), ccn=col("ccn"))
        qpl = col("qp", excl=("code", "name", "version")) ; qfl = col("qf") if col("qf") is not None else col("file")
        for tr in trs[1:]:
            tds = tr.find_all("td")
            if not tds:
                continue
            def cell(k):
                i = idx.get(k)
                return clean(tds[i].get_text(" ")) if i is not None and i < len(tds) else ""
            links = [(i, a.get("href")) for i, td in enumerate(tds) for a in td.find_all("a", href=True)]
            def link(col_i):
                if col_i is None:
                    return ""
                for i, hr in links:
                    if i == col_i:
                        return hr
                return ""
            qph, qfh = link(qpl), link(qfl)
            mapping = "by header"
            if (not qph or not qfh) and len(links) >= 2:
                qph, qfh, mapping = links[-2][1], links[-1][1], "positional (last two anchors)"
            rows_out.append(dict(sno=cell("sno"), qp_name=cell("name"), qp_code=cell("qp_code"), nqr_code=cell("nqr"),
                                 qp_version=cell("ver"), nsqf_level=cell("nsqf"), notional_hours=cell("hours"),
                                 credits=cell("credits"), ccn=cell("ccn"), qp_href_raw=qph, qf_href_raw=qfh,
                                 qp_url_resolved=up.urljoin(A1_BASE, qph) if qph else "",
                                 qf_url_resolved=up.urljoin(A1_BASE, qfh) if qfh else "", link_mapping=mapping))
        break
    os.makedirs(PROC, exist_ok=True)
    out = os.path.join(PROC, "approved_qualifications_parsed.csv")
    cols = ["sno", "qp_name", "qp_code", "nqr_code", "qp_version", "nsqf_level", "notional_hours", "credits", "ccn",
            "qp_href_raw", "qf_href_raw", "qp_url_resolved", "qf_url_resolved", "link_mapping"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows_out)
    codes = {r["qp_code"].replace(" ", "").upper() for r in rows_out}
    good = [r for r in rows_out if r["qp_code"] and r["nqr_code"] and r["qp_href_raw"] and r["qf_href_raw"]]
    ok = tbl_found and bool(good) and {"AMH/Q0301", "AMH/Q2301"} <= codes
    st["a1_parse"] = dict(ok=ok, table_found=tbl_found, header=hdr, rows=len(rows_out), rows_complete=len(good),
                          targets_present=sorted({"AMH/Q0301", "AMH/Q2301"} & codes), csv=rel(out))
    say("A1 parse:", json.dumps(st["a1_parse"]))
    return rows_out

def catalogue_xcheck(st, only=None):
    p = os.path.join(PROC, "approved_qualifications_parsed.csv")
    if not os.path.exists(p):
        return
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    for iid, it in st["items"].items():
        if not it.get("cat") or (only and iid not in only):
            continue
        code, which = it["cat"]
        row = next((r for r in rows if r["qp_code"].replace(" ", "").upper() == code), None)
        if not row:
            it["catalogue_xcheck"] = dict(result="NOT PERFORMED", reason="QP code row not found in catalogue")
            continue
        raw = row[f"{which}_href_raw"]
        res = row[f"{which}_url_resolved"]
        it["catalogue_raw"] = raw
        same = pu(res) == pu(it["url"])
        it["catalogue_xcheck"] = dict(result="MATCH" if same else "DISCREPANCY", catalogue_raw=raw,
                                      catalogue_normalised=pu(res), prompt_url_raw=it["url"], prompt_normalised=pu(it["url"]))
        it["extra_disc"] = [d for d in it["extra_disc"] if not d.startswith("catalogue URL")]
        if not same:
            it["extra_disc"].append("catalogue URL differs from prompt URL after normalisation")

def gate1(st):
    ids = ["A2", "A3", "A4", "A5"]
    okset = ("PASS", "PASS_WITH_DISCREPANCIES")
    a1 = st["items"].get("A1")
    g = dict(A1_status=final_status(a1) if a1 else None, A1_parsed=st.get("a1_parse", {}).get("ok", False))
    for i in ids:
        g[i] = final_status(st["items"][i]) if i in st["items"] else "NOT ATTEMPTED"
    g["passed"] = bool(a1 and g["A1_status"] in okset and g["A1_parsed"] and all(g[i] in okset for i in ids))
    st["gates"]["gate1"] = g
    say("GATE1:", json.dumps(g))
    return g

# ---------------------------------------------------------------- cross-checks
def sha_cmp(st):
    a, b = st["items"].get("B2"), st["items"].get("B2b")
    ok = lambda x: x and final_status(x) in ("PASS", "PASS_WITH_DISCREPANCIES")
    if not (ok(a) and ok(b)):
        return "NOT PERFORMED - source unavailable (" + ", ".join(f"{i} {final_status(x) if x else 'not attempted'}" for i, x in (("B2", a), ("B2b", b))) + ")"
    if a["sha"] == b["sha"]:
        return "SHA-256 identical"
    return dict(result="SHA-256 differ", B2_pages=a["pages"], B2b_pages=b["pages"], B2_nqr=a.get("found_nqr_codes"), B2b_nqr=b.get("found_nqr_codes"))

def dates_near(t, kw):
    out = []
    for m in re.finditer(kw + r"[^0-9]{0,80}?(\d{1,2}[/-]\d{1,2}[/-]\d{4})", t):
        out.append(m.group(1))
    return sorted(set(out))

def crosschecks(st):
    its = st["items"]
    xc = st.setdefault("crosschecks", {})
    def okp(i):
        return i in its and final_status(its[i]) in ("PASS", "PASS_WITH_DISCREPANCIES")
    def tx(i):
        it = its[i]; p = os.path.join(ROOT, it["local"])
        if it["kind"] == "pdf":
            return norm_codes(norm("\n".join(pdf_pages(p))))
        return norm_codes(norm(html_text(p)[1]))
    # SMO dates and PC28/29 (document only)
    if okp("A2") and okp("A3"):
        qp, qf = tx("A2"), tx("A3")
        d = dict(QF_approval_dates=dates_near(qf, r"(?:nsqc|approv)"), QP_approval_dates=dates_near(qp, r"(?:nsqc|approv)"),
                 QP_last_reviewed=dates_near(qp, r"last reviewed on"))
        xc["SMO_dates"] = d
        m28 = re.search(r"pc\s*28\.?\s*(.{0,300}?)\s*pc\s*29", qp)
        m29 = re.search(r"pc\s*29\.?\s*(.{0,300}?)(?:pc\s*30|nos |elements|$)", qp)
        same = None
        if m28 and m29:
            a, b = re.sub(r"\W+", "", m28.group(1)), re.sub(r"\W+", "", m29.group(1))
            same = bool(a) and (a == b or a[:80] == b[:80])
        xc["SMO_PC28_PC29"] = dict(qp_pc28_pc29_duplicated=same, qf_annexure_pc29_contains_operate_machines_safely=("operate machines safely" in qf),
                                   note="booleans only; PC text not extracted to any output. None = could not parse from extracted text")
        xc["SMO_NCO_in_docs"] = dict(QP=sorted(set(re.findall(r"\b\d{4}\.\d{4}\b", qp))), QF=sorted(set(re.findall(r"\b\d{4}\.\d{4}\b", qf))))
    else:
        xc["SMO_dates"] = xc["SMO_PC28_PC29"] = xc["SMO_NCO_in_docs"] = "NOT PERFORMED - source unavailable"
    xc["InlineChecker_B2_vs_B2b"] = sha_cmp(st)
    # NQR dependent
    if okp("C3") and okp("A5") and its["C3"]["identity"] == "confirmed":
        c3, a5 = tx("C3"), tx("A5")
        xc["SSMO_hours_NQR_vs_QF"] = dict(NQR_lists_N2301="amh/n2301" in c3, NQR_150h_near_N2301=bool(re.search(r"amh/n2301.{0,200}?\b150\b", c3)),
                                          QF_147_present=near_hour(a5, 147), QF_bridge_module_present="bridge" in a5, QF_3h_present=near_hour(a5, 3))
    else:
        xc["SSMO_hours_NQR_vs_QF"] = "NOT PERFORMED - source unavailable (C3 %s)" % (final_status(its["C3"]) if "C3" in its else "not attempted")
    for c, q in (("C1", "B2"), ("C2", "B4"), ("C3", "A5"), ("C4", "A3")):
        if c in its and okp(c) and its[c]["identity"] == "confirmed" and okp(q):
            n, f = tx(c), tx(q)
            e = EXP[its[c]["qual"]] if its[c]["qual"] else EXP["SMO"]
            xc[f"{c}_vs_{q}"] = dict(nqr_code_on_nqr=e["nqr"].lower() in n, nsqf_on_nqr=e["nsqf"] in vals(r"nsqf\s*level\D{0,40}?(\d(?:\.\d)?)", n),
                                     hours_total_on_nqr=near_hour(n, e["hours"]), eligibility_text_present=("eligib" in n),
                                     progression_text_present=("progress" in n),
                                     note="presence checks only; eligibility/progression wording not compared automatically")
        else:
            xc[f"{c}_vs_{q}"] = "NOT PERFORMED - source unavailable (%s %s)" % (c, final_status(its[c]) if c in its else "not attempted")

# ---------------------------------------------------------------- phase 3
def phase3(st):
    for spec in ITEMS:
        if spec[2] == 3 and spec[0] in ("D1", "D1-src"):
            acquire(st, spec)
    found, fm = {}, {}
    d1 = st["items"]["D1"]
    d1info = dict(status=final_status(d1))
    if d1.get("local") and d1["readable"]:
        pages = pdf_pages(os.path.join(ROOT, d1["local"]))
        d1info.update(chars=sum(len(x) for x in pages), pages_with_text=sum(1 for x in pages if len(x.strip()) > 20), pages=len(pages))
        full = "\n".join(pages)
        for c in NCO_TARGETS:
            m = re.search(re.escape(c) + r"\s*[-:]?\s*(.{0,80})", full)
            if m:
                found[c] = dict(source="D1", title=re.sub(r"\s+", " ", m.group(1)).strip()[:80])
    st["nco"]["d1_extraction"] = d1info
    rem = [c for c in NCO_TARGETS if c not in found]
    end, n, empty = "all codes found in D1" if not rem else "", 0, 0
    saved = []
    ok, why = robots_allows(st, "https://dge.gov.in/nat?page=0")
    if rem and not ok:
        end = "D2 skipped: " + why
    while rem and ok:
        url = f"https://dge.gov.in/nat?page={n}"
        res = http_get(st, url)
        if res.get("error") or not (res.get("status") and 200 <= res["status"] < 300):
            end = f"D2 stopped at page {n}: {res.get('error') or res.get('status')}"
            break
        soup = BeautifulSoup(res["body"], "html.parser")
        rows = [tr for tr in soup.find_all("tr") if tr.find("td")]
        text = soup.get_text(" ")
        empty = empty + 1 if not rows else 0
        hit = [c for c in rem if c in text]
        if hit:
            p = save_file("dge/nco", f"dge_nat_page_{n}.html", res["body"])
            for c in hit:
                tr = next((r for r in rows if c in r.get_text(" ")), None)
                tt = clean(tr.get_text(" "))[:120] if tr else ""
                found[c] = dict(source="D2", page=n, title=tt)
            rem = [c for c in rem if c not in hit]
            it = new_item(f"D2-p{n}", f"DGE NCO table page {n}", 3, "no", "DGE", url, "dge/nco", "html")
            fill_transport(it, res)
            it.update(local=rel(p), file_type="html", identity="confirmed", readable=True, notes="contains target code(s): " + ",".join(hit))
            st["items"][it["item_id"]] = it
            saved.append(n)
        if not rem:
            end = f"all codes found by page {n}"
        elif empty >= 3:
            end = f"3 consecutive pages without table rows (through page {n})"
        elif n >= 119:
            end = "120-page cap reached"
        if end:
            break
        n += 1
        save(st)
    for c in NCO_TARGETS:
        st["nco"][c] = found.get(c, dict(source=None, outcome="NOT_FOUND"))
    st["nco"]["d2_search_end"] = end or "n/a"
    it = new_item("D2", "DGE online NCO table search (summary)", 3, "no", "DGE", "https://dge.gov.in/nat?page=N", "dge/nco")
    it.update(status_override="NOT_FOUND" if any(c not in found for c in NCO_TARGETS) else "PASS",
              reason=end, notes=f"pages saved: {saved}")
    if not [c for c in NCO_TARGETS if c not in found]:
        it["reason"] = "all target codes located (" + end + ")"
    st["items"]["D2"] = it
    say("NCO:", json.dumps(st["nco"]))
    save(st)

# ---------------------------------------------------------------- outputs
def outputs(st):
    cols = ["item_id", "item_name", "phase", "required_for_gate", "source_org", "source_url", "catalogue_url_raw",
            "final_url", "local_relative_path", "retrieved_at", "http_status", "content_type", "size_bytes", "sha256",
            "file_type", "pdf_pages", "validation_status", "reason", "notes"]
    with open(os.path.join(RAW, "MANIFEST.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for it in st["items"].values():
            reason = it["reason"] or "; ".join(disc_list(it))
            w.writerow([it["item_id"], it["name"], it["phase"], it["gate"], it["org"], it["url"], it.get("catalogue_raw") or "",
                        it["final_url"], it["local"], it["retrieved_at"], it["http_status"], it["ctype"], it["size"], it["sha"],
                        it.get("file_type", ""), it["pages"], final_status(it), reason, (it["notes"] or "").strip()])
    val = dict(run_id=RUN_ID, generated=now_iso(), gates=st["gates"], a1_parse=st.get("a1_parse"), nco=st["nco"],
               crosschecks=st.get("crosschecks", {}), c4=st.get("c4"), items={})
    for k, it in st["items"].items():
        val["items"][k] = dict(status=final_status(it), identity=it["identity"], readable=it["readable"],
                               transport=dict(final_url=it["final_url"], http=it["http_status"], content_type=it["ctype"],
                                              size=it["size"], sha256=it["sha"], pages=it["pages"],
                                              requests_used=it.get("requests_used")),
                               page_chars_1_5=it.get("page_chars_1_5"), extraction_ok=it.get("extraction_ok"),
                               checks=it["checks"], discrepancies=disc_list(it), catalogue_url_xcheck=it["catalogue_xcheck"],
                               nqr_codes_found=it.get("found_nqr_codes"), snippets=it["snippets"], limitations=it["limitations"],
                               reason=it["reason"], notes=it["notes"])
    json.dump(val, open(os.path.join(RAW, "VALIDATION.json"), "w", encoding="utf-8"), indent=1, default=str)

# ---------------------------------------------------------------- C4 bounded search
C4_CODE = "QG-2.5-AP-01866-2024-V1.1-AMHSSC"
C4_CAP = 15

def c4(st, url):
    c = st.setdefault("c4", dict(tried=[], found=False))
    ok, why = robots_allows(st, url)
    if not ok:
        c["tried"].append(dict(url=url, result="skipped: " + why))
        return say("skipped", why)
    res = http_get(st, url, counter="c4_requests", cap=C4_CAP)
    page = dict(url=url, status=res.get("status"), error=res.get("error"), requests_so_far=st["c4_requests"])
    if res.get("body") is not None and res.get("status") == 200:
        soup = BeautifulSoup(res["body"], "html.parser")
        text = soup.get_text(" ")
        page["has_target_code"] = C4_CODE.lower() in text.lower()
        page["rows"] = len([tr for tr in soup.find_all("tr") if tr.find("td")])
        page["pagination"] = sorted({a["href"] for a in soup.find_all("a", href=True) if re.search(r"page=|qualifications-search", a["href"])})[:6] if False else None
        qlinks = [(a.get_text(" ", strip=True)[:70], a["href"]) for a in soup.find_all("a", href=True) if re.search(r"/qualifications/\d+", a["href"])]
        page["n_qual_links"] = len(qlinks)
        hits = [l for l in qlinks if re.search(r"sewing machine operator", l[0], re.I)]
        page["sewing_machine_operator_links"] = hits[:8]
        page["next_links"] = sorted({a["href"] for a in soup.find_all("a", href=True) if re.search(r"[?&]page=\d+", a["href"])})[:5]
        if page["has_target_code"]:
            p = save_file("nqr/html", "c4_search_page_with_target_code.html", res["body"])
            page["saved"] = rel(p)
    c["tried"].append(page)
    say(json.dumps(page, ensure_ascii=True)[:1500])

def c4search(st, query):
    """NQR's own public search form: GET page for CSRF token + cookie, then POST. Both counted against the cap."""
    c = st.setdefault("c4", dict(tried=[], found=False))
    for u in ("https://www.nqr.gov.in/", "https://www.nqr.gov.in/search"):
        if not robots_allows(st, u)[0]:
            c["tried"].append(dict(url=u, result="skipped: disallowed by robots.txt"))
            return say("robots disallow", u)
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=False) as cl:
        if st["c4_requests"] + 2 > C4_CAP:
            return say("cap would be exceeded")
        r1 = chain(st, cl, "https://www.nqr.gov.in/", "c4_requests")
        tok = re.search(r'name="_token"\s+value="([^"]+)"', (r1.get("body") or b"").decode("utf-8", "replace"))
        c["tried"].append(dict(url="https://www.nqr.gov.in/ (token fetch)", status=r1.get("status"), token=bool(tok), requests_so_far=st["c4_requests"]))
        if not tok:
            return say("no token", r1.get("status"))
        throttle(st, "www.nqr.gov.in")
        r = cl.post("https://www.nqr.gov.in/search", data={"_token": tok.group(1), "querySearch": query})
        st["last_req"]["www.nqr.gov.in"] = time.time()
        st["c4_requests"] += 1
        body = r.content
        soup = BeautifulSoup(body, "html.parser")
        text = soup.get_text(" ")
        qlinks = [(a.get_text(" ", strip=True)[:70], a["href"]) for a in soup.find_all("a", href=True) if re.search(r"/qualifications/\d+", a["href"])]
        page = dict(url="POST /search querySearch=" + query, status=r.status_code, final_url=str(r.url), requests_so_far=st["c4_requests"],
                    has_target_code=C4_CODE.lower() in text.lower(), n_qual_links=len(qlinks), links=qlinks[:15],
                    redirect=r.headers.get("location"))
        if page["has_target_code"]:
            p = save_file("nqr/html", "c4_search_results_with_target_code.html", body)
            page["saved"] = rel(p)
        c["tried"].append(page)
        say(json.dumps(page, ensure_ascii=True)[:2500])

def c4end(st):
    c = st.get("c4", {})
    it = new_item("C4", "NQR record Sewing Machine Operator", 2, "no", "NQR", "(ID unknown - bounded search)", "nqr/html")
    if c.get("found_url"):
        pass
    else:
        it.update(status_override="NOT_FOUND", reason=f"exact NQR code not located within {C4_CAP}-request cap",
                  notes=f"requests used: {st['c4_requests']}; pages tried: {len(c.get('tried', []))}")
    st["items"]["C4"] = it

# ---------------------------------------------------------------- main
def main():
    phase = sys.argv[1]
    os.makedirs(RAW, exist_ok=True)
    st = load()
    time.sleep(2.2)
    if phase == "p1":
        robots_step(st)
        for spec in ITEMS:
            if spec[2] == 1:
                acquire(st, spec)
    elif phase == "parse":
        parse_a1(st)
        catalogue_xcheck(st)
        gate1(st)
    elif phase == "p2":
        for spec in ITEMS:
            if spec[2] == 2:
                acquire(st, spec)
        catalogue_xcheck(st)
    elif phase == "cross":
        catalogue_xcheck(st)
        crosschecks(st)
        say(json.dumps(st["crosschecks"], default=str)[:3000])
    elif phase == "p3":
        phase3(st)
    elif phase == "c4":
        c4(st, sys.argv[2])
    elif phase == "c4search":
        c4search(st, sys.argv[2])
    elif phase == "c4end":
        c4end(st)
    elif phase == "revalidate":
        for it in st["items"].values():
            if it.get("local") and it["status_override"] is None:
                it["checks"], it["notes"], it["snippets"] = {}, "", []
                validate(st, it)
        catalogue_xcheck(st)
        gate1(st)
    elif phase == "outputs":
        pass
    save(st)
    outputs(st)
    say("statuses:", {k: final_status(v) for k, v in st["items"].items()})

if __name__ == "__main__":
    main()
