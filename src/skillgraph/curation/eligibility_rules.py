"""P1.5 Checkpoint B: structure the P1.4 eligibility source rows into components (ARCHITECTURE §9.2, §11).

A pure, deterministic and fail-closed layer between ``eligibility_source_rows.json`` (the immutable provenance
input) and the ``EligibilityRow`` / ``AgeRule`` models. ``config/eligibility_rules.yaml`` supplies the mapping; it
never replaces the source text and it can never raise a permission:

* every component's text must equal the source cell it names, and the cells joined with `` || `` must equal the
  row's ``raw_text`` byte for byte (nothing is trimmed, so an empty experience cell keeps its trailing delimiter);
* ``safe`` is computed from the source row or cell (``safe_from``), never read from the configuration, and only a
  computing, substantiated use makes a component safe; a sibling component is never evidence;
* the stored ``unknown_reason`` applies if and only if the computed ``safe`` is false (a computed-unsafe component
  without a configured reason is an error; a computed-safe one keeps none);
* a cell that carries an applied correction (``CORRECTION_APPLIED``) is refused (open question P1.5-A2);
* the age rules cannot be built while the source carries no verbatim item 9c text (open decision P1.5-A1): the
  components are structured, the rule itself raises ``AgeRuleBlocked`` and no text is reconstructed.

Nothing here is wired into the build: that is Checkpoint C, which also bumps ``CURATION_CODE_VERSION``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError, model_validator

from skillgraph.model.eligibility import (
    AgeRule,
    Component,
    ComponentType,
    EligibilityRow,
    EligibilitySourceRow,
    EligibilitySpec,
    ParamValue,
    SourceRowKind,
    UnknownReasonCode,
)
from skillgraph.model.evidence import SAFE_USES, EngineUse, QualityFlagCode, ValueStatus
from skillgraph.model.ids import RuleId

from .errors import BuildError

RULES_PATH = Path("config/eligibility_rules.yaml")
DELIMITER = " || "  # a space, two vertical bars, a space (ARCHITECTURE §9.2, cell mapping)

_UNCERTAIN = frozenset({ValueStatus.PARSED_UNCERTAIN, ValueStatus.UNRESOLVED})
# The uses that let the engine compute an eligibility component. SAFE_HOURS is a path-hours use and never applies.
_ELIGIBILITY_USES = SAFE_USES - {EngineUse.SAFE_HOURS}
_CREDENTIALS = frozenset({"UG_CERTIFICATE", "UG_DIPLOMA"})  # PostSchoolCredentialType without OTHER (a profile value)


class EligibilityRulesError(BuildError):
    """The eligibility structuring table or its source rows cannot be turned into rules safely."""


class AgeRuleBlocked(EligibilityRulesError):
    """P1.5-A1: the source carries no verbatim item 9c text for an age rule, and none is reconstructed."""


class CorrectionNotSupported(EligibilityRulesError):
    """P1.5-A2: a cell with an applied correction has no defined mapping to a component yet."""


# ---------------------------------------------------------------------------------------------- configuration
class Cell(StrEnum):
    ACADEMIC = "academic"
    EXPERIENCE = "experience"
    MIN_AGE = "min_age"


class SafeFrom(StrEnum):
    ROW = "row"
    CELL = "cell"
    NONE = "none"


class Review(StrEnum):
    SUPPORTED = "SUPPORTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Parameter names and exact types per component type (API_SPEC §2.4). Stored params never contain requires_relevance.
_REQUIRED_PARAMS: dict[ComponentType, dict[str, type]] = {
    ComponentType.AGE_MIN: {"min_age": int},
    ComponentType.SCHOOL_GRADE_MIN: {"grade": int},
    ComponentType.NAMED_CREDENTIAL: {"credential": str},
    ComponentType.PRIOR_NSQF_LEVEL: {"level": float},
    ComponentType.EXPERIENCE_MIN_YEARS: {"years": float},
    ComponentType.UNMODELLED: {},
}
_OPTIONAL_PARAMS: dict[ComponentType, dict[str, type]] = {ComponentType.SCHOOL_GRADE_MIN: {"below_required_verdict": str}}
# Which printed cell a component type can be read from (UNMODELLED covers either text cell, never the age).
_TYPE_CELLS: dict[ComponentType, frozenset[Cell]] = {
    ComponentType.AGE_MIN: frozenset({Cell.MIN_AGE}),
    ComponentType.SCHOOL_GRADE_MIN: frozenset({Cell.ACADEMIC}),
    ComponentType.NAMED_CREDENTIAL: frozenset({Cell.ACADEMIC}),
    ComponentType.PRIOR_NSQF_LEVEL: frozenset({Cell.ACADEMIC}),
    ComponentType.EXPERIENCE_MIN_YEARS: frozenset({Cell.EXPERIENCE}),
    ComponentType.UNMODELLED: frozenset({Cell.ACADEMIC, Cell.EXPERIENCE}),
}
_CREDENTIAL_WORDING = {"UG_DIPLOMA": "UG Diploma", "UG_CERTIFICATE": "UG Certificate"}
_YEARS_PATTERNS = (  # (regex on the experience cell, years from the match); any other wording cannot be verified
    (re.compile(r"^No Experience required$"), lambda m: 0.0),
    (re.compile(r"^(\d+(?:\.\d+)?)[- ]years?\b"), lambda m: float(m.group(1))),
    (re.compile(r"^(\d+(?:\.\d+)?) months?\b"), lambda m: float(m.group(1)) / 12),
    (re.compile(r"^One year\b"), lambda m: 1.0),
)
_OR_EQUIVALENT_TYPES = frozenset({ComponentType.NAMED_CREDENTIAL, ComponentType.SCHOOL_GRADE_MIN})
_RELEVANCE_TYPES = frozenset({ComponentType.PRIOR_NSQF_LEVEL, ComponentType.EXPERIENCE_MIN_YEARS})


class ComponentCfg(_Strict):
    cell: Cell
    text: StrictStr  # a guard: it must equal the source cell ("" for an empty cell)
    type: ComponentType
    params: dict[str, ParamValue] = {}
    requires_relevance: StrictBool = False
    or_equivalent: StrictBool = False
    safe_from: SafeFrom
    unknown_reason: UnknownReasonCode | None = None

    @model_validator(mode="after")
    def _check(self) -> ComponentCfg:
        required = _REQUIRED_PARAMS[self.type]
        allowed = {**required, **_OPTIONAL_PARAMS.get(self.type, {})}
        unknown = set(self.params) - set(allowed)
        if unknown:
            raise ValueError(f"{self.type.value} does not take params {sorted(unknown)} (allowed: {sorted(allowed)})")
        missing = set(required) - set(self.params)
        if missing:
            raise ValueError(f"{self.type.value} requires params {sorted(missing)}")
        for key, value in self.params.items():
            if type(value) is not allowed[key]:  # exact: a bool is not an int and 3 is not 3.0
                raise ValueError(f"params[{key!r}] must be {allowed[key].__name__}, not {type(value).__name__}")
        p = self.params
        if any(isinstance(v, float) and not math.isfinite(v) for v in p.values()):
            raise ValueError("numeric parameters must be finite")
        if "grade" in p and not 0 <= p["grade"] <= 12:
            raise ValueError("grade must be 0-12")
        if "min_age" in p and p["min_age"] < 0:
            raise ValueError("min_age must be >= 0")
        if "years" in p and p["years"] < 0:
            raise ValueError("years must be >= 0")
        if "level" in p and not (1 <= p["level"] <= 10 and p["level"] * 2 == int(p["level"] * 2)):
            raise ValueError("level must be 1-10 in steps of 0.5")
        if "credential" in p and p["credential"] not in _CREDENTIALS:
            raise ValueError(f"credential must be one of {sorted(_CREDENTIALS)}")
        if "below_required_verdict" in p and p["below_required_verdict"] != "UNKNOWN":
            raise ValueError("below_required_verdict is only 'UNKNOWN'")
        if self.requires_relevance and self.type not in _RELEVANCE_TYPES:
            raise ValueError("requires_relevance applies only to PRIOR_NSQF_LEVEL and EXPERIENCE_MIN_YEARS")
        if self.or_equivalent and self.type not in _OR_EQUIVALENT_TYPES:
            raise ValueError("or_equivalent applies only to NAMED_CREDENTIAL and SCHOOL_GRADE_MIN (not UNMODELLED)")
        if self.type is ComponentType.UNMODELLED and (self.safe_from is not SafeFrom.NONE or self.unknown_reason is None):
            raise ValueError("an UNMODELLED component needs safe_from 'none' and an unknown_reason")
        if self.cell not in _TYPE_CELLS[self.type]:
            raise ValueError(f"{self.type.value} cannot be read from the {self.cell.value} cell")
        problem = self._disagreement()
        if problem:
            raise ValueError(f"the parameters disagree with the quoted text {self.text!r}: {problem}")
        return self

    def _disagreement(self) -> str | None:
        """The table is human-written, so check what it claims against the very text it quotes (verification only:
        nothing is derived from the text). Wording the verifier does not recognise is refused, never waved through."""
        p, text = self.params, self.text
        if self.type is ComponentType.AGE_MIN:
            return None if text == str(p["min_age"]) else "min_age differs from the printed age"
        if self.type is ComponentType.SCHOOL_GRADE_MIN:
            if not re.search(rf"(?<!\d){p['grade']}(?!\d)", text):
                return f"grade {p['grade']} is not in the text"
            if "below_required_verdict" in p and ("pass" in text.lower() or self.or_equivalent):
                return "below_required_verdict is only for a grade printed without 'pass' and without 'equivalent' (D5)"
        elif self.type is ComponentType.NAMED_CREDENTIAL:
            if not text.startswith(_CREDENTIAL_WORDING[p["credential"]]):
                return f"credential {p['credential']} is not what the text names"
        elif self.type is ComponentType.PRIOR_NSQF_LEVEL:
            if not text.endswith(f"NSQF Level {p['level']:g}"):
                return f"level {p['level']:g} is not the level the text ends with"
        elif self.type is ComponentType.EXPERIENCE_MIN_YEARS:
            for pattern, years in _YEARS_PATTERNS:
                if match := pattern.search(text):
                    if abs(years(match) - p["years"]) > 1e-9:
                        return f"years {p['years']} differs from the {years(match)} the text states"
                    break
            else:
                return "the experience wording is not one the verifier recognises"
        if self.type in _RELEVANCE_TYPES and self.requires_relevance != ("relevant" in text.lower()):
            return "requires_relevance must hold exactly when the text says 'relevant'"
        if self.type in _OR_EQUIVALENT_TYPES and self.or_equivalent != ("equivalent" in text.lower()):
            return "or_equivalent must hold exactly when the text says 'equivalent'"
        return None


class ExpectCfg(_Strict):
    """Guards against a stale table: the source row must still say what the table was written against."""

    row_engine_use: EngineUse
    row_text: StrictStr | None = None
    min_age: StrictStr | None = None


class RuleCfg(_Strict):
    id: RuleId
    review: Review
    decision: StrictStr | None = None
    review_note: StrictStr | None = None
    expect: ExpectCfg
    components: list[ComponentCfg]

    @model_validator(mode="after")
    def _check(self) -> RuleCfg:
        if not self.components:
            raise ValueError("a rule needs at least one component")
        return self


class AuditRequestCfg(_Strict):
    """A request to the audit, nothing more: it can never be recorded as a decision (P1.5-R1)."""

    id: StrictStr
    status: Literal["OPEN_REQUEST_ONLY"]
    text: StrictStr
    cells: list[Annotated[StrictStr, Field(pattern=r"^rule:[A-Z]{2,6}/Q\d{4}/E\d{1,3}#c[1-9]$")]]


class RulesConfig(_Strict):
    conventions: dict[str, Any] = {}
    audit_review_requests: list[AuditRequestCfg] = []
    rules: list[RuleCfg]

    @model_validator(mode="after")
    def _unique(self) -> RulesConfig:
        ids = [r.id for r in self.rules]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate rule mappings: {dupes}")
        return self

    def get(self, rule_id: str) -> RuleCfg | None:
        return next((r for r in self.rules if r.id == rule_id), None)


def parse_rules_config(raw: object) -> RulesConfig:
    try:
        return RulesConfig.model_validate(raw)
    except ValidationError as exc:
        lines = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise EligibilityRulesError(f"eligibility rules configuration is invalid: {lines}") from exc


class _UniqueKeyLoader(yaml.SafeLoader):
    """PyYAML keeps the last of two equal keys silently; in a safety table that would hide an edit."""

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(k, deep=deep) for k, _ in node.value]
        duplicates = sorted({str(k) for k in keys if keys.count(k) > 1})
        if duplicates:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key(s) {duplicates}", node.start_mark)
        return super().construct_mapping(node, deep=deep)


def load_rules_config(path: Path = RULES_PATH) -> RulesConfig:
    try:
        raw = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506 (a safe subclass)
    except (OSError, yaml.YAMLError) as exc:
        raise EligibilityRulesError(f"cannot read {path}: {exc}") from exc
    return parse_rules_config(raw)


def load_source_rows(path: Path) -> list[EligibilitySourceRow]:
    """Read ``eligibility_source_rows.json`` (read-only); every row is re-validated by the P1.2 model."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [EligibilitySourceRow.model_validate(item) for item in data]
    except (OSError, ValueError) as exc:  # json errors and pydantic ValidationError are ValueErrors
        raise EligibilityRulesError(f"cannot load source rows from {path}: {exc}") from exc


