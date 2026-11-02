"""PROTOTYPE journey composition for the demo (NOT the API_SPEC contract): simple worker answers -> engine calls -> a result view.

This module adds no eligibility logic. It (1) translates four plain answers into the ``ProfileState`` the engine already
accepts, (2) calls ``eligibility.evaluate`` once per curated pilot qualification and ``graph.enumerate_paths`` for routes, and
(3) orders and describes the results using ONLY strings and numbers the engine, registry and evidence records returned.

Ordering is the documented default of ARCHITECTURE §13.2 restricted to the keys that can be computed today: verdict class
first (MET, CONDITIONAL, UNKNOWN, then NOT_MET), then official total hours, then qualification code. It is not P3.7 (no
``path_id``, no ``sort_values``) and it measures documented notional duration only: not difficulty, likelihood or outcome.

Nothing here is a prediction. Enrolment availability and deadlines are reported as not verified because the build holds no
training-centre listing or deadline data.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from skillgraph.eligibility.evaluate import (
    EligibilityResult,
    EngineConfig,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    evaluate,
)
from skillgraph.graph import RawPath, Scenario, enumerate_paths
from skillgraph.model.eligibility import Verdict
from skillgraph.model.qualification import Coverage, Qualification
from skillgraph.registry import Registry, UnknownEntityError
from skillgraph.settings import Settings

LEVEL_MATCH = Literal["exact", "at_least"] | None
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2,6}/Q\d{4}$")]
Education = Literal["NOT_STATED", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "UG_CERTIFICATE", "UG_DIPLOMA"]
CurrentKind = Literal["HOLDS_QUALIFICATION", "GARMENT_WORK_NO_QUALIFICATION", "OTHER_WORK"]

VERDICT_CLASS = {Verdict.MET: 0, Verdict.CONDITIONAL: 1, Verdict.UNKNOWN: 2, Verdict.NOT_MET: 3}
CARD_LIMIT = 3
ROUTE_MAX_STEPS = 2
ROUTES_PER_TARGET = 3

HEADLINES = {
    Verdict.MET: "The documented entry rules are met by the answers you gave.",
    Verdict.CONDITIONAL: "The documented entry rules are met only if the conditions below hold.",
    Verdict.UNKNOWN: "This cannot be decided from the answers given and the rules the system can read with certainty.",
    Verdict.NOT_MET: "No documented entry route is met by the answers you gave.",
}


class ExploreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_kind: CurrentKind
    held_code: Code | None = None
    education: Education = "NOT_STATED"
    years_in_job: float | None = Field(default=None, ge=0, le=60)
    age_years: int | None = Field(default=None, strict=True, ge=14, le=80)
    nsqf_level_match: LEVEL_MATCH = None


class ExploreError(Exception):
    """A request the journey cannot serve; ``code`` is machine-readable and mapped to a 422 by the caller."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _title(q: Qualification) -> str:
    return q.titles.qf or q.titles.qp or q.titles.catalogue or q.code


def _hours_total(q: Qualification) -> float:
    return q.hours.total.value


def _curated(registry: Registry) -> list[Qualification]:
    return sorted((q for q in registry.qualifications() if q.coverage is Coverage.CURATED and q.eligibility), key=lambda q: q.id)


# ------------------------------------------------------------------------------------------------------------------
# Answers -> profile
# ------------------------------------------------------------------------------------------------------------------


