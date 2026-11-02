"""Static graph edges (ARCHITECTURE §10.3; API_SPEC E08, §4; TASKS P3.4).

``build_static_edges(registry)`` turns the relationships that a curated build *documents* into a deterministic list of
``GraphEdge`` records. Four edge types are stored; each has one authoritative source and nothing else creates them:

=================== ====================== ============== ===================================================================
edge                direction              class          source in the registry
=================== ====================== ============== ===================================================================
``INCLUDES_NOS``    qual -> nos / mod      OFFICIAL       one per ``Qualification.nos_memberships`` row (the QF NOS table)
``SHARES_NOS``      qual <-> qual          RULE_DERIVED   exact NOS-code match on two such OFFICIAL memberships
``PROGRESSION_CLAIM`` qual -> claim        OFFICIAL       one per ``Qualification.progression_claims`` (QF item 15)
``ALIGNED_TO_NCO``  qual -> nco            OFFICIAL       one per ``Qualification.nco_codes`` (the stated NCO-2015 code)
=================== ====================== ============== ===================================================================

An edge records that a relationship is *documented*. It is never a claim that a person is eligible, that a move is
possible or that skills transfer: no edge is read by the eligibility evaluator, and none is used for feasibility
(ARCHITECTURE §10.3; the only feasibility edge is the per-request ``ELIGIBILITY_ROUTE``, which is not built here). Edges
are derived from codes, ids and stated lists only: no title, level, hours, credit, age, eligibility rule, occupation
similarity, labour-market figure, probability or LLM is consulted, and Q-B (use of a qualification-level NSQF value) is not
touched. A ``PROGRESSION_CLAIM`` ends at a ``claim:`` node and never at a qualification; the name-based link
``ProgressionClaim.resolved_target`` is an INFERENCE for P3.5 and is deliberately not read here.

Decisions where the specification is silent (D-7 … D-14 continue the D-numbering of P3.3; recorded in ``TASKS.md``):

D-7   Only edges and the legend are built. Nodes (labels, attributes, flags) belong to the E08 view (P3.10 / P5.4); this
      module neither filters by ``coverage`` nor by ``focus``. ``include_inference=True`` (P3.5) adds the experimental edges
      of ``graph.inference`` to the result; the static edges are returned exactly as without it (same objects' values, same
      relative order), and the default is unchanged. (Until P3.5 this raised ``NotImplementedError``.)
D-8   Provenance. A membership is not itself a ``Valued``, so its ``evidence_ids`` are those of every printed cell of the
      NOS-table row it was read from (level, version when printed, the five hours values, credits) - sorted, de-duplicated.
      A ``SHARES_NOS`` edge carries the union over both qualifications and every shared code (it is RULE_DERIVED from
      exactly those OFFICIAL cells). A claim edge carries the claim's evidence id; an NCO edge the code's. Every id must
      resolve in the registry. Only ids are read: no value of a cell takes part in building an edge.
D-9   Invalid input is reported, never repaired. A dangling endpoint (unknown NOS unit, module or occupation, a module or
      membership belonging to another qualification), a null NCO code, an unresolved evidence or conflict id, or the same
      relationship stated twice (one qualification listing a NOS unit or NCO code twice) raises ``EdgeBuildError`` listing
      every problem found; no relationship is dropped, merged or picked.
D-10  ``version_agreement`` per shared code: ``SAME`` if both memberships print a version and the strings are equal,
      ``DIFFERENT`` if both print one and they differ, ``NOT_STATED`` if either prints none (null or empty/blank). Versions
      are DISPLAY_ONLY values; they are compared for this annotation only and never for a verdict.
D-11  ``core_shared_count`` / ``noncore_shared_count`` count codes that are Core / Non-Core in BOTH qualifications. A code
      classified differently by the two QFs is neither: it is listed in the extra attribute ``mixed_core_codes`` (always
      present, usually empty), so that ``core + noncore + len(mixed) == len(shared_codes)`` and no disagreement is hidden.
D-12  Conflicts. A membership value that carries a ``conflict_id`` puts one ``SOURCE_CONFLICT`` flag (severity ``INFO``, as
      in the E08 example, ``refs = [conflict id]``) on its ``INCLUDES_NOS`` edge and on every ``SHARES_NOS`` edge that
      uses that membership. Flags are de-duplicated and sorted by ref; no value is chosen between the sources.
D-13  Identity and order. Edge id = ``e:<TYPE>:<source key>:<target key>`` (the E08 example form; the key is the id without
      its kind prefix). ``SHARES_NOS`` is undirected and stored once with ``source < target``. The list is sorted by
      ``(type, source, target)`` (E08). Repeated calls on one registry, and calls on registries assembled from the same
      records in any order, give equal results.
D-14  Legend. The ``SHARES_NOS`` text is E08's verbatim. API_SPEC gives no text for the other three types, so their
      ``meaning`` / ``does_not_mean`` are drafted from ARCHITECTURE §10.2-§10.3 and are for review. Closeout review (run 8,
      ``docs/decisions/P3_4_CLOSEOUT.md``): the ``PROGRESSION_CLAIM`` ``does_not_mean`` was corrected, because a claim text can
      equal a catalogue title exactly (SMO's "Specialized Sewing Machine Operator"); the edge states no such link.
"""