# ------------------------------------------------------------------------------------------- pure derivations
def component_id(rule_id: str, ordinal: int) -> str:
    """``<rule id>#c<n>``, n counting from 1 in printed cell order (API_SPEC §2.4). Derived, never stored."""
    if ordinal < 1:
        raise ValueError("component ordinals start at 1")
    return f"{rule_id}#c{ordinal}"


def split_cells(raw_text: str) -> tuple[str, str]:
    """Split a row's ``raw_text`` once on the first delimiter; the exact inverse of the join. Never trims."""
    head, sep, tail = raw_text.partition(DELIMITER)
    if not sep:
        raise EligibilityRulesError(f"raw_text has no {DELIMITER!r} delimiter: {raw_text!r}")
    return head, tail


def response_params(component: Component) -> dict[str, ParamValue]:
    """The API projection (API_SPEC §2.4): stored params plus ``requires_relevance: true`` only when it is true."""
    if "requires_relevance" in component.params:
        raise EligibilityRulesError("a stored component must not carry requires_relevance inside params")
    out = dict(component.params)
    if component.requires_relevance:
        out["requires_relevance"] = True
    return out


def check_component_invariant(component: Component, where: str = "component") -> None:
    """Curated-data invariant (ARCHITECTURE §9.2): ``safe = false`` <=> a static reason; UNMODELLED is never safe."""
    if "requires_relevance" in component.params:
        raise EligibilityRulesError(f"{where}: requires_relevance is a component field, never a stored param")
    if component.safe and component.unknown_reason is not None:
        raise EligibilityRulesError(f"{where}: a safe component cannot carry unknown_reason {component.unknown_reason.value}")
    if not component.safe and component.unknown_reason is None:
        raise EligibilityRulesError(f"{where}: a component that is not safe needs a static unknown_reason")
    if component.type is ComponentType.UNMODELLED and component.safe:
        raise EligibilityRulesError(f"{where}: an UNMODELLED component is never safe")