def build_profile(req: ExploreRequest, registry: Registry) -> tuple[ProfileState, list[dict[str, str]]]:
    """The engine profile and the plain list of how each answer was read (shown to the user, never hidden)."""
    reading: list[dict[str, str]] = []
    held: tuple[str, ...] = ()
    if req.current_kind == "HOLDS_QUALIFICATION":
        if req.held_code is None:
            raise ExploreError("HELD_CODE_REQUIRED", "Choose which qualification you hold.")
        try:
            q = registry.qualification_by_code(req.held_code)
        except UnknownEntityError:
            raise ExploreError("UNKNOWN_QUALIFICATION_CODE", f"{req.held_code} is not in the registry.") from None
        if q.coverage is not Coverage.CURATED:
            raise ExploreError("TARGET_NOT_EVALUABLE", f"{req.held_code} is a catalogue entry only and cannot be used.")
        held = (q.code,)
        reading.append({"label": "Current qualification", "value": f"{_title(q)} ({q.code})",
                        "how": "Declared as held, and declared relevant to every option below (all are garment-sewing "
                               "qualifications). Its NSQF level is the official registry level."})
    elif req.current_kind == "GARMENT_WORK_NO_QUALIFICATION":
        reading.append({"label": "Current work", "value": "Garment / sewing work, no listed qualification",
                        "how": "Declared as holding none of the registry qualifications."})
    else:
        reading.append({"label": "Current work", "value": "Other work, not garment related",
                        "how": "Declared as holding none of the registry qualifications, and 0 years of relevant experience."})

    if req.education == "NOT_STATED":
        grade, creds = None, None
        reading.append({"label": "Education", "value": "Not stated",
                        "how": "Not declared, so any school-grade or credential rule is UNKNOWN, never assumed."})
    elif req.education in ("UG_CERTIFICATE", "UG_DIPLOMA"):
        grade, creds = None, (PostSchoolCredential(type=req.education),)
        reading.append({"label": "Education", "value": "Post-school " + req.education.split("_")[1].lower(),
                        "how": "Declared as the credential named; the school grade is left undeclared."})
    else:
        grade, creds = int(req.education[1:]), ()
        reading.append({"label": "Education", "value": f"Grade {grade} passed",
                        "how": "Declared as the highest school grade passed, with no post-school credential."})

    if req.current_kind == "OTHER_WORK":
        exp: float | None = 0.0
        reading.append({"label": "Years in current job", "value": "Not counted",
                        "how": "Non-garment work is not counted as relevant experience."})
    elif req.years_in_job is None:
        exp = None
        reading.append({"label": "Years in current job", "value": "Not stated",
                        "how": "Not declared, so any experience rule is UNKNOWN."})
    else:
        exp = float(req.years_in_job)
        reading.append({"label": "Years in current job", "value": f"{exp:g}",
                        "how": "Declared as relevant experience for every option below. This is your declaration, not a "
                               "checked fact."})

    reading.append({"label": "Age", "value": "Not stated" if req.age_years is None else str(req.age_years),
                    "how": "Every qualification has a minimum age. Without an age that rule is UNKNOWN, so no option can "
                           "be MET." if req.age_years is None else "Declared; compared with each qualification's minimum age."})
    reading.append({"label": "NSQF level comparison",
                    "value": {None: "Not set", "exact": "Exact", "at_least": "At least"}[req.nsqf_level_match],
                    "how": "How a held qualification's NSQF level is compared with a level-based rule. The project has no "
                           "default reading, so 'Not set' makes such rules UNKNOWN."})

    decl = tuple(TargetDeclaration(target_code=q.code, relevant_experience_years=exp,
                                   relevant_prior_qualifications=held) for q in _curated(registry))
    profile = ProfileState(age_years=req.age_years, school_grade_passed=grade, post_school_credentials=creds,
                           held_qualification_codes=held, external_qualifications=(), declarations=decl)
    return profile, reading


# ------------------------------------------------------------------------------------------------------------------
# Result -> view
# ------------------------------------------------------------------------------------------------------------------


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for i in items:
        seen.setdefault(i, None)
    return list(seen)


def _why(res: EligibilityResult) -> list[str]:
    """Short reasons for the card, taken only from engine strings (rule text, condition text, reason text)."""
    rows = {r.rule_id: r for r in res.rows}
    if res.verdict is Verdict.MET:
        out = [f"Rule met: {rows[i].raw_text.replace(' || ', ' · ')}" for i in res.decisive_rule_ids if i in rows]
    elif res.verdict is Verdict.CONDITIONAL:
        out = [c.text if c.text.lower().startswith("holds only if") else f"Holds only if: {c.text}" for c in res.conditions]
    elif res.verdict is Verdict.UNKNOWN:
        out = [u.text for u in res.unknown_reasons]
    else:
        out = [f"{c.requirement_text} - not met" for r in res.rows for c in r.components if c.verdict is Verdict.NOT_MET]
        if res.age.verdict is Verdict.NOT_MET:
            out.insert(0, f"{res.age.requirement_text} - not met")
    return _dedupe(out)[:3]


def _evidence_map(registry: Registry, res: EligibilityResult) -> dict[str, dict[str, object]]:
    ids = {e for c in [res.age, *(c for r in res.rows for c in r.components)] for e in c.evidence_ids}
    out: dict[str, dict[str, object]] = {}
    for eid in sorted(ids):
        ev = registry.evidence_by_id(eid)
        src = registry.source_by_id(ev.source_id) if ev.source_id else None
        out[eid] = {"evidence_class": ev.evidence_class.value, "source_title": src.title if src else None,
                    "source_org": src.org if src else None, "page": ev.page, "location": ev.location,
                    "value_status": ev.value_status.value if ev.value_status else None, "note": ev.note}
    return out


