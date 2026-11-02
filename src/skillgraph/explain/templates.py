"""Deterministic explanation templates for an eligibility result (ARCHITECTURE §13.3; API_SPEC §2.2, §4; TASKS P3.8).

``for_eligibility(result, registry)`` turns an ``EligibilityResult`` into a list of ``ExplanationItem``. It is a pure function:
no I/O, no clock, no randomness, no language model, no network. It only *reads* what the engine already decided; it never
changes a verdict, a condition, a flag or any other field of the result, and it imports nothing from ``graph``, ``api``,
``judge`` or any model client.

Scope of this stage (user decisions of 2026-11-02): ``for_eligibility`` only. ``for_path`` is NOT built, because ``RawPath``
carries no hours, shared-NOS or progression data (TASKS P3.6 O-5 assigns them to no stage) and ranking (P3.7) is not built.
An OVERLAP item is not produced either: an overlap is a statement about two qualifications (consecutive path steps), and an
``EligibilityResult`` names only the target.

Evidence rules (decided 2026-11-02, "cite stored IDs, label the rest"):

* Every item has an evidence class.
* A statement drawn from the official rule text or official hours is class OFFICIAL and cites the stored evidence IDs.
* A statement about what the engine concluded is class RULE_DERIVED and cites the stored evidence IDs of the components it
  summarises. Those IDs are copied from the result (or from the registry's official hours); none is ever created here.
* A condition is class DECLARED or CONFIG (as the engine labelled it). It is request-scoped, so it has no record of its own;
  it cites the stored IDs of the deciding components that carry that very condition, and of no other component. The result
  keeps enough provenance for this: a DECLARATION condition is the component's own ``condition`` (API_SPEC §2.4), and any other
  condition's key must also be among that component's ``inputs_used`` (``eligibility/components.py``, ``ComponentOutcome``
  validator). A CONFIG condition is therefore attributed to the CONDITIONAL deciding components that used that key with that
  value. A condition that no deciding component carries makes the result inconsistent, and ``ExplanationError`` is raised
  instead of guessing a link.
* The CAVEAT item is not a factual statement about the data. It carries no evidence ID, as in the API_SPEC example.
* If a factual item cannot cite any stored ID, ``ExplanationError`` is raised: the data defect is surfaced, not papered over.

What the cited IDs do and do not prove. ``Evidence`` records hold a source, a page and/or location, a method and a value
status, but not the value itself. This module copies IDs from the result and the registry; it does not look a claim up in the
source, and nothing in the stored data would let it check that a record states a given figure. A resolvable ID is a pointer,
not proof of content-level support. The registry validates evidence references when a build is loaded (``registry.load``);
this function does not resolve component IDs again. It does resolve the HOURS IDs, only to report the official source page.

Consistency guard: ``for_eligibility`` refuses a result whose own parts contradict each other (a verdict that is not the
lattice fold of its rows, decisive rows that are not the rows attaining the verdict, a result without rows, a conditional
result without a deciding row). It re-derives nothing to *replace* the engine's verdicts; it only refuses to explain data that
disagrees with itself.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from skillgraph.eligibility.components import Condition, ConditionKind
from skillgraph.eligibility.evaluate import ComponentResult, EligibilityResult, ExplanationItem, RowResult
from skillgraph.eligibility.logic import and_, or_
from skillgraph.model.conflict import ConflictStatus
from skillgraph.model.eligibility import UnknownReasonCode, Verdict
from skillgraph.model.evidence import EvidenceClass, QualityFlagCode, ValueStatus
from skillgraph.registry import Registry, UnknownEntityError

__all__ = ["CAVEAT_TEXT", "ExplanationError", "for_eligibility"]

CAVEAT_TEXT = (
    "This is an eligibility reading of official documents, not a prediction of admission, employability, placement or "
    "earnings. It does not establish enrolment, a job transition or any reduction in the training required."
)

_INPUT_CLASS = {
    "DECLARED": "declared",
    "CONFIG": "configuration choice",
    "OFFICIAL": "official",
    "HYPOTHETICAL": "assumed completed on a path, not held",
}

_AGAIN = "the result would then be evaluated again and could still be not met, conditional or unknown"
_NO_INPUT = "no profile or configuration input changes the outcome of this requirement"

# Guidance per cause code. Each entry restates only what the engine's own cause code and its documented meaning (API_SPEC
# §2.1, §2.4; ARCHITECTURE §7, §11.3) support. None promises that the result will change, and none approves, applies or
# assumes anything. A code without an entry gets ``_NO_GUIDANCE`` and the test suite fails until it is added.
_GUIDANCE: dict[UnknownReasonCode, str] = {
    UnknownReasonCode.INPUT_NOT_DECLARED:
        f"Adding the missing input to the profile would let the engine evaluate this requirement; {_AGAIN}.",
    UnknownReasonCode.RELEVANCE_NOT_DECLARED:
        "The engine does not assume that a prior qualification or experience is relevant. Where the profile can declare "
        f"relevance, the declaration would be recorded as an unverified condition and {_AGAIN}.",
    UnknownReasonCode.CONFIG_UNSET:
        f"This is a configuration choice that the engine does not make on anyone's behalf; once it is made, {_AGAIN}.",
    UnknownReasonCode.EQUIVALENCE_UNDEFINED:
        "The current sources do not define an equivalence for this requirement, so no profile or configuration input "
        "resolves it.",
    UnknownReasonCode.CREDENTIAL_ORDER_UNDEFINED:
        "The current sources do not define an order among the credentials, so no profile or configuration input resolves it.",
    UnknownReasonCode.ENROLMENT_NOT_MODELLED: f"The engine does not model this route, so {_NO_INPUT}.",
    UnknownReasonCode.LITERACY_NOT_MODELLED: f"The engine does not model this route, so {_NO_INPUT}.",
    UnknownReasonCode.NTC_NAC_CITS_NOT_MODELLED: f"The engine does not model this route, so {_NO_INPUT}.",
    UnknownReasonCode.DIPLOMA_YEAR_NOT_MODELLED: f"The engine does not model this route, so {_NO_INPUT}.",
    UnknownReasonCode.REVIEW_FLAG:
        f"The audit flagged this requirement's text for review and it stays unevaluated; {_NO_INPUT}.",
    UnknownReasonCode.UNCERTAIN_EXTRACTION:
        f"The value has not been substantiated against its source and stays unevaluated until it is; {_NO_INPUT}.",
    UnknownReasonCode.SOURCE_CONFLICT:
        f"The sources disagree on a value this requirement depends on and it stays unevaluated; {_NO_INPUT}.",
    UnknownReasonCode.OVERLAY_NOT_APPROVED:
        "Only a proposed overlay exists for this value and the engine does not apply it. The curated rules use such a "
        "proposal only if it is listed in the project's overlay approvals, which records an explicit approval by the "
        f"project owner; this tool neither makes nor assumes that approval. {_NO_INPUT.capitalize()}.",
    UnknownReasonCode.ENGINE_USE_UNDECIDED:
        "The audit assigned this requirement no safe use. Only a new audit decision on that cell changes this; "
        f"{_NO_INPUT}.",
}
_NO_GUIDANCE = "No resolution is documented for this cause."

_UNCERTAIN_STATUS = frozenset({ValueStatus.PARSED_UNCERTAIN, ValueStatus.UNRESOLVED})


class ExplanationError(ValueError):
    """A result cannot be explained honestly: a factual statement has no stored evidence ID to cite, or a reference does not
    resolve. This is a data defect, not a verdict."""


# --------------------------------------------------------------------------------------------------------------------
# Formatting (deterministic; no locale, no dict-order dependence)
# --------------------------------------------------------------------------------------------------------------------


def _num(v: float | int) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v) if isinstance(v, int) else format(v, ".10g")


def _val(v: object) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def _inputs(c: ComponentResult) -> str:
    if not c.inputs_used:
        return "none recorded"
    return "; ".join(f"{i.field} = {_val(i.value)} ({_INPUT_CLASS[i.evidence_class.value]})" for i in c.inputs_used)


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _ids(components: Iterable[ComponentResult], what: str) -> tuple[str, ...]:
    ids = _unique(e for c in components for e in c.evidence_ids)
    if not ids:
        raise ExplanationError(f"{what}: no stored evidence ID to cite")
    return ids


def _flag_codes(codes: Iterable[QualityFlagCode]) -> tuple[QualityFlagCode, ...]:
    return tuple(sorted(set(codes), key=lambda f: f.value))


# --------------------------------------------------------------------------------------------------------------------
# Component and row wording (restates what the engine returned; adds no reason of its own)
# --------------------------------------------------------------------------------------------------------------------


def _component_sentence(c: ComponentResult) -> str:
    what = f"Requirement \"{c.requirement_text}\"" if c.requirement_text.strip() else "The empty source cell"
    head = f"{what} is {c.verdict.value}"
    if c.verdict is Verdict.MET:
        return f"{head}; inputs used: {_inputs(c)}."
    if c.verdict is Verdict.NOT_MET:
        return f"{head} on the declared inputs; inputs used: {_inputs(c)}."
    if c.verdict is Verdict.CONDITIONAL and c.condition is not None:
        return f"{head}: {c.condition.text} Inputs used: {_inputs(c)}."
    if c.verdict is Verdict.UNKNOWN and c.unknown_reason is not None:
        r = c.unknown_reason
        return f"{head}: it cannot be determined. {r.text} (reason {r.code.value}; inputs used: {_inputs(c)})."
    return f"{head}; inputs used: {_inputs(c)}."  # a hand-built result that breaks the engine's invariants is still described


def _row_text(row: RowResult) -> str:
    parts = [f"Entry row {row.s_no} (\"{row.raw_text}\") is {row.verdict.value}."]
    parts += [_component_sentence(c) for c in row.components]
    parts += [f"Note ({f.code.value}): {f.message}" + (f" [{', '.join(f.refs)}]" if f.refs else "") for f in row.flags]
    return " ".join(parts)


def _decisive(result: EligibilityResult) -> tuple[RowResult, ...]:
    wanted = set(result.decisive_rule_ids)
    return tuple(r for r in result.rows if r.rule_id in wanted)


def _components_by_id(result: EligibilityResult) -> dict[str, ComponentResult]:
    return {c.component_id: c for c in (result.age, *(c for r in result.rows for c in r.components))}


def _check_consistent(result: EligibilityResult) -> None:
    """Refuse a result whose parts contradict each other. This never changes or replaces a verdict; it only refuses to
    explain data that disagrees with itself (the engine's own constructor cannot produce such a result)."""
    if not result.rows:
        raise ExplanationError("a result without entry rows cannot be explained: the engine refuses a specification "
                               "without rows (evaluate.py D-1)")
    ids = [r.rule_id for r in result.rows]
    if len(set(ids)) != len(ids):
        raise ExplanationError("the result lists the same entry row twice")
    stray = [d for d in result.decisive_rule_ids if d not in ids]
    if stray:
        raise ExplanationError(f"decisive rule {stray[0]!r} is not an entry row of the result")
    for r in result.rows:
        if r.components and r.verdict is not and_(*(c.verdict for c in r.components)):
            raise ExplanationError(f"row {r.s_no}: its verdict {r.verdict.value} is not the lowest verdict of its components")
    if result.verdict is Verdict.CONDITIONAL and not result.decisive_rule_ids:
        raise ExplanationError("a CONDITIONAL result with no deciding row cannot be explained: a condition always arises in "
                               "a deciding row, and the engine cannot produce this shape")
    folded = and_(result.age.verdict, or_(*(r.verdict for r in result.rows)))
    if folded is not result.verdict:
        raise ExplanationError(f"the result verdict {result.verdict.value} is not the fold of its age and rows ({folded.value})")
    expected = {r.rule_id for r in result.rows if result.verdict is Verdict.NOT_MET or r.verdict is result.verdict}
    if expected != set(result.decisive_rule_ids):
        raise ExplanationError("the decisive rows are not the rows that attain the result verdict")


def _carrying(condition: Condition, components: Iterable[ComponentResult]) -> list[ComponentResult]:
    """The CONDITIONAL components that carry exactly this condition. A DECLARATION condition is the component's own
    ``condition``; any other kind must also be among the component's ``inputs_used`` (a model invariant), so it is matched
    by key and value there."""
    found = []
    for c in components:
        if c.verdict is not Verdict.CONDITIONAL:
            continue
        if condition.kind is ConditionKind.DECLARATION:
            if c.condition == condition:
                found.append(c)
        elif any(u.field == condition.key and u.value == condition.value for u in c.inputs_used):
            found.append(c)
    return found


# --------------------------------------------------------------------------------------------------------------------
# Items
# --------------------------------------------------------------------------------------------------------------------


def _summary_text(result: EligibilityResult, decisive: tuple[RowResult, ...]) -> str:
    t = f"{result.target.title} ({result.target.code})"
    v = result.verdict
    if v is Verdict.MET:
        text = f"Met: on the declared inputs, the modelled entry requirements for {t} are satisfied."
    elif v is Verdict.CONDITIONAL:
        text = (f"Conditional: the modelled entry requirements for {t} are satisfied only if the conditions listed below "
                "hold. They rest on declarations or configuration choices that the engine cannot verify.")
    elif v is Verdict.UNKNOWN:
        n = len(result.unknown_reasons)
        text = (f"Unknown: the engine cannot determine whether the modelled entry requirements for {t} are met, because "
                f"{n} item{'s are' if n != 1 else ' is'} missing, unmodelled or unresolved (listed below). "
                "Unknown is not a negative result.")
    else:
        why = []
        if result.age.verdict is Verdict.NOT_MET:
            why.append("the age requirement is not met")
        if result.rows and all(r.verdict is Verdict.NOT_MET for r in result.rows):
            why.append("no entry row is met")
        text = (f"Not met: for {t}, " + (" and ".join(why) if why else "the modelled requirements are not met")
                + " on the declared inputs.")
    if v is not Verdict.NOT_MET:
        if decisive:
            text += " Deciding entry row" + ("s" if len(decisive) != 1 else "") + ": " + ", ".join(str(r.s_no) for r in decisive) + "."
        elif result.age.verdict is v:
            text += " The age requirement limits this result; no entry row attains it."
    return text


def _source_page_note(registry: Registry, evidence_ids: Iterable[str]) -> str:
    """The official source page(s) of the cited hours values, as recorded on their evidence records. Never invented: with no
    recorded page the text says so."""
    pages: set[str] = set()
    without = 0
    for e in evidence_ids:
        try:
            rec = registry.evidence_by_id(e)
        except UnknownEntityError:
            without += 1
            continue
        if rec.evidence_class is EvidenceClass.OFFICIAL and rec.page:
            pages.add(rec.page)
        else:
            without += 1
    if not pages:
        return " The source page is not recorded in the available metadata."
    note = f" Source {'page' if len(pages) == 1 else 'pages'}: {', '.join(sorted(pages))}."
    return note + (" The page is not recorded for every one of these values." if without else "")


def _conflict_note(registry: Registry, conflict_ids: Iterable[str]) -> str:
    parts = []
    for cid in conflict_ids:
        try:
            status = registry.conflict_by_id(cid).status
        except UnknownEntityError:
            parts.append(f"a source conflict is recorded ({cid}) but its record is not available")
            continue
        parts.append(f"a lead whose other source is unavailable remains unresolved ({cid})"
                     if status is ConflictStatus.UNRESOLVED_LEAD_SOURCE_UNAVAILABLE
                     else f"the sources disagree and the conflict is unresolved ({cid})")
    return " For at least one of these values " + "; ".join(parts) + ", so the stated figure is not settled."


def _hours_item(result: EligibilityResult, registry: Registry) -> ExplanationItem | None:
    q = registry.qualification_by_code(result.target.code)  # UnknownEntityError propagates: the registry does not match
    h = q.hours
    if h.total.value is None or h.total.evidence_id is None:
        return None  # nothing citable: say nothing rather than state hours without a source
    parts = [("theory", h.theory), ("practical", h.practical),
             ("on-the-job training (mandatory)", h.ojt_mandatory), ("on-the-job training (recommended)", h.ojt_recommended)]
    shown = [(name, v) for name, v in parts if v is not None and v.value is not None and v.evidence_id is not None]
    cited = [h.total, *(v for _, v in shown)]
    flags = {QualityFlagCode.NO_OFFICIAL_REDUCTION_SOURCE}
    conflicts = _unique(v.conflict_id for v in cited if v.conflict_id is not None)
    if conflicts:
        flags.add(QualityFlagCode.SOURCE_CONFLICT)
    if any(v.value_status in _UNCERTAIN_STATUS for v in cited):
        flags.add(QualityFlagCode.UNCERTAIN_EXTRACTION)
    ids = _unique(v.evidence_id for v in cited)
    text = (f"Official notional training hours for {result.target.title}: {_num(h.total.value)} in total"
            + (" (" + ", ".join(f"{n} {_num(v.value)}" for n, v in shown) + ")" if shown else "")
            + "." + _source_page_note(registry, ids)
            + " This is the documented duration of the full qualification, not personal effort, calendar time or cost; "
              "the project's documentation records no source that defines a reduced route.")
    if conflicts:
        text += _conflict_note(registry, conflicts)
    if QualityFlagCode.UNCERTAIN_EXTRACTION in flags:
        text += " At least one of these values was extracted with uncertainty."
    return ExplanationItem(kind="HOURS", text=text, evidence_class=EvidenceClass.OFFICIAL, evidence_ids=ids,
                           flags=_flag_codes(flags))


def for_eligibility(result: EligibilityResult, registry: Registry) -> list[ExplanationItem]:
    """The explanation of one eligibility result, in a fixed order: verdict summary, age, each entry row, conditions,
    what would resolve this, hours, progression claims, caveat. Identical inputs give identical output.

    Raises ``TypeError`` for a wrong argument type; ``ExplanationError`` if the result contradicts itself (see the module
    notes), a factual item has no stored evidence ID to cite, an unknown reason refers to no component, or a condition is
    carried by no deciding component; and ``UnknownEntityError`` if the target is not in ``registry``. The result is not
    modified.
    """
    if not isinstance(result, EligibilityResult):
        raise TypeError(f"result must be an EligibilityResult, got {type(result).__name__}")
    if not isinstance(registry, Registry):
        raise TypeError(f"registry must be a Registry, got {type(registry).__name__}")

    _check_consistent(result)
    decisive = _decisive(result)
    decisive_components = [c for r in decisive for c in r.components]
    derived = EvidenceClass.RULE_DERIVED
    items: list[ExplanationItem] = []

    # 1. verdict summary: cites the age component and the components of the deciding rows
    items.append(ExplanationItem(
        kind="VERDICT_SUMMARY", text=_summary_text(result, decisive), evidence_class=derived,
        evidence_ids=_ids([result.age, *decisive_components], "verdict summary"),
        flags=_flag_codes(f.code for f in result.quality_flags)))

    # 2. per-row reasoning: the age requirement, then every row in the engine's order (all routes, not only the deciding ones)
    items.append(ExplanationItem(
        kind="AGE_REASONING", text="Age requirement. " + _component_sentence(result.age), evidence_class=derived,
        evidence_ids=_ids([result.age], "age reasoning")))
    for row in result.rows:
        items.append(ExplanationItem(
            kind="ROW_REASONING", text=_row_text(row), evidence_class=derived,
            evidence_ids=_ids(row.components, f"row {row.s_no}"), flags=_flag_codes(f.code for f in row.flags)))

    # 3. conditions: the engine's own condition texts, one item each, with the class the engine gave them
    if result.conditions:
        prefix = "" if result.verdict is Verdict.CONDITIONAL else (
            f"Recorded assumption on the deciding rows (the overall result is {result.verdict.value}, so this does not make "
            "it conditional): ")
        for c in result.conditions:
            carriers = _carrying(c, decisive_components)  # only the deciding components that carry this very condition
            if not carriers:
                raise ExplanationError(f"condition {c.key!r} is carried by no deciding component of the result")
            flag = {"DECLARATION": QualityFlagCode.DEPENDS_ON_DECLARATION, "CONFIG": QualityFlagCode.DEPENDS_ON_CONFIG}.get(c.kind.value)
            items.append(ExplanationItem(kind="CONDITION", text=f"{prefix}{c.text}", evidence_class=c.evidence_class,
                                         evidence_ids=_ids(carriers, f"condition {c.key}"),
                                         flags=_flag_codes([flag] if flag else [])))

    # 4. what would resolve this
    if result.verdict is Verdict.UNKNOWN:
        by_id = _components_by_id(result)
        for r in result.unknown_reasons:
            comp = by_id.get(r.ref)
            if comp is None:
                raise ExplanationError(f"unknown reason {r.code.value} refers to {r.ref!r}, which is not a component of the result")
            items.append(ExplanationItem(
                kind="WHAT_WOULD_RESOLVE", evidence_class=derived, evidence_ids=_ids([comp], f"unknown reason {r.ref}"),
                text=(f"{r.text} {_GUIDANCE.get(r.code, _NO_GUIDANCE)} "
                      f"Engine classification of who can resolve this: {r.resolvable_by}.")))
    elif result.verdict is Verdict.CONDITIONAL:
        items.append(ExplanationItem(
            kind="WHAT_WOULD_RESOLVE", evidence_class=derived, evidence_ids=_ids(decisive_components, "resolution"),
            text="This result stays conditional until each condition listed above is confirmed. The engine cannot verify a "
                 "declaration, and it does not accept a configuration choice on anyone's behalf."))

    # 5. official hours of the target (omitted when the registry gives nothing citable)
    hours = _hours_item(result, registry)
    if hours is not None:
        items.append(hours)

    # 6. progression claims: the engine's own supporting evidence, restated with its stored evidence IDs; never a verdict input
    for s in result.supporting_evidence:
        if not s.evidence_ids:
            raise ExplanationError("a supporting-evidence item has no evidence ID to cite")
        items.append(ExplanationItem(kind="PROGRESSION_CLAIM", text=s.text, evidence_class=s.evidence_class,
                                     evidence_ids=s.evidence_ids, flags=s.flags))

    # 7. caveat: always present, not a statement about the data
    items.append(ExplanationItem(kind="CAVEAT", text=CAVEAT_TEXT, evidence_class=derived))
    return items