# ------------------------------------------------------------------------------------------------- structuring
_CELL_FIELD = {Cell.ACADEMIC: "raw_academic_or_skill", Cell.EXPERIENCE: "raw_required_experience", Cell.MIN_AGE: "min_age"}


def _computing(use: EngineUse | None) -> bool:
    return use in _ELIGIBILITY_USES


def _cell(row: EligibilitySourceRow, cell: Cell, where: str):
    valued = getattr(row, _CELL_FIELD[cell])
    if valued is None:
        raise EligibilityRulesError(f"{where}: the source row has no {cell.value} cell")
    if valued.value is None:
        raise EligibilityRulesError(f"{where}: the {cell.value} cell has no value (null is not an empty cell)")
    if valued.evidence_id is None:
        raise EligibilityRulesError(f"{where}: the {cell.value} cell has no evidence record")
    if valued.value_status is ValueStatus.CORRECTION_APPLIED or valued.source_value is not None:
        raise CorrectionNotSupported(
            f"{where}: the {cell.value} cell carries an applied correction; its mapping to a component is not "
            "defined yet (P1.5-A2)")
    return valued


def _text(row: EligibilitySourceRow, cell: Cell, where: str) -> str:
    value = _cell(row, cell, where).value
    return str(value) if cell is Cell.MIN_AGE else value


