"""PROTOTYPE demo server: a thin, local, read-only wrapper over the existing engine (NOT the API_SPEC contract).

This module is a pre-submission demonstration slice. It deliberately does NOT implement API_SPEC E01-E14, the service façade
(P3.10) or the FastAPI application of P5.1; those remain unbuilt. Its routes live under ``/demo`` so that nothing here can be
mistaken for the contract, and every response says ``"contract": "PROTOTYPE_NOT_API_SPEC"``.

What it does: loads one curated build, refuses to serve unless the build's validation state is ``PASSED`` (the strict side of
the open question Q-C; this prototype does not decide Q-C), and calls ``eligibility.evaluate`` and ``graph.enumerate_paths``
exactly as the golden tests do. It adds no engine behaviour and no new explanation text: it returns the engine's structured
result.

Not claimed: employment, placement, earnings, labour demand or real transitions. Module A (Karnataka labour-market context)
is ``NO_GO`` and nothing from it is used. Provisional behaviours (Q-B ``COMPARE``, the hypothetical-relevance rule) are
reported to the client in ``notices``.

Run (local only): ``python -m uvicorn skillgraph.api.demo_app:create_app --factory --host 127.0.0.1 --port 8000``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from skillgraph.api.demo_explore import ExploreError, ExploreRequest, explore
from skillgraph.curation.build import CURATION_CODE_VERSION
from skillgraph.eligibility.evaluate import EligibilityError, EngineConfig, ProfileState, evaluate
from skillgraph.graph import (
    LimitExceededError,
    Scenario,
    TargetNotEvaluableError,
    enumerate_paths,
)
from skillgraph.model.qualification import Coverage
from skillgraph.registry import Registry, RegistryError, UnknownEntityError, load
from skillgraph.settings import Settings, load_settings

CONTRACT_MARK = "PROTOTYPE_NOT_API_SPEC"
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "index.html"

LEVEL_MATCH = Literal["exact", "at_least"] | None

# Fixed, reviewed wording. Nothing here predicts anything, and nothing is generated from data.
NOTICES: tuple[dict[str, str], ...] = (
    {"code": "NOT_A_PREDICTION",
     "text": "This tool reads documented entry requirements for a hypothetical profile. It does not predict employment, "
             "placement, earnings, labour demand or any real transition."},
    {"code": "PILOT_ONLY",
     "text": "Four AMHSSC garment-sector qualifications are evaluated. The other registry qualifications are catalogue "
             "entries only and are not evaluated."},
    {"code": "MODULE_A_NO_GO",
     "text": "Karnataka labour-market context (Module A) is NO_GO: no labour-market statistic is used or shown."},
    {"code": "PROVISIONAL_QB",
     "text": "PROVISIONAL (open question Q-B): a held qualification's NSQF level is compared as if usable. The policy is "
             "not yet decided."},
    {"code": "PROVISIONAL_RELEVANCE",
     "text": "PROVISIONAL: in a path, a qualification completed earlier in the path cannot yet be declared relevant, so a "
             "later step that needs it for its level is UNKNOWN."},
    {"code": "OVERLAYS_NOT_APPROVED",
     "text": "No audit overlay is approved. Rules that depend on one are reported as UNKNOWN, never guessed."},
    {"code": "PARTIAL_RANKING_AND_EXPLANATIONS",
     "text": "Ranking (P3.7), explanations (P3.8) and scenario flags (P3.6b) are not built. The journey orders options by "
             "verdict class and then official hours (the ARCHITECTURE 13.2 default, partial) and words reasons only from "
             "engine and evidence strings. It does not measure difficulty or any outcome."},
    {"code": "ENROLMENT_AND_DEADLINES_NOT_VERIFIED",
     "text": "No training-centre listing, enrolment availability or application deadline data exists in this build, so none "
             "is shown as fact."},
)

Code = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2,6}/Q\d{4}$")]


class EligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProfileState
    target_code: Code
    nsqf_level_match: LEVEL_MATCH = None


class PathsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProfileState
    target_code: Code | None = None
    max_steps: int | None = Field(default=None, strict=True)
    nsqf_level_match: LEVEL_MATCH = None


class _NotServing(Exception):
    """The build is absent or not validated: the data endpoints answer 503, never a result."""


def select_build(curated_dir: Path) -> Path | None:
    """The newest curated build of the current curation code version (the rule the golden-test fixture uses)."""
    found: list[tuple[str, Path]] = []
    for manifest in curated_dir.glob("cb-*/build_manifest.json") if curated_dir.is_dir() else []:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("curation_code_version") == CURATION_CODE_VERSION:
            found.append((str(data.get("built_at", "")), manifest.parent))
    return max(found)[1] if found else None


def _load_default(settings: Settings) -> Registry | None:
    build_dir = select_build(settings.data_path("curated_dir"))
    return load(build_dir) if build_dir else None


def _envelope(registry: Registry, **body: object) -> dict[str, object]:
    build = registry.build
    return {
        "contract": CONTRACT_MARK,
        "data_build_id": build.data_build_id if build else None,
        "validation": build.validation if build else None,
        "notices": list(NOTICES),
        **body,
    }


def create_app(
    settings: Settings | None = None,
    loader: Callable[[Settings], Registry | None] = _load_default,
) -> FastAPI:
    """Build the app. ``loader`` is a test seam; the default loads the newest matching curated build."""
    cfg = settings or load_settings()
    app = FastAPI(title="SkillPath demo (prototype, not the API_SPEC contract)", docs_url=None, redoc_url=None,
                  openapi_url=None)
    state: dict[str, object] = {"registry": None, "error": None}
    try:
        state["registry"] = loader(cfg)
    except RegistryError as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"

    def serving() -> Registry:
        registry = state["registry"]
        if not isinstance(registry, Registry) or registry.build is None:
            raise _NotServing("NOT_BUILT: no curated build is available")
        if registry.build.validation != "PASSED":
            raise _NotServing(f"NOT_VALIDATED: build {registry.build.data_build_id} has validation "
                              f"{registry.build.validation}; a validated build is required")
        return registry

    @app.exception_handler(_NotServing)
    async def _not_serving(_request, exc: _NotServing) -> JSONResponse:  # noqa: RUF029
        return JSONResponse(status_code=503, content={"contract": CONTRACT_MARK, "error": "DATA_NOT_BUILT",
                                                      "message": str(exc)})

    def curated(registry: Registry) -> list:
        return sorted((q for q in registry.qualifications() if q.coverage is Coverage.CURATED), key=lambda q: q.id)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        if not FRONTEND.is_file():
            raise HTTPException(status_code=404, detail="frontend/index.html is missing")
        return FileResponse(FRONTEND, media_type="text/html")

    @app.get("/demo/status")
    def status() -> dict[str, object]:
        registry = state["registry"]
        build = registry.build if isinstance(registry, Registry) else None
        try:
            serving()
            ready, reason = True, None
        except _NotServing as exc:
            ready, reason = False, str(exc)
        return {
            "contract": CONTRACT_MARK,
            "serving": ready,
            "reason": reason if reason or not state["error"] else state["error"],
            "data_build_id": build.data_build_id if build else None,
            "validation": build.validation if build else None,
            "counts": dict(build.counts) if build else None,
            "module_a": "NO_GO",
            "engine_default_nsqf_level_match": cfg.engine.nsqf_level_match,
            "path_limits": {"max_steps_default": cfg.paths.max_steps_default,
                            "max_steps_limit": cfg.paths.max_steps_limit},
            "notices": list(NOTICES),
        }

    @app.get("/demo/qualifications")
    def qualifications() -> dict[str, object]:
        registry = serving()
        items = [{"code": q.code, "title": q.titles.qf or q.titles.qp or q.titles.catalogue or q.code,
                  "nsqf_level": q.nsqf_level.value, "min_age": q.min_age.value if q.min_age else None,
                  "hours": {k: (getattr(q.hours, k).value if getattr(q.hours, k) else None)
                            for k in ("theory", "practical", "ojt_mandatory", "ojt_recommended", "total")}}
                 for q in curated(registry)]
        return _envelope(registry, curated=items,
                         catalogue_only_count=sum(1 for q in registry.qualifications()
                                                  if q.coverage is Coverage.CATALOGUE_ONLY))

    @app.post("/demo/eligibility")
    def eligibility(req: EligibilityRequest) -> dict[str, object]:
        registry = serving()
        try:
            target = registry.qualification_by_code(req.target_code)
        except UnknownEntityError:
            raise HTTPException(status_code=422, detail={"error": "UNKNOWN_QUALIFICATION_CODE",
                                                         "code": req.target_code}) from None
        if target.coverage is not Coverage.CURATED or target.eligibility is None:
            raise HTTPException(status_code=422, detail={"error": "TARGET_NOT_EVALUABLE", "code": req.target_code})
        try:
            result = evaluate(target.eligibility, req.profile, EngineConfig(nsqf_level_match=req.nsqf_level_match),
                              registry)
        except UnknownEntityError as exc:
            raise HTTPException(status_code=422, detail={"error": "UNKNOWN_QUALIFICATION_CODE", "message": str(exc)}) \
                from None
        except EligibilityError as exc:
            raise HTTPException(status_code=422, detail={"error": "ELIGIBILITY_ERROR", "message": str(exc)}) from None
        return _envelope(registry, nsqf_level_match=req.nsqf_level_match, result=result.model_dump(mode="json"))

    @app.post("/demo/explore")
    def explore_journey(req: ExploreRequest) -> dict[str, object]:
        registry = serving()
        try:
            body = explore(req, registry, cfg)
        except ExploreError as exc:
            raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from None
        except LimitExceededError as exc:
            raise HTTPException(status_code=422, detail={"error": "LIMIT_EXCEEDED", "message": str(exc)}) from None
        except (UnknownEntityError, EligibilityError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={"error": "VALIDATION_ERROR", "message": str(exc)}) from None
        return _envelope(registry, nsqf_level_match=req.nsqf_level_match, **body)

    @app.post("/demo/paths")
    def paths(req: PathsRequest) -> dict[str, object]:
        registry = serving()
        steps = req.max_steps if req.max_steps is not None else cfg.paths.max_steps_default
        try:
            raw = enumerate_paths(req.profile, registry, EngineConfig(nsqf_level_match=req.nsqf_level_match),
                                  Scenario(), steps, req.target_code, max_expansions=cfg.paths.max_expansions,
                                  max_steps_limit=cfg.paths.max_steps_limit)
        except LimitExceededError as exc:
            raise HTTPException(status_code=422, detail={"error": "LIMIT_EXCEEDED", "message": str(exc)}) from None
        except TargetNotEvaluableError:
            raise HTTPException(status_code=422, detail={"error": "TARGET_NOT_EVALUABLE", "code": req.target_code}) \
                from None
        except UnknownEntityError as exc:
            raise HTTPException(status_code=422, detail={"error": "UNKNOWN_QUALIFICATION_CODE", "message": str(exc)}) \
                from None
        except (EligibilityError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={"error": "VALIDATION_ERROR", "message": str(exc)}) from None
        titles = {q.code: q.titles.qf or q.titles.qp or q.code for q in curated(registry)}
        out = [{
            "verdict": p.verdict.value,
            "steps": [{
                "index": s.index,
                "target_code": s.target_code,
                "title": titles.get(s.target_code, s.target_code),
                "verdict": s.eligibility.verdict.value,
                "from_state": list(s.from_state),
                "unknown_reasons": sorted({u.code.value for u in s.eligibility.unknown_reasons}),
                "condition_count": len(s.eligibility.conditions),
            } for s in p.steps],
        } for p in raw]
        return _envelope(registry, nsqf_level_match=req.nsqf_level_match, max_steps=steps, ordering="ENUMERATION_ORDER",
                         paths=out)

    return app
