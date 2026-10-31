"""Source documents and the evidence registry (ARCHITECTURE §9.1 ``src:``/``ev:``, §9.2 ``Evidence``).

Evidence is OFFICIAL only when its source resolves: the (path, SHA-256) pair must name a manifest item with a usable
local file, whose bytes were re-hashed by the integrity verifier before the build started. An overlay's own
statement never makes anything OFFICIAL.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from skillgraph.model.evidence import Evidence, EvidenceClass, ValueStatus
from skillgraph.model.ids import make_id, IdKind
from skillgraph.model.source import ManifestStatus, SourceDocument, SourceRole
from skillgraph.provenance.manifest import _relative_to_raw

from .errors import BuildError, EvidenceError
from .inputs import Row

_AVAILABLE = {ManifestStatus.PASS, ManifestStatus.PASS_WITH_DISCREPANCIES}


class SourceRegistry:
    """One ``SourceDocument`` per manifest item, and the lookup from (raw-relative path, SHA-256) to it."""

    def __init__(self, manifest: list[Row], raw_root: Path, secondary_hashes: set[str]) -> None:
        self.raw_root = raw_root
        self.docs: dict[str, SourceDocument] = {}
        self._by_file: dict[tuple[str, str], str] = {}
        self.rel_path: dict[str, str] = {}
        for m in manifest:
            item = m["item_id"]
            try:
                status = ManifestStatus(m["validation_status"])
            except ValueError:
                raise BuildError(f"manifest item {item}: unknown validation_status {m['validation_status']!r}") from None
            path = m["local_relative_path"].strip()
            sha = m["sha256"].strip().lower()
            usable = status in _AVAILABLE and bool(path)
            rel = _relative_to_raw(path, raw_root) if usable else None
            if usable and rel is None:
                raise BuildError(f"manifest item {item}: local path {path!r} is not under {raw_root.name}")
            retrieved = None
            if m.get("retrieved_at"):
                try:
                    retrieved = datetime.fromisoformat(m["retrieved_at"])
                except ValueError:
                    retrieved = None
                if retrieved is not None and retrieved.tzinfo is None:
                    retrieved = None
            pages = m.get("pdf_pages", "").strip()
            ftype = m.get("file_type", "").strip().lower()
            try:
                doc = SourceDocument(
                    id=make_id(IdKind.SRC, item),
                    manifest_item_id=item,
                    title=m["item_name"],
                    org=m["source_org"],
                    url=(m.get("final_url") or m.get("source_url") or None),
                    retrieved_at=retrieved,
                    sha256=sha if usable else None,
                    file_type=ftype if ftype in ("pdf", "html") else None,
                    pages=int(pages) if pages.isdigit() and int(pages) > 0 else None,
                    validation_status=status,
                    role=SourceRole.SECONDARY if (usable and sha in secondary_hashes) else SourceRole.PRIMARY,
                )
            except (ValidationError, ValueError) as exc:
                raise BuildError(f"manifest item {item}: {exc}") from None
            if doc.id in self.docs:
                raise BuildError(f"manifest item {item} is listed twice")
            self.docs[doc.id] = doc
            if usable and rel:
                self._by_file[(rel, sha)] = doc.id
                self.rel_path[doc.id] = rel

    def source_for(self, source_file: str, sha256: str) -> SourceDocument:
        """The available source named by an extraction/overlay (path, hash) pair, or ``EvidenceError``."""
        key = (source_file.replace("\\", "/").strip(), sha256.strip().lower())
        sid = self._by_file.get(key)
        if sid is None:
            raise EvidenceError(f"no available manifest source for {key[0]!r} with SHA-256 {key[1][:12]}…")
        doc = self.docs[sid]
        if not doc.has_local_file or not (self.raw_root / self.rel_path[sid]).is_file():
            raise EvidenceError(f"{sid} has no usable local file")
        return doc

    def available(self, item_id: str) -> SourceDocument:
        doc = self.docs.get(make_id(IdKind.SRC, item_id))
        if doc is None or not doc.has_local_file:
            raise EvidenceError(f"manifest item {item_id} is not an available source")
        return doc


def page_numbers(page: str) -> set[int]:
    """``'3'`` -> {3}; ``'3-4'`` -> {3, 4}; ``'5-6'`` -> {5, 6}. Anything else is an error."""
    m = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", page or "")
    if not m:
        raise EvidenceError(f"unreadable page {page!r}")
    lo, hi = int(m[1]), int(m[2] or m[1])
    if hi < lo:
        raise EvidenceError(f"unreadable page range {page!r}")
    return set(range(lo, hi + 1))


def evidence_id(*parts: str) -> str:
    """``ev:`` + 16 hex digits of SHA-256 over (source id, page, record key, field) (ARCHITECTURE §9.1)."""
    return "ev:" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


class EvidenceBook:
    """All evidence records of a build, keyed by id. Adding the same cell twice merges overlay references."""

    def __init__(self, sources: SourceRegistry) -> None:
        self.sources = sources
        self.items: dict[str, Evidence] = {}

    def official(
        self,
        *,
        source_file: str,
        sha256: str,
        page: str,
        record_key: str,
        field: str,
        value_status: ValueStatus,
        method: str | None,
        location: str | None = None,
        overlay_ids: tuple[str, ...] = (),
        decision_refs: tuple[str, ...] = (),
        note: str | None = None,
    ) -> str:
        src = self.sources.source_for(source_file, sha256)
        if src.sha256 != sha256.strip().lower():  # defensive: the registry keys on the hash already
            raise EvidenceError(f"{src.id}: evidence hash differs from the SourceDocument hash")
        if not (page.strip() or location):
            raise EvidenceError(f"{record_key} {field}: evidence needs a page or a location")
        if page.strip() and src.pages is not None and max(page_numbers(page)) > src.pages:
            raise EvidenceError(f"{record_key} {field}: page {page} is beyond the {src.pages} pages of {src.id}")
        eid = evidence_id(src.id, page.strip(), record_key, field)
        ids = sorted(set(overlay_ids))
        refs = sorted(set(decision_refs))
        old = self.items.get(eid)
        if old is not None:
            if old.value_status != value_status or old.source_id != src.id:
                raise BuildError(f"{eid}: one cell was given two different statuses ({old.value_status}, {value_status})")
            ids = sorted(set(old.overlay_ids) | set(ids))
            refs = sorted(set(old.decision_refs) | set(refs))
        try:
            self.items[eid] = Evidence(
                id=eid,
                evidence_class=EvidenceClass.OFFICIAL,
                source_id=src.id,
                source_sha256=src.sha256,
                page=page.strip() or None,
                location=location,
                method=method or None,
                value_status=value_status,
                overlay_ids=ids,
                decision_refs=refs,
                note=note or (old.note if old else None),
            )
        except ValidationError as exc:
            raise EvidenceError(f"{record_key} {field}: {exc}") from None
        return eid

    def derived(self, key: str, derived_from: list[str], note: str) -> str:
        eid = evidence_id("derived", key)
        try:
            self.items[eid] = Evidence(
                id=eid, evidence_class=EvidenceClass.RULE_DERIVED, derived_from=sorted(set(derived_from)), note=note
            )
        except ValidationError as exc:
            raise EvidenceError(f"{key}: {exc}") from None
        return eid