def _check_source_row_text(row: EligibilitySourceRow, where: str) -> None:
    if row.kind is not SourceRowKind.ELIGIBILITY_ROW:
        return
    academic, experience = _text(row, Cell.ACADEMIC, where), _text(row, Cell.EXPERIENCE, where)
    full = row.raw_row_text  # required for an eligibility row by the P1.2 model
    if full.value is None:
        raise EligibilityRulesError(f"{where}: the row text has no value")
    if full.value_status is ValueStatus.CORRECTION_APPLIED or full.source_value is not None:
        raise CorrectionNotSupported(f"{where}: the row text carries an applied correction (P1.5-A2)")
    raw = full.value
    if DELIMITER in academic or DELIMITER in experience:
        raise EligibilityRulesError(
            f"{where}: a cell contains the delimiter {DELIMITER!r}, so the printed cells cannot be told apart")
    if raw.count(DELIMITER) != 1 or academic + DELIMITER + experience != raw:
        raise EligibilityRulesError(
            f"{where}: the printed cells {academic!r} + {DELIMITER!r} + {experience!r} do not reproduce raw_text {raw!r}")


def _safe_and_reason(
    row: EligibilitySourceRow, cell: Cell, cfg: ComponentCfg, where: str
) -> tuple[bool, UnknownReasonCode | None]:
    """Compute ``safe`` from the source (never from the configuration) and apply the configured reason iff unsafe."""
    valued = _cell(row, cell, where)
    status = valued.value_status
    if cfg.safe_from is SafeFrom.ROW:
        use = row.engine_use
    elif cfg.safe_from is SafeFrom.CELL:
        use = valued.engine_use
    else:
        use = None
    substantiated = status not in _UNCERTAIN  # geometry/corroboration/correction already changed the status itself
    if cfg.safe_from is SafeFrom.ROW:  # a row-level use also needs its own row-level component to be certain
        row_component = row.min_age if row.kind is SourceRowKind.AGE_9C else row.raw_row_text
        substantiated = substantiated and row_component.value_status not in _UNCERTAIN
    if valued.conflict_id is not None and _computing(use):
        raise EligibilityRulesError(f"{where}: the {cell.value} cell has an open conflict ({valued.conflict_id})")
    safe = cfg.type is not ComponentType.UNMODELLED and _computing(use) and substantiated
    if safe:
        return True, None  # a computed-safe component keeps no static reason
    reason = cfg.unknown_reason
    if reason is None:
        raise EligibilityRulesError(
            f"{where}: the {cell.value} cell is not evaluable (safe_from '{cfg.safe_from.value}': engine_use "
            f"{use.value if use else 'none'}, status {status.value if status else 'none'}) and the table gives no "
            "unknown_reason; the table is stale or incomplete")
    if reason is UnknownReasonCode.UNCERTAIN_EXTRACTION and status not in _UNCERTAIN:
        raise EligibilityRulesError(f"{where}: UNCERTAIN_EXTRACTION is only for an uncertain cell, not {status}")
    if reason is UnknownReasonCode.ENGINE_USE_UNDECIDED and (status in _UNCERTAIN or _computing(use)):
        raise EligibilityRulesError(
            f"{where}: ENGINE_USE_UNDECIDED is only for a parsed (not uncertain) cell whose engine use is undecided")
    if reason is UnknownReasonCode.OVERLAY_NOT_APPROVED and not (row.pending_overlay_ids and valued.value == ""):
        raise EligibilityRulesError(
            f"{where}: OVERLAY_NOT_APPROVED is only for an empty cell of a row with a pending overlay proposal")
    return False, reason


