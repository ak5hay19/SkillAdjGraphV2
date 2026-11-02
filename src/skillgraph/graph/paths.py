"""Bounded path enumeration, the P3.6a core (ARCHITECTURE §13.1; API_SPEC §4 and E09; TASKS P3.6).

``enumerate_paths`` walks simple paths over the ``CURATED`` qualifications the profile does not hold, depth first, and keeps a
step only if its eligibility verdict is not ``NOT_MET``. Eligibility of every step is decided by ``eligibility.evaluate``
(P3.3); nothing here decides a verdict except the ``and_`` fold of a path. The module reads no inference edge, no static edge,
no credit, no hours figure, no occupation and no labour-market value, so none of those can influence which paths exist, their
verdicts or their order. Imports: ``model/``, ``registry/``, ``eligibility/`` and ``graph.edges`` (for ``GraphError``) only;
never ``settings`` (ARCHITECTURE §6.2, amendment A-4). It is pure: no I/O, no global state, no randomness.

**Contract amendments** (documented in API_SPEC §4 and TASKS P3.6): the limits ``max_expansions`` and ``max_steps_limit`` are
required keyword-only arguments with no default; the caller supplies the validated ``Settings.paths`` values.

**Guard and argument rules (TASKS P3.6 O-1 and O-2, approved 2026-11-02).** Arguments are validated first, before anything is
enumerated or evaluated: ``max_steps``, ``max_expansions`` and ``max_steps_limit`` must be ``int`` and not ``bool``
(``TypeError``) and at least 1 (``ValueError``); ``max_steps > max_steps_limit`` raises ``LimitExceededError``. The guard then
computes ``estimate = n ** max_steps``, ``n`` being the number of ``CURATED`` qualifications not already held, and raises
``LimitExceededError`` only if ``estimate > max_expansions`` (equal is allowed). It is a conservative budget estimate and not
an exact count of evaluations, and it is computed before any eligibility evaluation.

**Implementation decisions P-1 to P-5 (explicit user decisions of 2026-11-02; the contract does not specify them):**

* P-1  every valid non-empty prefix of a path is returned as its own path, in depth-first pre-order (a path before its
  extensions; candidates in ascending ``qualification_id``). With ``target_code`` only paths whose last step is the target are
  returned. Stopping the search at the target changes no result (no qualification repeats); it is only an optimisation.
* P-2  a ``target_code`` that the profile already holds gives an empty list.
* P-3  an unknown ``target_code`` raises ``UnknownEntityError`` (registry); an existing ``CATALOGUE_ONLY`` one raises
  ``TargetNotEvaluableError``, before any evaluation.
* P-4  a ``CURATED`` qualification with no structured eligibility (``eligibility is None``) raises ``EligibilityError``; it is
  never skipped silently. (A specification without rows already raises it in ``evaluate``, P3.3 D-1.)
* P-5  ``RawStep.from_state`` is the profile's declared registry holdings sorted ascending, then the earlier targets of the
  path in step order.

**Scenario (user decision of 2026-11-02; the departure from E09 is UNRESOLVED).** Only the default scenario is supported. A
scenario that changes any field raises ``ScenarioNotSupportedError`` rather than being ignored. This is an internal limitation
of P3.6a and must not be exposed through a façade. Scenario flags belong to the later P3.6b run.

**Hypothetical relevance (PROVISIONAL, TASKS P3.6 A-3 / O-4).** After a step, its target is a holding of origin
``HYPOTHETICAL`` for later steps. Its relevance cannot be declared by a profile, so where it is what satisfies a prior-level
component the result is ``UNKNOWN(RELEVANCE_NOT_DECLARED)``, never ``NOT_MET``. The profile is never changed.

**Path identity (P3.6b, API_SPEC §4 amendment A-6, decided 2026-11-02).** ``path_id = "p-" + sha256_hex(canonical_json(payload))[:12]``
(lowercase hex; ``json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`` as UTF-8), ``payload`` being exactly
``{"config": <EngineConfig>, "profile_digest": <the caller's digest>, "scenario": <Scenario>, "steps": [<ordered step target
codes>]}``, the models serialised with ``model_dump(mode="json")``. ``profile_digest`` is a required keyword-only argument with no
default, supplied by the caller (``eligibility.evaluate.identity_profile_digest`` of the same ``state``); this module neither
imports ``logging_setup`` nor computes it, and it only checks the format ``^sha256:[0-9a-f]{64}$`` (``TypeError`` for a
non-``str``, ``ValueError`` otherwise), before enumeration. Excluded from the identity: the build ID, ``sort_by``, ``limit``,
``include_inference``, ``max_steps``, ``target_code`` and every ranking or display setting. Two paths with the same ID in one
result raise ``GraphError``. A path ID identifies a query, not a result: another build can give the same ID a different verdict.
The identity never influences which paths exist, their verdicts or their order.

**Not yet implemented:** ranking, hours and totals, explanations, inference annotations, ``is_hypothetical`` and the scenario
flags. ``Q-B`` stays ``undecided_level_use = COMPARE`` (the ``evaluate`` default), PROVISIONAL.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, StrictStr, StringConstraints, model_validator

from skillgraph.eligibility.evaluate import EligibilityError, EligibilityResult, EngineConfig, ProfileState, evaluate
from skillgraph.eligibility.logic import and_
from skillgraph.graph.edges import GraphError
from skillgraph.model.base import Number, SchemaModel
from skillgraph.model.eligibility import Verdict
from skillgraph.model.ids import QualificationCode
from skillgraph.model.qualification import Coverage, Qualification
from skillgraph.registry import Registry

__all__ = [
    "IncrementalHoursPolicy",
    "LimitExceededError",
    "RawPath",
    "RawStep",
    "Scenario",
    "ScenarioNotSupportedError",
    "TargetNotEvaluableError",
    "enumerate_paths",
]


_PATH_ID_PATTERN = r"^p-[0-9a-f]{12}$"
_PROFILE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class LimitExceededError(GraphError):
    """``max_steps`` exceeds the hard limit, or the estimated expansion exceeds the budget (API_SPEC ``LIMIT_EXCEEDED``)."""


class TargetNotEvaluableError(GraphError):
    """The target exists but is not ``CURATED``, so it has no eligibility evidence (API_SPEC ``TARGET_NOT_EVALUABLE``)."""


class ScenarioNotSupportedError(GraphError):
    """P3.6a supports the default scenario only. An internal limitation; E09 itself accepts such scenarios (UNRESOLVED)."""


class IncrementalHoursPolicy(StrEnum):
    NONE = "NONE"
    EXCLUDE_SHARED_NOS_CODE = "EXCLUDE_SHARED_NOS_CODE"
    EXCLUDE_SHARED_NOS_CODE_AND_VERSION = "EXCLUDE_SHARED_NOS_CODE_AND_VERSION"


class Scenario(SchemaModel):
    """API_SPEC §2.3. Every default is "no assumption"; a non-default value is unsupported in P3.6a."""

    assume_intermediate_relevance: StrictBool = False
    assumed_experience_gain_years_per_step: Annotated[Number, Field(ge=0, le=5)] = 0
    incremental_hours_policy: IncrementalHoursPolicy = IncrementalHoursPolicy.NONE


class RawStep(SchemaModel):
    """One qualification entered by a path, with the full eligibility result that allowed it (never ``NOT_MET``)."""

    index: Annotated[StrictInt, Field(ge=1)]
    from_state: tuple[StrictStr, ...]
    target_code: QualificationCode
    eligibility: EligibilityResult

    @model_validator(mode="after")
    def _check(self) -> RawStep:
        if self.eligibility.verdict is Verdict.NOT_MET:
            raise ValueError("a NOT_MET step is never part of a path")
        if self.eligibility.target.code != self.target_code:
            raise ValueError("the eligibility result belongs to another qualification")
        if self.target_code in self.from_state:
            raise ValueError("a step cannot enter a qualification that is already held")
        return self


class RawPath(SchemaModel):
    """The minimum path (API_SPEC §4, A-5, A-6): identifier, ordered steps and their ``and_`` verdict. No rank or total."""

    path_id: Annotated[StrictStr, StringConstraints(pattern=_PATH_ID_PATTERN)]
    steps: Annotated[tuple[RawStep, ...], Field(min_length=1)]
    verdict: Verdict

    @property
    def target_codes(self) -> tuple[str, ...]:
        """The ordered qualifications entered (one component of the identity; see ``path_id``)."""
        return tuple(s.target_code for s in self.steps)

    @model_validator(mode="after")
    def _check(self) -> RawPath:
        if [s.index for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("step indexes must be 1, 2, … in order")
        if len(set(self.target_codes)) != len(self.steps):
            raise ValueError("a qualification is never repeated in a path")
        if self.verdict is not and_(*(s.eligibility.verdict for s in self.steps)):
            raise ValueError("the path verdict is the AND of its step verdicts")
        return self


def _int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int (not a bool), got {type(value).__name__}")
    return value


def _path_id(config: EngineConfig, scenario: Scenario, profile_digest: str, step_codes: tuple[str, ...]) -> str:
    """``"p-"`` + the first 12 lowercase hex characters of the SHA-256 of the canonical JSON of exactly
    ``{config, profile_digest, scenario, steps}`` (API_SPEC §4, A-6). Nothing else enters the identity."""
    payload = {"config": config.model_dump(mode="json"), "profile_digest": profile_digest,
               "scenario": scenario.model_dump(mode="json"), "steps": list(step_codes)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "p-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _require_unique_ids(paths: list[RawPath]) -> None:
    seen: dict[str, tuple[str, ...]] = {}
    for p in paths:
        if p.path_id in seen:
            raise GraphError(f"duplicate path_id {p.path_id} for {list(seen[p.path_id])} and {list(p.target_codes)}")
        seen[p.path_id] = p.target_codes


def _validate(state: object, registry: object, config: object, scenario: object, max_steps: object,
              target_code: object, max_expansions: object, max_steps_limit: object, profile_digest: object) -> None:
    """Every argument check, in a fixed order, before anything is enumerated or evaluated (O-2)."""
    for obj, cls, name in ((state, ProfileState, "state"), (registry, Registry, "registry"),
                           (config, EngineConfig, "config"), (scenario, Scenario, "scenario")):
        if not isinstance(obj, cls):
            raise TypeError(f"{name} must be a {cls.__name__}, got {type(obj).__name__}")
    if target_code is not None and not isinstance(target_code, str):
        raise TypeError(f"target_code must be a str or None, got {type(target_code).__name__}")
    if not isinstance(profile_digest, str):
        raise TypeError(f"profile_digest must be a str, got {type(profile_digest).__name__}")
    if not _PROFILE_DIGEST.fullmatch(profile_digest):
        raise ValueError("profile_digest must match ^sha256:[0-9a-f]{64}$")
    values = {"max_steps": _int(max_steps, "max_steps"), "max_expansions": _int(max_expansions, "max_expansions"),
              "max_steps_limit": _int(max_steps_limit, "max_steps_limit")}
    for name, v in values.items():
        if v < 1:
            raise ValueError(f"{name} must be at least 1, got {v}")
    if values["max_steps"] > values["max_steps_limit"]:
        raise LimitExceededError(
            f"max_steps {values['max_steps']} exceeds the hard limit {values['max_steps_limit']}")


def enumerate_paths(
    state: ProfileState,
    registry: Registry,
    config: EngineConfig,
    scenario: Scenario,
    max_steps: int,
    target_code: str | None,
    *,
    max_expansions: int,
    max_steps_limit: int,
    profile_digest: str,
) -> list[RawPath]:
    """Enumerate the simple paths of up to ``max_steps`` ``CURATED`` qualifications that the profile may enter.

    Returns the paths in depth-first pre-order (P-1). Raises ``TypeError`` / ``ValueError`` / ``LimitExceededError`` for
    arguments (module notes), ``ScenarioNotSupportedError`` for a non-default scenario, ``UnknownEntityError`` for an unknown
    code, ``TargetNotEvaluableError`` for a non-``CURATED`` target, ``EligibilityError`` for a ``CURATED`` qualification
    without structured rules, ``GraphError`` for a duplicate ``path_id``, and whatever ``eligibility.evaluate`` raises for
    malformed data. A valid but incomplete profile never raises: it gives ``UNKNOWN`` steps. ``state`` is never changed.
    ``profile_digest`` is the caller's ``identity_profile_digest(state)`` and only feeds ``RawPath.path_id`` (module notes)."""
    _validate(state, registry, config, scenario, max_steps, target_code, max_expansions, max_steps_limit, profile_digest)
    if scenario != Scenario():
        changed = sorted(k for k, v in scenario.model_dump().items() if v != getattr(Scenario(), k))
        raise ScenarioNotSupportedError(f"P3.6a supports only the default scenario; non-default: {', '.join(changed)}")
    if target_code is not None and registry.qualification_by_code(target_code).coverage is not Coverage.CURATED:
        raise TargetNotEvaluableError(f"{target_code} is not CURATED and has no eligibility evidence")

    declared = tuple(sorted(state.held_qualification_codes or ()))
    for code in declared:
        registry.qualification_by_code(code)  # an unknown held code fails here, whatever the search would reach
    candidates: tuple[Qualification, ...] = tuple(sorted(
        (q for q in registry.qualifications() if q.coverage is Coverage.CURATED and q.code not in declared),
        key=lambda q: q.id))

    estimate = len(candidates) ** max_steps  # the guard: before any evaluation (O-1)
    if estimate > max_expansions:
        raise LimitExceededError(
            f"estimated expansion {len(candidates)}**{max_steps} = {estimate} exceeds max_expansions {max_expansions}")
    if target_code is not None and target_code in declared:
        return []  # P-2
    for q in candidates:
        if q.eligibility is None:
            raise EligibilityError(f"{q.code}: a CURATED qualification without structured eligibility rules (P-4)")

    found: list[RawPath] = []

    def walk(steps: tuple[RawStep, ...]) -> None:
        taken = tuple(s.target_code for s in steps)
        for q in candidates:
            if q.code in taken:
                continue
            result = evaluate(q.eligibility, state, config, registry, hypothetical_codes=taken)
            if result.verdict is Verdict.NOT_MET:
                continue  # never emitted and never extended
            step = RawStep(index=len(steps) + 1, from_state=declared + taken, target_code=q.code, eligibility=result)
            new = (*steps, step)
            at_target = target_code is None or q.code == target_code
            if at_target:
                found.append(RawPath(path_id=_path_id(config, scenario, profile_digest, tuple(s.target_code for s in new)),
                                     steps=new, verdict=and_(*(s.eligibility.verdict for s in new))))
            if q.code != target_code and len(new) < max_steps:  # past the target nothing can end at it (no repeats)
                walk(new)

    walk(())
    _require_unique_ids(found)
    return found
