"""Deterministic input preparation for the judge: engine result + evidence metadata + candidate text -> a frozen packet.

The packet is the ONLY thing a judge sees. It is built by an allowlist: rule and component results, the verdict, conditions,
unknown reasons, flags, the evidence metadata the result cites, and the candidate text. It carries no raw PDF text, no
profile field beyond the ``inputs_used`` entries the engine itself echoed into its result, no contact detail and no secret.
Building a packet reads the engine result and the registry and changes neither.

A packet that matches a privacy pattern (email, phone number) in any free-text field is refused (``PacketError``), and the
same check runs on every packet that is constructed from data.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from typing import Annotated

from pydantic import StrictBool, StrictFloat, StrictInt, StrictStr, StringConstraints, ValidationError, model_validator

from skillgraph.eligibility.evaluate import ComponentResult, EligibilityResult
from skillgraph.model.base import SchemaModel
from skillgraph.registry import Registry, RegistryError

PACKET_SCHEMA_VERSION = "1"
MAX_CANDIDATE_CHARS = 4000

CaseId = Annotated[StrictStr, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None

# Same families as the legacy reconciliation test (data_extraction/test_reconcile_2026-10-30.py): an email, a phone-like
# number. They are applied to free text only, never to ids (a hex evidence id can contain ten digits in a row).
_PII = (
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"(?<![\w.])\+?\d{1,3}[\s-]?\(?\d{2,5}\)?[\s-]?\d{3,5}[\s-]?\d{3,5}(?![\w.])"),
    re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),
)


class PacketError(ValueError):
    """The packet cannot be built or is refused. Never a verdict; the engine result is untouched."""


class PacketInput(SchemaModel):
    field: StrictStr
    value: JsonScalar | tuple[StrictStr, ...]
    evidence_class: StrictStr


class PacketComponent(SchemaModel):
    component_id: StrictStr
    type: StrictStr
    requirement_text: StrictStr
    verdict: StrictStr
    inputs_used: tuple[PacketInput, ...] = ()
    evidence_ids: tuple[StrictStr, ...] = ()
    condition_text: StrictStr | None = None
    unknown_reason_code: StrictStr | None = None
    unknown_reason_text: StrictStr | None = None


class PacketRule(SchemaModel):
    rule_id: StrictStr
    raw_text: StrictStr
    verdict: StrictStr
    components: tuple[PacketComponent, ...]


class PacketCondition(SchemaModel):
    kind: StrictStr
    key: StrictStr
    text: StrictStr
    evidence_class: StrictStr


class PacketUnknown(SchemaModel):
    code: StrictStr
    ref: StrictStr
    text: StrictStr
    resolvable_by: StrictStr


class PacketFlag(SchemaModel):
    code: StrictStr
    severity: StrictStr
    message: StrictStr


class PacketSupport(SchemaModel):
    kind: StrictStr
    text: StrictStr
    evidence_class: StrictStr
    evidence_ids: tuple[StrictStr, ...] = ()


class PacketEvidence(SchemaModel):
    evidence_class: StrictStr
    source_title: StrictStr | None = None
    source_org: StrictStr | None = None
    page: StrictStr | None = None
    location: StrictStr | None = None
    value_status: StrictStr | None = None
    note: StrictStr | None = None


class JudgePacket(SchemaModel):
    schema_version: StrictStr = PACKET_SCHEMA_VERSION
    case_id: CaseId
    target_code: StrictStr
    target_title: StrictStr
    verdict: StrictStr
    age: PacketComponent
    rows: tuple[PacketRule, ...]
    decisive_rule_ids: tuple[StrictStr, ...]
    conditions: tuple[PacketCondition, ...] = ()
    unknown_reasons: tuple[PacketUnknown, ...] = ()
    quality_flags: tuple[PacketFlag, ...] = ()
    supporting_statements: tuple[PacketSupport, ...] = ()
    evidence: dict[StrictStr, PacketEvidence]
    candidate_text: Annotated[StrictStr, StringConstraints(min_length=1, max_length=MAX_CANDIDATE_CHARS)]

    @model_validator(mode="after")
    def _checked(self) -> JudgePacket:
        if self.schema_version != PACKET_SCHEMA_VERSION:
            raise ValueError(f"unsupported packet schema_version {self.schema_version!r}")
        cited = {e for c in self._components() for e in c.evidence_ids} | {e for s in self.supporting_statements for e in s.evidence_ids}
        missing = sorted(cited - set(self.evidence))
        if missing:
            raise ValueError(f"evidence cited but not supplied (never inferred): {missing}")
        for text in self.free_text():
            for rx in _PII:
                for m in rx.finditer(text):
                    if "@" in m.group() or sum(ch.isdigit() for ch in m.group()) >= 10:
                        raise ValueError("a free-text field matches a contact-detail pattern; the packet is refused")
        return self

    def _components(self) -> Iterator[PacketComponent]:
        yield self.age
        for r in self.rows:
            yield from r.components

    def free_text(self) -> Iterator[str]:
        """Every field that holds prose; ids and codes are deliberately not scanned."""
        yield self.candidate_text
        yield self.target_title
        for c in self._components():
            yield c.requirement_text
            for t in (c.condition_text, c.unknown_reason_text):
                if t:
                    yield t
            for i in c.inputs_used:
                if isinstance(i.value, str):
                    yield i.value
        for r in self.rows:
            yield r.raw_text
        yield from (c.text for c in self.conditions)
        yield from (u.text for u in self.unknown_reasons)
        yield from (f.message for f in self.quality_flags)
        yield from (s.text for s in self.supporting_statements)
        for e in self.evidence.values():
            yield from (v for v in (e.source_title, e.source_org, e.location, e.note) if v)

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _component(c: ComponentResult) -> PacketComponent:
    return PacketComponent(
        component_id=c.component_id, type=c.type.value, requirement_text=c.requirement_text, verdict=c.verdict.value,
        inputs_used=tuple(PacketInput(field=i.field, value=(tuple(i.value) if isinstance(i.value, tuple) else i.value),
                                      evidence_class=i.evidence_class.value) for i in c.inputs_used),
        evidence_ids=tuple(c.evidence_ids),
        condition_text=c.condition.text if c.condition else None,
        unknown_reason_code=c.unknown_reason.code.value if c.unknown_reason else None,
        unknown_reason_text=c.unknown_reason.text if c.unknown_reason else None)


def build_packet(case_id: str, result: EligibilityResult, registry: Registry, candidate_text: str) -> JudgePacket:
    """Allowlisted packet for one engine result and one candidate explanation. Raises ``PacketError``; changes nothing."""
    try:
        age = _component(result.age)
        rows = tuple(PacketRule(rule_id=r.rule_id, raw_text=r.raw_text, verdict=r.verdict.value,
                                components=tuple(_component(c) for c in r.components)) for r in result.rows)
        ids = sorted({e for c in [age, *(c for r in rows for c in r.components)] for e in c.evidence_ids}
                     | {e for s in result.supporting_evidence for e in s.evidence_ids})
        evidence: dict[str, PacketEvidence] = {}
        for eid in ids:
            ev = registry.evidence_by_id(eid)  # an unknown id raises: evidence is never invented
            src = registry.source_by_id(ev.source_id) if ev.source_id else None
            evidence[eid] = PacketEvidence(
                evidence_class=ev.evidence_class.value, source_title=src.title if src else None,
                source_org=src.org if src else None, page=ev.page, location=ev.location,
                value_status=ev.value_status.value if ev.value_status else None, note=ev.note)
        return JudgePacket(
            case_id=case_id, target_code=result.target.code, target_title=result.target.title,
            verdict=result.verdict.value, age=age, rows=rows, decisive_rule_ids=tuple(result.decisive_rule_ids),
            conditions=tuple(PacketCondition(kind=c.kind.value, key=c.key, text=c.text, evidence_class=c.evidence_class.value)
                             for c in result.conditions),
            unknown_reasons=tuple(PacketUnknown(code=u.code.value, ref=u.ref, text=u.text, resolvable_by=u.resolvable_by)
                                  for u in result.unknown_reasons),
            quality_flags=tuple(PacketFlag(code=f.code.value, severity=f.severity.value, message=f.message)
                                for f in result.quality_flags),
            supporting_statements=tuple(PacketSupport(kind=s.kind, text=s.text, evidence_class=s.evidence_class.value,
                                                      evidence_ids=tuple(s.evidence_ids)) for s in result.supporting_evidence),
            evidence=evidence, candidate_text=candidate_text)
    except (ValidationError, RegistryError, KeyError) as exc:
        raise PacketError(f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}") from exc


def packet_from_mapping(data: Mapping[str, object]) -> JudgePacket:
    """Validate a packet given as plain data (a case file). Raises ``PacketError``."""
    try:
        return JudgePacket.model_validate(dict(data))
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise PacketError(f"packet invalid{' at ' + where if where else ''}: {first['msg'][:160]}") from exc