def _check_expect(row: EligibilitySourceRow, rule: RuleCfg, where: str) -> None:
    exp = rule.expect
    if exp.row_engine_use is not row.engine_use:
        raise EligibilityRulesError(
            f"{where}: the table was written for row engine_use {exp.row_engine_use.value} but the source row is "
            f"{row.engine_use.value}")
    if row.kind is SourceRowKind.ELIGIBILITY_ROW:
        if exp.row_text is None or exp.min_age is not None:
            raise EligibilityRulesError(f"{where}: an eligibility row's table entry needs expect.row_text only")
        if exp.row_text != row.raw_row_text.value:
            raise EligibilityRulesError(f"{where}: the row text changed: table {exp.row_text!r}, source {row.raw_row_text.value!r}")
    else:
        if exp.min_age is None or exp.row_text is not None:
            raise EligibilityRulesError(f"{where}: an age row's table entry needs expect.min_age only")
        if exp.min_age != _text(row, Cell.MIN_AGE, where):
            raise EligibilityRulesError(f"{where}: the minimum age changed: table {exp.min_age!r}, source {row.min_age.value!r}")


def _prepare(row: EligibilitySourceRow, rule: RuleCfg) -> tuple[EligibilitySourceRow, RuleCfg]:
    """Re-validate both inputs. A model built with ``model_construct`` or changed with ``model_copy(update=...)`` skips
    its validators; this layer must never rely on the caller having kept them, so every public function starts here."""
    try:
        return (EligibilitySourceRow.model_validate(row.model_dump()), RuleCfg.model_validate(rule.model_dump()))
    except ValidationError as exc:
        lines = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise EligibilityRulesError(f"{row.id}: the source row or the table entry is not valid: {lines}") from exc