def _qualification_facts(registry: Registry, q: Qualification) -> dict[str, object]:
    units = []
    for m in q.nos_memberships:
        title = None
        if m.nos_id:
            nos = registry.nos_by_id(m.nos_id)
            title = nos.titles_by_source.get(q.id) or next(iter(nos.titles_by_source.values()), None)
        units.append({"code": m.nos_id.split(":", 1)[1] if m.nos_id else None, "title": title, "is_bridge": m.is_bridge,
                      "core_or_noncore": m.core_or_noncore.value,
                      "hours_total": m.hours.total.value if m.hours and m.hours.total else None})
    return {
        "code": q.code, "title": _title(q), "nsqf_level": q.nsqf_level.value, "min_age": q.min_age.value if q.min_age else None,
        "sector": q.sector.value if q.sector else None, "awarding_body": q.awarding_body.value if q.awarding_body else None,
        "hours": {k: (getattr(q.hours, k).value if getattr(q.hours, k) else None)
                  for k in ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total")},
        "skill_units": units,
        "progression_claims": [c.model_dump(mode="json") for c in q.progression_claims],
        "quality_flags": [f.model_dump(mode="json") for f in q.quality_flags],
    }


def _route_view(path: RawPath, registry: Registry) -> dict[str, object]:
    steps = [{"code": s.target_code, "title": _title(registry.qualification_by_code(s.target_code)),
              "verdict": s.eligibility.verdict.value, "hours": _hours_total(registry.qualification_by_code(s.target_code))}
             for s in path.steps]
    return {"verdict": path.verdict.value, "steps": steps, "total_hours": sum(s["hours"] for s in steps)}


def explore(req: ExploreRequest, registry: Registry, cfg: Settings) -> dict[str, object]:
    profile, reading = build_profile(req, registry)
    config = EngineConfig(nsqf_level_match=req.nsqf_level_match)
    held = set(profile.held_qualification_codes or ())
    options = []
    for q in _curated(registry):
        if q.code in held:
            continue
        res = evaluate(q.eligibility, profile, config, registry)
        options.append((q, res))
    options.sort(key=lambda o: (VERDICT_CLASS[o[1].verdict], _hours_total(o[0]), o[0].code))

    raw_paths = enumerate_paths(profile, registry, config, Scenario(), ROUTE_MAX_STEPS, None,
                                max_expansions=cfg.paths.max_expansions, max_steps_limit=cfg.paths.max_steps_limit)

    def routes_to(code: str) -> list[dict[str, object]]:
        views = [_route_view(p, registry) for p in raw_paths if len(p.steps) > 1 and p.steps[-1].target_code == code]
        views.sort(key=lambda v: (VERDICT_CLASS[Verdict(v["verdict"])], v["total_hours"],
                                  [s["code"] for s in v["steps"]]))
        return views[:ROUTES_PER_TARGET]

    def view(rank: int, q: Qualification, res: EligibilityResult) -> dict[str, object]:
        verdict = res.verdict
        return {
            "rank": rank, "code": q.code, "title": _title(q), "verdict": verdict.value, "headline": HEADLINES[verdict],
            "why": _why(res), "official_total_hours": _hours_total(q), "nsqf_level": q.nsqf_level.value,
            "enrolment": {"status": "NOT_VERIFIED",
                          "text": "Whether you can enrol now is not verified: this build has no training-centre listing data."},
            "deadline": {"status": "NOT_VERIFIED", "text": "No application deadline is verified for this qualification."},
            "eligibility": res.model_dump(mode="json"),
            "conditions": [c.model_dump(mode="json") for c in res.conditions],
            "unknown_reasons": [u.model_dump(mode="json") for u in res.unknown_reasons],
            "evidence": _evidence_map(registry, res),
            "facts": _qualification_facts(registry, q),
            "routes": routes_to(q.code),
        }

    views = [view(i + 1, q, r) for i, (q, r) in enumerate(options)]
    open_views = [v for v in views if v["verdict"] != Verdict.NOT_MET.value]
    return {
        "reading": reading,
        "ordering": {"rule": "Verdict class first (MET, CONDITIONAL, UNKNOWN), then fewest official notional hours. "
                             "Documented duration only: not difficulty, likelihood or any outcome.",
                     "contract": "ARCHITECTURE section 13.2 default, partial (P3.7 is not built)"},
        "cards": open_views[:CARD_LIMIT],
        "more_options": open_views[CARD_LIMIT:],
        "not_open": [v for v in views if v["verdict"] == Verdict.NOT_MET.value],
        "held": sorted(held),
    }
