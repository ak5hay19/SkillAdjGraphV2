"""Synthetic builders for the schema tests. Codes are TEST/…; no value here is a real source value."""

from __future__ import annotations

CODE = "TEST/Q9001"
QID = f"qual:{CODE}"


def ev(n: int) -> str:
    return f"ev:{n:016x}"


def official(value, n: int = 1, *, engine_use=None, status="TRANSCRIBED", **extra) -> dict:
    return {"value": value, "evidence_class": "OFFICIAL", "evidence_id": ev(n), "value_status": status,
            "engine_use": engine_use, **extra}


def hours(total=100.0, n: int = 1) -> dict:
    parts = {"theory": 20.0, "practical": 80.0, "ojt_mandatory": 0.0, "ojt_recommended": 0.0, "total": total}
    return {k: official(v, n, engine_use="SAFE_HOURS") for k, v in parts.items()}


def credits(value=4.0, n: int = 1) -> dict:
    return official(value, n, engine_use="NOT_USED")


def component(type_="AGE_MIN", **kw) -> dict:
    params = {"AGE_MIN": {"min_age": 18}, "EXPERIENCE_MIN_YEARS": {"years": 3.0}, "PRIOR_NSQF_LEVEL": {"level": 2.5}}
    return {"type": type_, "params": params.get(type_, {}), "evidence_id": ev(2), "safe": True, **kw}


def age_rule() -> dict:
    return {"id": f"rule:{CODE}/AGE", "raw_text": "Age: 18 years", "evidence_id": ev(2),
            "components": [component()], "engine_use": "SAFE_HARD_RULE"}


def row(s_no: int = 1, **kw) -> dict:
    base = {"id": f"rule:{CODE}/E{s_no}", "s_no": s_no, "raw_text": "10th Grade pass work", "evidence_id": ev(3),
            "components": [component("UNMODELLED", safe=False, unknown_reason="REVIEW_FLAG")],
            "engine_use": "UNKNOWN", "overlay_ids": ["OV-015"]}
    return {**base, **kw}


def membership(**kw) -> dict:
    base = {"qualification_id": QID, "nos_id": "nos:TEST/N9001", "s_no": 2, "core_or_noncore": "Core",
            "nsqf_level": official(2.5), "version": official("4.0", engine_use="DISPLAY_ONLY"),
            "hours": hours(), "credits": credits(), "is_bridge": False}
    return {**base, **kw}


def bridge_membership() -> dict:
    return membership(nos_id=None, module_id=f"mod:{CODE}/S1", s_no=1, version=None, is_bridge=True)


def module() -> dict:
    return {"id": f"mod:{CODE}/S1", "qualification_id": QID, "s_no": 1, "title": "Introduction (Bridge Module)",
            "is_bridge": True}


def curated(**kw) -> dict:
    base = {
        "id": QID, "code": CODE, "slug": "TEST.Q9001", "coverage": "CURATED", "nqr_code": "QG-TEST",
        "titles": {"qf": "Synthetic Qualification"}, "nsqf_level": official(2.5, engine_use="SAFE_HARD_RULE"),
        "min_age": official(18, engine_use="SAFE_HARD_RULE"), "hours": hours(), "credits": credits(),
        "nco_codes": [official("8153.0101", 4)],
        "nos_memberships": [bridge_membership(), membership()], "modules": [module()],
        "eligibility": {"age_rule": age_rule(), "rows": [row(1)]},
    }
    return {**base, **kw}


def catalogue_only(**kw) -> dict:
    base = {"id": "qual:TEST/Q9002", "code": "TEST/Q9002", "slug": "TEST.Q9002", "coverage": "CATALOGUE_ONLY",
            "nqr_code": "QG-TEST-2", "titles": {"catalogue": "Synthetic Catalogue Entry"},
            "nsqf_level": official(4.0, 5), "hours": {"total": official(240.0, 5, engine_use="SAFE_HOURS")},
            "credits": credits(8.0, 5)}
    return {**base, **kw}