def structure_components(row: EligibilitySourceRow, rule: RuleCfg) -> list[Component]:
    """The components of one source row, in printed cell order. Raises on any inconsistency; guesses nothing."""
    row, rule = _prepare(row, rule)
    return _components(row, rule)


def _components(row: EligibilitySourceRow, rule: RuleCfg) -> list[Component]:
    where = row.id
    if rule.id != row.id:
        raise EligibilityRulesError(f"{where}: mapped by the entry for {rule.id}")
    if rule.review is not Review.SUPPORTED:
        raise EligibilityRulesError(f"{where}: the table entry is {rule.review.value}, not SUPPORTED; refusing to use it")
    _check_expect(row, rule, where)
    _check_source_row_text(row, where)
    expected = [Cell.MIN_AGE] if row.kind is SourceRowKind.AGE_9C else [Cell.ACADEMIC, Cell.EXPERIENCE]
    mapped = [c.cell for c in rule.components]
    if mapped != expected:
        raise EligibilityRulesError(
            f"{where}: the source has the printed cells {[c.value for c in expected]} but the table maps "
            f"{[c.value for c in mapped]} (one component per printed cell, in printed order)")
    out: list[Component] = []
    for n, cfg in enumerate(rule.components, start=1):
        at = component_id(where, n)
        source_text = _text(row, cfg.cell, at)
        if cfg.text != source_text:
            raise EligibilityRulesError(f"{at}: the table quotes {cfg.text!r} but the source cell is {source_text!r}")
        safe, reason = _safe_and_reason(row, cfg.cell, cfg, at)
        try:
            component = Component(
                type=cfg.type, params=dict(cfg.params), requires_relevance=cfg.requires_relevance,
                or_equivalent=cfg.or_equivalent, evidence_id=_cell(row, cfg.cell, at).evidence_id, safe=safe,
                unknown_reason=reason)
        except ValidationError as exc:
            raise EligibilityRulesError(f"{at}: {exc}") from exc
        check_component_invariant(component, at)
        out.append(component)
    return out