from __future__ import annotations

import re
from collections import defaultdict
from enum import StrEnum
from itertools import combinations
from typing import Any

from pydantic import model_validator

from skillgraph.model.base import SchemaModel
from skillgraph.model.evidence import EvidenceClass, QualityFlag, QualityFlagCode, Severity, Valued
from skillgraph.model.ids import NCO_CODE, EvidenceId, IdKind, split_id
from skillgraph.model.qualification import CoreOrNonCore, NosMembership
from skillgraph.registry import Registry, UnknownEntityError

MAX_PROBLEMS_SHOWN = 8


# --------------------------------------------------------------------------------------------------------------------
# Types
# --------------------------------------------------------------------------------------------------------------------


class EdgeType(StrEnum):
    """API_SPEC §2.1. The two inference types are listed for completeness; ``NCO_GROUP_PROXIMITY`` is built by
    ``graph.inference`` (P3.5) and ``TITLE_SIMILARITY`` (COULD, not planned) by nothing."""

    INCLUDES_NOS = "INCLUDES_NOS"
    SHARES_NOS = "SHARES_NOS"
    PROGRESSION_CLAIM = "PROGRESSION_CLAIM"
    ALIGNED_TO_NCO = "ALIGNED_TO_NCO"
    NCO_GROUP_PROXIMITY = "NCO_GROUP_PROXIMITY"
    TITLE_SIMILARITY = "TITLE_SIMILARITY"


STATIC_EDGE_TYPES = (
    EdgeType.INCLUDES_NOS,
    EdgeType.SHARES_NOS,
    EdgeType.PROGRESSION_CLAIM,
    EdgeType.ALIGNED_TO_NCO,
)

# type -> (source kinds, target kinds, directed, evidence class)
_RULES: dict[EdgeType, tuple[tuple[IdKind, ...], tuple[IdKind, ...], bool, EvidenceClass]] = {
    EdgeType.INCLUDES_NOS: ((IdKind.QUAL,), (IdKind.NOS, IdKind.MOD), True, EvidenceClass.OFFICIAL),
    EdgeType.SHARES_NOS: ((IdKind.QUAL,), (IdKind.QUAL,), False, EvidenceClass.RULE_DERIVED),
    EdgeType.PROGRESSION_CLAIM: ((IdKind.QUAL,), (IdKind.CLAIM,), True, EvidenceClass.OFFICIAL),
    EdgeType.ALIGNED_TO_NCO: ((IdKind.QUAL,), (IdKind.NCO,), True, EvidenceClass.OFFICIAL),
}
_VERSION_AGREEMENT = frozenset({"SAME", "DIFFERENT", "NOT_STATED"})
_SHARES_KEYS = frozenset({"shared_codes", "core_shared_count", "noncore_shared_count", "mixed_core_codes",
                          "version_agreement"})
_NCO_PROXIMITY_KEYS = frozenset({"group_digits", "shared_groups", "codes_by_qualification"})
_NCO_CODE = re.compile(NCO_CODE)


