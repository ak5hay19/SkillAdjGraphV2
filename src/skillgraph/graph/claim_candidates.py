"""Name-matched progression-target *candidates* (ARCHITECTURE §10.3, §13.4, DQ-15; TASKS P3.5). Not edges.

A progression claim (QF item 15) is verbatim ``DISPLAY_ONLY`` text. Linking it to a catalogue qualification by name is an
``INFERENCE`` that "needs review" (DQ-15) and may only become a graph relationship "via reviewed inference" (§10.3). No review
has taken place and the contract defines no edge type for the link (``PROGRESSION_CLAIM`` ends at a ``claim:`` node and
``GraphEdge`` refuses a qualification target). So this module produces **candidates for a human reviewer**, as TASKS P3.5
says ("written to the review file as candidates"), and nothing else: it creates no edge, sets no ``resolved_target``, changes
no record, feeds no verdict, path or ranking, and is not reachable from ``build_static_edges``.

Matching: the claim text, after the normalisation below, equals the normalised **catalogue title** of another record (TASKS:
"claim text to catalogue titles"). Exact equality of normalised strings only - no similarity, stemming, abbreviation, word
order or synonym handling. ARCHITECTURE §13.4 says only "normalised text match"; the normalisation is the narrowest reading
that reproduces the two examples the contract gives ("Sampling Coordinator" matches AMH/Q1801; "QC Executive - Sewing Line"
has no exact match), and it is recorded as D-21 for review:

1. the claim's own trailing direction label in parentheses is removed - the claim text is stored with it ("Sampling
   Coordinator(Vertical)") while the label is a separate field of the same record;
2. Unicode NFKC, then case folding;
3. the text is reduced to its sequence of letters and digits (every other character, such as a space, hyphen, dash, bracket or
   ``&``, separates tokens), joined by single spaces.

D-22: ambiguity and self reference are reported, never resolved. Two catalogue titles that normalise equally give two
candidates for the claim (``candidate_count`` = 2), and none is preferred. A claim that matches the title of its own
qualification is kept and marked ``target_is_source``. A claim with no match is listed in ``unmatched_claim_ids``. Catalogue-
title-less records cannot match. Each candidate carries the claim's evidence id; the catalogue title is a plain string in the
registry and has no evidence id of its own (a gap: the reviewer must confirm the title in the catalogue).

D-23: the candidates are returned and can be rendered as a Markdown section (``render_review_section``); this module writes
no file. The build's ``eligibility_rules_review.md`` lies in the protected ``data/`` tree and is a generated snapshot, so it is
neither edited nor regenerated here; ``docs/decisions/P3_5_INFERENCE.md`` records the candidates observed on the real build.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from skillgraph.model.base import SchemaModel
from skillgraph.model.evidence import EngineUse, EvidenceClass
from skillgraph.model.ids import ClaimId, EvidenceId, QualificationId
from skillgraph.registry import Registry

_TOKENS = re.compile(r"[^\W_]+")


def normalise_name(text: str, direction_label: str | None = None) -> str:
    """The comparison form of a claim text or a catalogue title (D-21). ``direction_label`` is the claim's own label."""
    t = unicodedata.normalize("NFKC", text)
    if direction_label:
        t = re.sub(rf"\s*\(\s*{re.escape(unicodedata.normalize('NFKC', direction_label))}\s*\)\s*$", "", t, flags=re.IGNORECASE)
    return " ".join(_TOKENS.findall(t.casefold()))


class ClaimTitleCandidate(SchemaModel):
    """One unreviewed candidate link from a progression claim to a catalogue qualification. Never an edge."""

    claim_id: ClaimId
    source_qualification_id: QualificationId
    claim_text: str
    direction_label: str
    candidate_qualification_id: QualificationId
    candidate_title: str
    normalised_name: str
    candidate_count: int  # the number of candidates for this claim: more than 1 means the name is ambiguous
    target_is_source: bool
    evidence_class: Literal[EvidenceClass.INFERENCE] = EvidenceClass.INFERENCE
    engine_use: Literal[EngineUse.DISPLAY_ONLY] = EngineUse.DISPLAY_ONLY
    status: Literal["UNREVIEWED_CANDIDATE"] = "UNREVIEWED_CANDIDATE"
    evidence_ids: list[EvidenceId]  # the claim's own evidence id (the title is the catalogue's plain string, see D-22)


class ClaimCandidateReport(SchemaModel):
    candidates: list[ClaimTitleCandidate]
    unmatched_claim_ids: list[ClaimId]


def claim_title_candidates(registry: Registry) -> ClaimCandidateReport:
    """Every progression claim against every catalogue title: candidates sorted by ``(claim_id, candidate id)``."""
    quals = sorted(registry.qualifications(), key=lambda q: q.id)
    by_name: dict[str, list[tuple[str, str]]] = {}
    for q in quals:
        title = q.titles.catalogue
        name = normalise_name(title) if title is not None else ""
        if name:
            by_name.setdefault(name, []).append((q.id, title))

    candidates: list[ClaimTitleCandidate] = []
    unmatched: list[str] = []
    for q in quals:
        for c in sorted(q.progression_claims, key=lambda x: x.id):
            name = normalise_name(c.text_verbatim, c.direction_label)
            matches = by_name.get(name, []) if name else []
            if not matches:
                unmatched.append(c.id)
            candidates += [
                ClaimTitleCandidate(
                    claim_id=c.id, source_qualification_id=q.id, claim_text=c.text_verbatim,
                    direction_label=c.direction_label, candidate_qualification_id=target_id, candidate_title=title,
                    normalised_name=name, candidate_count=len(matches), target_is_source=target_id == q.id,
                    evidence_ids=[c.evidence_id],
                )
                for target_id, title in sorted(matches)
            ]
    return ClaimCandidateReport(
        candidates=sorted(candidates, key=lambda x: (x.claim_id, x.candidate_qualification_id)),
        unmatched_claim_ids=sorted(unmatched),
    )


def render_review_section(report: ClaimCandidateReport) -> str:
    """A Markdown section for a reviewer (D-23). Wording states that nothing here is a decision."""
    lines = [
        "## Name-matched progression targets (experimental inference, unreviewed)",
        "",
        "Nothing here is a decision or an official link. A match means only that the normalised claim text equals a "
        "normalised catalogue title; it does not mean the pathway is endorsed and it never changes a verdict.",
        "",
        "| Claim | Claim text | Candidate | Catalogue title | Candidates | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for c in report.candidates:
        notes = "; ".join(n for n, on in (("ambiguous", c.candidate_count > 1), ("same qualification", c.target_is_source)) if on)
        lines.append(f"| `{c.claim_id}` | {c.claim_text} | `{c.candidate_qualification_id}` | {c.candidate_title} | "
                     f"{c.candidate_count} | {notes} |")
    lines += ["", "No exact match: " + (", ".join(f"`{i}`" for i in report.unmatched_claim_ids) or "none") + "."]
    return "\n".join(lines) + "\n"