def _carry(row: EligibilitySourceRow) -> tuple[list[str], list]:
    """Decided overlay ids and flags, carried verbatim. A pending proposal is never an overlay id; it must already
    be named in an OVERLAY_PENDING_APPROVAL flag, otherwise it would be silently dropped."""
    refs = {r for f in row.flags if f.code is QualityFlagCode.OVERLAY_PENDING_APPROVAL for r in f.refs}
    missing = sorted(set(row.pending_overlay_ids) - refs)
    if missing:
        raise EligibilityRulesError(f"{row.id}: pending overlay(s) {missing} are not named in an OVERLAY_PENDING_APPROVAL flag")
    overlap = sorted(set(row.pending_overlay_ids) & set(row.overlay_ids))
    if overlap:
        raise EligibilityRulesError(f"{row.id}: {overlap} are both decided and pending")
    return list(row.overlay_ids), [flag.model_copy(deep=True) for flag in row.flags]  # no aliasing of the source


def structure_row(row: EligibilitySourceRow, rule: RuleCfg) -> EligibilityRow:
    if row.kind is not SourceRowKind.ELIGIBILITY_ROW:
        raise EligibilityRulesError(f"{row.id}: not an eligibility row; use structure_age_rule")
    row, rule = _prepare(row, rule)
    components = _components(row, rule)
    overlay_ids, flags = _carry(row)
    full = row.raw_row_text
    if full.evidence_id is None:
        raise EligibilityRulesError(f"{row.id}: the row text has no evidence record")
    try:
        return EligibilityRow(
            id=row.id, s_no=row.s_no, raw_text=full.value, evidence_id=full.evidence_id, components=components,
            engine_use=row.engine_use, overlay_ids=overlay_ids, flags=flags)
    except ValidationError as exc:
        raise EligibilityRulesError(f"{row.id}: {exc}") from exc


def structure_age_rule(row: EligibilitySourceRow, rule: RuleCfg) -> AgeRule:
    """Build an age rule only if the source row carries the verbatim item 9c text with its own evidence (P1.5-A1)."""
    if row.kind is not SourceRowKind.AGE_9C:
        raise EligibilityRulesError(f"{row.id}: not an age row")
    row, rule = _prepare(row, rule)
    components = _components(row, rule)  # validated first, so a stale table is reported before the block
    text = row.raw_row_text
    if text is None or not text.value or text.evidence_id is None:
        raise AgeRuleBlocked(
            f"{row.id}: the source row carries no verbatim item 9c text with an evidence record, so AgeRule.raw_text "
            "cannot be filled without reconstructing it from min_age (open decision P1.5-A1)")
    if text.value_status is ValueStatus.CORRECTION_APPLIED or text.source_value is not None:
        raise CorrectionNotSupported(f"{row.id}: the age text carries an applied correction (P1.5-A2)")
    overlay_ids, flags = _carry(row)
    try:
        return AgeRule(id=row.id, raw_text=text.value, evidence_id=text.evidence_id, components=components,
                       engine_use=row.engine_use, overlay_ids=overlay_ids, flags=flags)
    except ValidationError as exc:
        raise EligibilityRulesError(f"{row.id}: {exc}") from exc


@dataclass(frozen=True)
class StructuredRules:
    """Result of ``structure_all``. ``blocked`` maps each age row that could not be built to the reason."""

    rows: tuple[EligibilityRow, ...]
    age_rules: tuple[AgeRule, ...]
    age_components: dict[str, tuple[Component, ...]] = field(default_factory=dict)
    blocked: dict[str, str] = field(default_factory=dict)


def _order(row: EligibilitySourceRow) -> tuple[str, int, int]:
    code = row.id.rsplit("/", 1)[0]
    return code, 0 if row.kind is SourceRowKind.AGE_9C else 1, row.s_no or 0