class GraphEdge(SchemaModel):
    """API_SPEC E08 ``GraphEdge``. The model refuses an edge that breaks the contract of its type."""

    id: str
    type: EdgeType
    source: str
    target: str
    directed: bool
    evidence_class: EvidenceClass
    experimental: bool
    attributes: dict[str, Any]
    evidence_ids: list[EvidenceId]
    flags: list[QualityFlag] = []

    @model_validator(mode="after")
    def _check(self) -> GraphEdge:
        (s_kind, s_key), (t_kind, t_key) = split_id(self.source), split_id(self.target)
        if self.id != f"e:{self.type.value}:{s_key}:{t_key}":
            raise ValueError("id must be e:<TYPE>:<source key>:<target key>")
        if not self.evidence_ids or self.evidence_ids != sorted(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be non-empty, ascending and unique")
        if (self.evidence_class is EvidenceClass.INFERENCE) != self.experimental:
            raise ValueError("an edge is experimental if and only if its evidence class is INFERENCE")
        if self.type is EdgeType.NCO_GROUP_PROXIMITY:
            self._check_nco_proximity(s_kind, s_key, t_kind, t_key)
            return self
        rule = _RULES.get(self.type)
        if rule is None:  # TITLE_SIMILARITY (COULD, not planned): its contract is not defined, so none is enforced
            return self
        s_kinds, t_kinds, directed, evidence_class = rule
        if s_kind not in s_kinds or t_kind not in t_kinds:
            raise ValueError(f"{self.type.value} runs from {[k.value for k in s_kinds]} to {[k.value for k in t_kinds]}")
        if self.directed is not directed or self.evidence_class is not evidence_class or self.experimental:
            raise ValueError(f"{self.type.value} is directed={directed}, {evidence_class.value} and not experimental")
        if t_kind in (IdKind.MOD, IdKind.CLAIM) and not t_key.startswith(s_key + "/"):
            raise ValueError("a module or claim endpoint must belong to the source qualification")
        if self.type is EdgeType.SHARES_NOS:
            if not self.source < self.target:
                raise ValueError("SHARES_NOS is stored once, with source < target")
            self._check_shares_attributes()
        return self

    def _check_nco_proximity(self, s_kind: IdKind, s_key: str, t_kind: IdKind, t_key: str) -> None:
        """P3.5 (``graph.inference``, D-15 .. D-20): qualification <-> qualification, INFERENCE, experimental, flagged."""
        if s_kind is not IdKind.QUAL or t_kind is not IdKind.QUAL:
            raise ValueError("NCO_GROUP_PROXIMITY runs from a qualification to a qualification")
        if self.directed or self.evidence_class is not EvidenceClass.INFERENCE or not self.experimental:
            raise ValueError("NCO_GROUP_PROXIMITY is undirected, INFERENCE and experimental")
        if not self.source < self.target:
            raise ValueError("NCO_GROUP_PROXIMITY is stored once, with source < target")
        if QualityFlagCode.INFERENCE_EXPERIMENTAL not in {f.code for f in self.flags}:
            raise ValueError("an inference edge carries the INFERENCE_EXPERIMENTAL flag")
        a = self.attributes
        if set(a) != _NCO_PROXIMITY_KEYS:
            raise ValueError(f"NCO_GROUP_PROXIMITY attributes must be exactly {sorted(_NCO_PROXIMITY_KEYS)}")
        digits, groups, by_qual = a["group_digits"], a["shared_groups"], a["codes_by_qualification"]
        if type(digits) is not int or digits not in (3, 4):
            raise ValueError("group_digits must be 3 or 4")
        if not (isinstance(groups, list) and groups and groups == sorted(set(groups))
                and all(isinstance(g, str) and len(g) == digits and g.isdecimal() for g in groups)):
            raise ValueError("shared_groups must be a non-empty, ascending, unique list of group_digits-digit groups")
        if not (isinstance(by_qual, dict) and set(by_qual) == {s_key, t_key}):
            raise ValueError("codes_by_qualification must list exactly the two qualifications")
        for codes in by_qual.values():
            if not (isinstance(codes, list) and codes and codes == sorted(set(codes))
                    and all(isinstance(c, str) and _NCO_CODE.fullmatch(c) for c in codes)):
                raise ValueError("codes_by_qualification must hold ascending, unique NCO codes")
        if any({c[:digits] for c in codes} != set(groups) for codes in by_qual.values()):
            raise ValueError("every shared group must be reached by a stated code of each qualification, and no other")

    def _check_shares_attributes(self) -> None:
        a = self.attributes
        if set(a) != _SHARES_KEYS:
            raise ValueError(f"SHARES_NOS attributes must be exactly {sorted(_SHARES_KEYS)}")
        codes, mixed, agreement = a["shared_codes"], a["mixed_core_codes"], a["version_agreement"]
        if not (isinstance(codes, list) and codes and codes == sorted(set(codes))):
            raise ValueError("shared_codes must be a non-empty, ascending, unique list")
        if not (isinstance(mixed, list) and set(mixed) <= set(codes) and mixed == sorted(set(mixed))):
            raise ValueError("mixed_core_codes must be an ascending subset of shared_codes")
        counts = (a["core_shared_count"], a["noncore_shared_count"])
        if any(type(c) is not int or c < 0 for c in counts) or sum(counts) + len(mixed) != len(codes):
            raise ValueError("core + non-core + mixed must account for every shared code")
        if not (isinstance(agreement, dict) and set(agreement) == set(codes)
                and set(agreement.values()) <= _VERSION_AGREEMENT):
            raise ValueError("version_agreement must map every shared code to SAME, DIFFERENT or NOT_STATED")


class LegendEntry(SchemaModel):
    """API_SPEC E08 ``LegendEntry``: what an edge type means, and what it does not."""

    edge_type: EdgeType
    evidence_class: EvidenceClass
    meaning: str
    does_not_mean: str


class GraphError(Exception):
    """Base of every graph failure."""


class EdgeBuildError(GraphError):
    """The registry holds a relationship that cannot become a valid edge. ``problems`` lists every one found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems: tuple[str, ...] = tuple(problems)
        shown = "; ".join(self.problems[:MAX_PROBLEMS_SHOWN])
        more = len(self.problems) - MAX_PROBLEMS_SHOWN
        super().__init__(f"cannot build static edges: {shown}" + (f" (+{more} more)" if more > 0 else ""))


# --------------------------------------------------------------------------------------------------------------------
# Legend
# --------------------------------------------------------------------------------------------------------------------

_LEGEND = (
    LegendEntry(
        edge_type=EdgeType.INCLUDES_NOS, evidence_class=EvidenceClass.OFFICIAL,
        meaning="The qualification's official QF lists this NOS unit or module as a row of its NOS table.",
        does_not_mean="The unit is separately certified, exempt from re-training, or transferable to another qualification.",
    ),
    LegendEntry(
        edge_type=EdgeType.SHARES_NOS, evidence_class=EvidenceClass.RULE_DERIVED,
        meaning="Both qualifications list the same NOS code in their official QF.",
        does_not_mean="Skills are equivalent, units are exempt, or people move between these roles.",
    ),
    LegendEntry(
        edge_type=EdgeType.PROGRESSION_CLAIM, evidence_class=EvidenceClass.OFFICIAL,
        meaning="The qualification's official QF (item 15) lists this text as a progression.",
        does_not_mean="That the text is linked to a qualification in this graph (any such link is an experimental inference), that anyone is eligible for it, or that people make this move.",
    ),
    LegendEntry(
        edge_type=EdgeType.ALIGNED_TO_NCO, evidence_class=EvidenceClass.OFFICIAL,
        meaning="The qualification's official documents state this NCO-2015 occupation code.",
        does_not_mean="The qualification leads to that occupation, jobs exist in it, or qualifications sharing a code are interchangeable.",
    ),
)


def static_legend() -> tuple[LegendEntry, ...]:
    """One legend entry per static edge type, in ``STATIC_EDGE_TYPES`` order (immutable)."""
    return _LEGEND


# --------------------------------------------------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------------------------------------------------


def _key(entity_id: str) -> str:
    return split_id(entity_id)[1]


def _edge_id(edge_type: EdgeType, source: str, target: str) -> str:
    return f"e:{edge_type.value}:{_key(source)}:{_key(target)}"


def _cells(m: NosMembership) -> list[Valued[Any]]:
    """Every printed cell of the NOS-table row (D-8): level, version when printed, hours, credits."""
    h = m.hours
    cells: list[Valued[Any]] = [m.nsqf_level, m.credits, h.total]
    cells += [v for v in (m.version, h.theory, h.practical, h.ojt_mandatory, h.ojt_recommended) if v is not None]
    return cells


def _version(m: NosMembership) -> str | None:
    value = m.version.value if m.version is not None else None
    value = value.strip() if isinstance(value, str) else None
    return value or None


class _Builder:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self.problems: list[str] = []
        self.edges: dict[str, GraphEdge] = {}
        self._evidence_ok: set[str] = set()
        self._flags: dict[str, QualityFlag] = {}

    # ---- checks shared by every edge -------------------------------------------------------------------------------

    def evidence(self, ids: set[str], where: str) -> list[str] | None:
        """The sorted ids if every one resolves in the registry, else ``None`` (the problem is recorded)."""
        ok = True
        for eid in sorted(ids):
            if eid in self._evidence_ok:
                continue
            try:
                self.registry.evidence_by_id(eid)
            except UnknownEntityError:
                self.problems.append(f"{where}: evidence {eid} is not in the registry")
                ok = False
            else:
                self._evidence_ok.add(eid)
        if not ids:
            self.problems.append(f"{where}: no evidence id")
            ok = False
        return sorted(ids) if ok else None

    def conflict_flag(self, conflict_id: str, where: str) -> QualityFlag | None:
        if conflict_id not in self._flags:
            try:
                c = self.registry.conflict_by_id(conflict_id)
            except UnknownEntityError:
                self.problems.append(f"{where}: conflict {conflict_id} is not in the registry")
                return None
            self._flags[conflict_id] = QualityFlag(
                code=QualityFlagCode.SOURCE_CONFLICT, severity=Severity.INFO, refs=[conflict_id],
                message=f"Unresolved source conflict on {c.subject.field} of {c.subject.entity_id}; no value has been chosen.",
            )
        return self._flags[conflict_id]

    def flags(self, conflict_ids: set[str], where: str) -> list[QualityFlag] | None:
        found = [self.conflict_flag(cid, where) for cid in sorted(conflict_ids)]
        return None if None in found else found  # type: ignore[return-value]

    def add(self, edge: GraphEdge, where: str) -> None:
        if edge.id in self.edges:
            self.problems.append(f"{where}: the relationship {edge.id} is stated more than once")
        else:
            self.edges[edge.id] = edge

    # ---- the four edge types ---------------------------------------------------------------------------------------

    def run(self) -> list[GraphEdge]:
        reg = self.registry
        quals = reg.qualifications()
        nos_ids = {n.id for n in reg.nos_units()}
        nco_ids = {o.id for o in reg.occupations()}
        memberships: dict[str, dict[str, NosMembership]] = {}

        for q in quals:
            modules = {m.id: m for m in q.modules}
            own = memberships.setdefault(q.id, {})
            for m in q.nos_memberships:
                where = f"{q.id} NOS-table row S.No. {m.s_no}"
                target = m.nos_id if m.nos_id is not None else m.module_id
                if m.qualification_id != q.id:
                    self.problems.append(f"{where}: the membership belongs to {m.qualification_id}")
                    continue
                if m.nos_id is not None and m.nos_id not in nos_ids:
                    self.problems.append(f"{where}: unknown NOS unit {m.nos_id}")
                    continue
                if m.nos_id is None and (modules.get(m.module_id) is None or modules[m.module_id].qualification_id != q.id):
                    self.problems.append(f"{where}: {m.module_id} is not a module of {q.id}")
                    continue
                if m.nos_id is not None:
                    own.setdefault(m.nos_id, m)  # the first row stands for the unit; a repeat is reported by add()
                evidence = self.evidence({c.evidence_id for c in _cells(m) if c.evidence_id is not None}, where)
                flags = self.flags({c.conflict_id for c in _cells(m) if c.conflict_id is not None}, where)
                if evidence is None or flags is None:
                    continue
                self.add(GraphEdge(
                    id=_edge_id(EdgeType.INCLUDES_NOS, q.id, target), type=EdgeType.INCLUDES_NOS, source=q.id,
                    target=target, directed=True, evidence_class=EvidenceClass.OFFICIAL, experimental=False,
                    attributes={"s_no": m.s_no, "core_or_noncore": m.core_or_noncore.value,
                                "is_bridge": m.is_bridge, "version": _version(m)},
                    evidence_ids=evidence, flags=flags), where)

            for c in q.progression_claims:
                where = f"{q.id} claim {c.id}"
                evidence = self.evidence({c.evidence_id}, where)
                if c.qualification_id != q.id:
                    self.problems.append(f"{where}: the claim belongs to {c.qualification_id}")
                elif evidence is not None:
                    self.add(GraphEdge(
                        id=_edge_id(EdgeType.PROGRESSION_CLAIM, q.id, c.id), type=EdgeType.PROGRESSION_CLAIM,
                        source=q.id, target=c.id, directed=True, evidence_class=EvidenceClass.OFFICIAL,
                        experimental=False, attributes={"direction_label": c.direction_label},
                        evidence_ids=evidence), where)

            for n in q.nco_codes:
                where = f"{q.id} stated NCO code {n.value!r}"
                if n.value is None:
                    self.problems.append(f"{q.id}: a stated NCO code is null")
                    continue
                target = f"nco:{n.value}"
                evidence = self.evidence({n.evidence_id} if n.evidence_id is not None else set(), where)
                if target not in nco_ids:
                    self.problems.append(f"{where}: unknown occupation {target}")
                elif evidence is not None:
                    self.add(GraphEdge(
                        id=_edge_id(EdgeType.ALIGNED_TO_NCO, q.id, target), type=EdgeType.ALIGNED_TO_NCO,
                        source=q.id, target=target, directed=True, evidence_class=EvidenceClass.OFFICIAL,
                        experimental=False, attributes={}, evidence_ids=evidence), where)

        self._shares_nos(sorted(nos_ids), memberships)
        if self.problems:
            raise EdgeBuildError(self.problems)
        return sorted(self.edges.values(), key=lambda e: (e.type.value, e.source, e.target))

    def _shares_nos(self, nos_ids: list[str], memberships: dict[str, dict[str, NosMembership]]) -> None:
        pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
        for nos_id in nos_ids:
            users = self.registry.qualification_ids_with_nos(nos_id)  # ascending
            if any(nos_id not in memberships.get(u, {}) for u in users):
                self.problems.append(f"{nos_id}: the registry's users of the unit do not match the NOS tables")
                continue
            for a, b in combinations(users, 2):
                pairs[(a, b)].append(nos_id)
        for (a, b), codes in sorted(pairs.items()):
            where = f"{a} / {b}"
            rows = [(nos_id, memberships[a][nos_id], memberships[b][nos_id]) for nos_id in codes]
            cells = [c for _, ma, mb in rows for m in (ma, mb) for c in _cells(m)]
            evidence = self.evidence({c.evidence_id for c in cells if c.evidence_id is not None}, where)
            flags = self.flags({c.conflict_id for c in cells if c.conflict_id is not None}, where)
            if evidence is None or flags is None:
                continue
            core = [n for n, ma, mb in rows if ma.core_or_noncore is mb.core_or_noncore is CoreOrNonCore.CORE]
            noncore = [n for n, ma, mb in rows if ma.core_or_noncore is mb.core_or_noncore is CoreOrNonCore.NON_CORE]
            agreement: dict[str, str] = {}
            for n, ma, mb in rows:
                va, vb = _version(ma), _version(mb)
                agreement[_key(n)] = "NOT_STATED" if va is None or vb is None else "SAME" if va == vb else "DIFFERENT"
            shared = [_key(n) for n in codes]
            self.add(GraphEdge(
                id=_edge_id(EdgeType.SHARES_NOS, a, b), type=EdgeType.SHARES_NOS, source=a, target=b, directed=False,
                evidence_class=EvidenceClass.RULE_DERIVED, experimental=False,
                attributes={
                    "shared_codes": shared, "core_shared_count": len(core), "noncore_shared_count": len(noncore),
                    "mixed_core_codes": [_key(n) for n, ma, mb in rows if ma.core_or_noncore is not mb.core_or_noncore],
                    "version_agreement": dict(sorted(agreement.items())),
                },
                evidence_ids=evidence, flags=flags), where)


def build_static_edges(registry: Registry, include_inference: bool = False, *, nco_group_digits: int = 4) -> list[GraphEdge]:
    """The documented static edges of ``registry``, sorted by ``(type, source, target)`` (API_SPEC §4, E08).

    With ``include_inference=True`` (P3.5) the experimental ``NCO_GROUP_PROXIMITY`` edges of ``graph.inference`` are added to
    the same list, sorted by the same key. The static edges are exactly those returned without it: inference edges are
    separate records (``evidence_class = INFERENCE``, ``experimental = true``) and never replace, merge into or reorder a
    static edge. ``nco_group_digits`` (4 or 3) is read only when ``include_inference`` is true.

    Raises ``EdgeBuildError`` (every problem listed) if a relationship cannot become a valid edge. The registry is only read;
    the result is a new list of frozen edges on every call.
    """
    edges = _Builder(registry).run()
    if not include_inference:
        return edges
    from .inference import build_inference_edges  # imported here: inference.py builds on this module's edge types

    return sorted(edges + build_inference_edges(registry, nco_group_digits=nco_group_digits),
                  key=lambda e: (e.type.value, e.source, e.target))
