"""Experimental inference edges (ARCHITECTURE §10.1, §10.3, §13.4; API_SPEC E08, §4; TASKS P3.5).

``build_inference_edges(registry)`` builds the one inference edge type that the specification defines completely enough to
implement without inventing a method: ``NCO_GROUP_PROXIMITY``.

========================== ============= ============ ============================================================
edge                       direction     class        source in the registry
========================== ============= ============ ============================================================
``NCO_GROUP_PROXIMITY``    qual <-> qual ``INFERENCE`` two qualifications' stated NCO-2015 codes (the OFFICIAL
                                                      ``ALIGNED_TO_NCO`` relationships) share a code prefix
========================== ============= ============ ============================================================

What the contract fixes (ARCHITECTURE §13.4, TASKS P3.5, API_SPEC E08): two qualifications whose *stated* NCO codes share a
unit group (the first 4 digits), or, when configured, a minor group (the first 3 digits); the 3-digit level is
configurable; the edge is ``INFERENCE`` and ``experimental``; it is hidden unless ``include_inference`` is true; it carries the
``INFERENCE_EXPERIMENTAL`` warning; it measures "classification proximity of the occupations the qualifications align to"
and does **not** measure skill overlap, feasibility or mobility; it is never used for feasibility (§10.3) and never changes a
path set, a verdict or an order (§10.3 invariant; tested again by P3.6).

What the contract does not fix, and what this module therefore does **not** do:

* no similarity, distance, score, weight, probability, rank or confidence is computed or stored - the contract names no
  confidence semantics. An edge exists or it does not;
* no title, level, hours, credit, age, eligibility rule, labour-market figure or LLM is consulted; only the stated codes
  and their code prefixes (derived by ``Occupation.nco_levels``, a pure string derivation) are read;
* ``TITLE_SIMILARITY`` is COULD and "not planned" (TASKS P3.5): it is not built, and the ``GraphEdge`` contract for it stays
  undefined;
* the name-based progression-target link is not an edge here (see ``claim_candidates.py``).

Decisions where the specification is silent (D-15 … D-20 continue D-1 … D-14; recorded in ``TASKS.md``):

D-15  One edge per unordered pair of distinct qualifications that share at least one group at the configured level. If they
      share several groups, there is still one edge and ``shared_groups`` lists them. Two codes of one qualification never
      make an edge. Qualifications of every ``coverage`` take part, as in D-7 (the real build's catalogue-only records state
      no NCO code).
D-16  Attributes, the smallest set that makes an edge traceable and checkable: ``group_digits`` (3 or 4),
      ``shared_groups`` (ascending, each exactly ``group_digits`` digits) and ``codes_by_qualification`` (for each of the two
      qualifications, the ascending stated codes that fall in a shared group). E08 defines no attribute set for this type.
D-17  Provenance: ``evidence_ids`` are the evidence ids of the stated NCO codes listed in ``codes_by_qualification`` (the
      OFFICIAL cells the inference is computed from; the same ids that the ``ALIGNED_TO_NCO`` edges cite), sorted and unique.
D-18  Identity and order as D-13: id ``e:NCO_GROUP_PROXIMITY:<source key>:<target key>``, undirected, stored once with
      ``source < target``, sorted by ``(type, source, target)``. Repeated calls, and registries assembled from the same
      records in any order, give equal results.
D-19  Invalid input is reported, never repaired (as D-9): a null stated code, a code with no occupation record, a code with no
      or an unresolved evidence id, or one code stated twice by one qualification raises ``EdgeBuildError`` listing every
      problem. Nothing is dropped, merged or guessed. A bad ``nco_group_digits`` raises ``ValueError``.
D-20  Configuration: the level is the keyword ``nco_group_digits`` (4 by default, or 3). The specification names no settings
      key for it and ``config/default.yaml`` has only ``inference.enabled``; no key was invented, so the service layer (P3.10)
      must pass the value. Every edge carries the ``INFERENCE_EXPERIMENTAL`` flag (E08, "Warnings"); the legend wording is
      drafted from ARCHITECTURE §13.4 and is for review, like D-14.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from skillgraph.model.evidence import EvidenceClass, QualityFlag, QualityFlagCode, Severity
from skillgraph.model.ids import split_id
from skillgraph.registry import Registry, UnknownEntityError

from .edges import EdgeBuildError, EdgeType, GraphEdge, LegendEntry

NCO_GROUP_DIGITS_DEFAULT = 4
NCO_GROUP_DIGITS_ALLOWED = (4, 3)

INFERENCE_EDGE_TYPES = (EdgeType.NCO_GROUP_PROXIMITY,)

_FLAG = QualityFlag(
    code=QualityFlagCode.INFERENCE_EXPERIMENTAL, severity=Severity.INFO,
    message="Experimental inference from NCO code prefixes. It is not documented by any qualification source and is never "
            "used for eligibility, feasibility or ranking.",
)

_LEGEND = (
    LegendEntry(
        edge_type=EdgeType.NCO_GROUP_PROXIMITY, evidence_class=EvidenceClass.INFERENCE,
        meaning="Experimental inference: the official documents of both qualifications state NCO-2015 occupation codes that "
                "begin with the same digits (4 digits = unit group, 3 digits = minor group).",
        does_not_mean="That the qualifications share skills, are equivalent or interchangeable, that anyone is eligible for one "
                      "after the other, that people move between these roles, or that jobs exist in the occupation.",
    ),
)


def inference_legend() -> tuple[LegendEntry, ...]:
    """One legend entry per inference edge type that is built, in ``INFERENCE_EDGE_TYPES`` order (immutable)."""
    return _LEGEND


def _prefix(occupation, digits: int) -> str:
    return occupation.nco_levels.family if digits == 4 else occupation.nco_levels.group


def build_inference_edges(registry: Registry, *, nco_group_digits: int = NCO_GROUP_DIGITS_DEFAULT) -> list[GraphEdge]:
    """The ``NCO_GROUP_PROXIMITY`` edges of ``registry``, sorted by ``(type, source, target)``.

    ``nco_group_digits`` is 4 (unit group, the default) or 3 (minor group). Raises ``ValueError`` for another value and
    ``EdgeBuildError`` (every problem listed) for invalid stated codes. The registry is only read.
    """
    if type(nco_group_digits) is not int or nco_group_digits not in NCO_GROUP_DIGITS_ALLOWED:
        raise ValueError(f"nco_group_digits must be one of {NCO_GROUP_DIGITS_ALLOWED}, got {nco_group_digits!r}")

    problems: list[str] = []
    # group prefix -> qualification id -> [(stated code, evidence id)]
    groups: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for q in sorted(registry.qualifications(), key=lambda x: x.id):
        seen: set[str] = set()
        for n in q.nco_codes:
            where = f"{q.id} stated NCO code {n.value!r}"
            if n.value is None:
                problems.append(f"{q.id}: a stated NCO code is null")
                continue
            if n.value in seen:
                problems.append(f"{where}: stated more than once")
                continue
            seen.add(n.value)
            try:
                occupation = registry.occupation_by_nco_code(n.value)
            except UnknownEntityError:
                problems.append(f"{where}: unknown occupation nco:{n.value}")
                continue
            if n.evidence_id is None:
                problems.append(f"{where}: no evidence id")
                continue
            try:
                registry.evidence_by_id(n.evidence_id)
            except UnknownEntityError:
                problems.append(f"{where}: evidence {n.evidence_id} is not in the registry")
                continue
            groups[_prefix(occupation, nco_group_digits)][q.id].append((n.value, n.evidence_id))
    if problems:
        raise EdgeBuildError(problems)

    pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for prefix, members in groups.items():
        for a, b in combinations(sorted(members), 2):
            pairs[(a, b)].add(prefix)

    edges: list[GraphEdge] = []
    for (a, b), prefixes in sorted(pairs.items()):
        shared = sorted(prefixes)
        used = {q: sorted({item for p in shared for item in groups[p].get(q, [])}) for q in (a, b)}
        edges.append(GraphEdge(
            id=f"e:{EdgeType.NCO_GROUP_PROXIMITY.value}:{split_id(a)[1]}:{split_id(b)[1]}",
            type=EdgeType.NCO_GROUP_PROXIMITY, source=a, target=b, directed=False,
            evidence_class=EvidenceClass.INFERENCE, experimental=True,
            attributes={
                "group_digits": nco_group_digits,
                "shared_groups": shared,
                "codes_by_qualification": {split_id(q)[1]: [code for code, _ in used[q]] for q in (a, b)},
            },
            evidence_ids=sorted({eid for q in (a, b) for _, eid in used[q]}),
            flags=[_FLAG],
        ))
    return sorted(edges, key=lambda e: (e.type.value, e.source, e.target))