def structure_all(
    source_rows: list[EligibilitySourceRow], config: RulesConfig, *, allow_blocked: bool = False
) -> StructuredRules:
    """Structure every source row. The table and the source must cover exactly the same rows.

    ``allow_blocked=False`` (the default) raises ``AgeRuleBlocked`` for the first age rule that cannot be built;
    ``True`` records it in ``blocked`` (the age components are still returned) so that the rest can be inspected.
    """
    ids = [r.id for r in source_rows]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise EligibilityRulesError(f"duplicate source rows: {duplicates}")
    unmapped = sorted(set(ids) - {r.id for r in config.rules})
    unknown = sorted({r.id for r in config.rules} - set(ids))
    if unmapped or unknown:
        raise EligibilityRulesError(
            f"the table and the source rows differ: no mapping for {unmapped}; mapping without a source row {unknown}")
    rows: list[EligibilityRow] = []
    ages: list[AgeRule] = []
    age_components: dict[str, tuple[Component, ...]] = {}
    blocked: dict[str, str] = {}
    for src in sorted(source_rows, key=_order):
        rule = config.get(src.id)
        if src.kind is SourceRowKind.ELIGIBILITY_ROW:
            rows.append(structure_row(src, rule))
            continue
        age_components[src.id] = tuple(structure_components(src, rule))
        try:
            ages.append(structure_age_rule(src, rule))
        except AgeRuleBlocked as exc:
            if not allow_blocked:
                raise
            blocked[src.id] = str(exc)
    return StructuredRules(rows=tuple(rows), age_rules=tuple(ages), age_components=age_components, blocked=blocked)


def rules_digest(config: RulesConfig) -> str:
    """SHA-256 of the validated table's canonical JSON: part of the build identity, independent of file location,
    comments and key order (a change of any rule, parameter or reason changes the data_build_id)."""
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def project_rule(rule: EligibilityRow | AgeRule) -> dict[str, Any]:
    """The static response view of one stored rule (API_SPEC §2.4): what a client may see before any evaluation.

    Derived, never stored: ``component_id`` (``<rule id>#c<n>``) and ``requirement_text`` (the verbatim text of the
    component's own cell). ``params`` gets ``requires_relevance: true`` only when true. Not exposed: ``safe`` (an
    engine-internal gate), ``or_equivalent``, the stored ``unknown_reason`` (the response one is per evaluation)
    and ``engine_use`` of a component. Verdicts, inputs and conditions belong to the evaluation (P3), not here.

    ``flags`` are the stored rule's quality flags (``RowResult.flags``), copied so that a caller cannot change the
    stored rule; they include ``OVERLAY_PENDING_APPROVAL`` (whose ``refs`` name the pending proposals) and
    ``UNCERTAIN_EXTRACTION``.
    """
    if isinstance(rule, AgeRule):
        texts: list[str] = [rule.raw_text]
    else:
        texts = list(split_cells(rule.raw_text))
    if len(texts) != len(rule.components):
        raise EligibilityRulesError(f"{rule.id}: {len(rule.components)} components for {len(texts)} printed cells")
    components = []
    for ordinal, (component, text) in enumerate(zip(rule.components, texts, strict=True), start=1):
        check_component_invariant(component, component_id(rule.id, ordinal))
        components.append({
            "component_id": component_id(rule.id, ordinal), "type": component.type.value,
            "requirement_text": text, "params": response_params(component), "evidence_ids": [component.evidence_id],
        })
    out: dict[str, Any] = {"rule_id": rule.id, "raw_text": rule.raw_text, "engine_use": rule.engine_use.value,
                           "overlay_ids": list(rule.overlay_ids), "flags": [f.model_dump(mode="json") for f in rule.flags],
                           "components": components}
    if isinstance(rule, EligibilityRow):
        out["s_no"] = rule.s_no
    return out


def project_spec(spec: EligibilitySpec) -> dict[str, Any]:
    """AND(age, OR(rows)) in the response order: the age rule, then the rows by ascending s_no."""
    return {"age": project_rule(spec.age_rule), "rows": [project_rule(r) for r in spec.rows]}


def assemble_specs(structured: StructuredRules) -> dict[str, EligibilitySpec]:
    """Group rules into one ``EligibilitySpec`` per qualification code. Refused while any age rule is blocked."""
    if structured.blocked:
        raise AgeRuleBlocked("; ".join(f"{k}: {v}" for k, v in sorted(structured.blocked.items())))
    specs: dict[str, EligibilitySpec] = {}
    for age in structured.age_rules:
        code = age.qualification_code
        specs[code] = EligibilitySpec(age_rule=age, rows=[r for r in structured.rows if r.qualification_code == code])
    orphans = sorted({r.qualification_code for r in structured.rows} - set(specs))
    if orphans:
        raise EligibilityRulesError(f"eligibility rows without an age rule: {orphans}")
    return specs
