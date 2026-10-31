"""Resolve every overlay ``target_row_key`` to the extraction rows it names (fail closed).

The keys are not uniform. Each ``target_file`` has its own grammar, and four keys are not single-row keys:

======================  ==============================================  ===========================================
target_file             key (after ``<qp>|<doc>|``)                      resolves to
======================  ==============================================  ===========================================
eligibility_rows.csv    ``eligibility_row|<n>`` / ``age_9c``             exactly one row
qf_nos.csv              ``<nos_code>``                                   exactly one row
qf_nos.csv              ``bridge(s_no <n>)+<nos_code>`` (OV-034/035)     exactly two adjacent rows: the bridge row
                                                                         and the NOS row sharing one credit cell
qf_nos.csv              ``s_no sequence`` (OV-041)                       every row of the qualification's table
qp_nos_headers.csv      ``<nos_code>``                                   exactly one row
facts.csv               ``<field>``                                      exactly one row (column ``value``)
progression_claims.csv  ``claim <n>`` / ``claims <a>-<b>`` (OV-032/033)  exactly one row / exactly b-a+1 rows
======================  ==============================================  ===========================================

Zero matches, several matches, an unknown grammar, a qp_code that disagrees with the key or an unknown column all
raise ``TargetError``; nothing is guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .errors import TargetError
from .overlay import OverlayRow

Row = dict[str, str]


class TargetKind(StrEnum):
    CELL = "CELL"
    COMPOSITE = "COMPOSITE"  # two rows sharing one cell (credit group)
    RANGE = "RANGE"  # several progression claims
    SEQUENCE = "SEQUENCE"  # the s_no column of one table


@dataclass(frozen=True)
class Target:
    overlay_id: str
    file: str
    kind: TargetKind
    rows: tuple[Row, ...]
    field: str

    @property
    def row(self) -> Row:
        if self.kind is not TargetKind.CELL:
            raise TargetError(f"{self.overlay_id}: {self.kind.value} target has no single row")
        return self.rows[0]

    @property
    def cell(self) -> str:
        return self.row[self.field]


_COMPOSITE = re.compile(r"bridge\(s_no (\d+)\)\+(\S+)")
_RANGE = re.compile(r"claims (\d+)-(\d+)")
_CLAIM = re.compile(r"claim (\d+)")
_ELIG = re.compile(r"eligibility_row\|(\d+)")


def _exactly(oid: str, rows: list[Row], n: int, what: str) -> tuple[Row, ...]:
    if len(rows) != n:
        raise TargetError(f"{oid}: {what} matched {len(rows)} row(s), expected exactly {n}")
    return tuple(rows)


def resolve_target(ov: OverlayRow, tables: dict[str, list[Row]]) -> Target:
    oid, file = ov.overlay_id, ov.target_file
    if file not in tables:
        raise TargetError(f"{oid}: unknown target_file {file!r}")
    parts = ov.target_row_key.split("|", 2)
    if len(parts) != 3 or not all(parts):
        raise TargetError(f"{oid}: malformed target_row_key {ov.target_row_key!r}")
    qp, doc, rest = parts
    if qp != ov.qp_code:
        raise TargetError(f"{oid}: key names {qp} but qp_code is {ov.qp_code}")
    rows = tables[file]
    if rows and ov.target_field not in rows[0]:
        raise TargetError(f"{oid}: {file} has no column {ov.target_field!r}")
    mine = [r for r in rows if r["qp_code"] == qp and r["doc_type"] == doc]
    what = f"{ov.target_row_key} in {file}"

    if file == "eligibility_rows.csv":
        if rest == "age_9c":
            sel = [r for r in mine if r["row_type"] == "age_9c"]
            return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)
        m = _ELIG.fullmatch(rest)
        if not m:
            raise TargetError(f"{oid}: unknown eligibility_rows.csv key {rest!r}")
        sel = [r for r in mine if r["row_type"] == "eligibility_row" and r["s_no"] == m[1]]
        return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)

    if file == "qf_nos.csv":
        if rest == "s_no sequence":
            if ov.target_field != "s_no" or not mine:
                raise TargetError(f"{oid}: 's_no sequence' needs field s_no and a non-empty table")
            return Target(oid, file, TargetKind.SEQUENCE, tuple(mine), "s_no")
        m = _COMPOSITE.fullmatch(rest)
        if m:
            bridge = _exactly(oid, [r for r in mine if r["s_no"] == m[1] and r["is_bridge"] == "true"], 1, f"bridge s_no {m[1]}")
            nos = _exactly(oid, [r for r in mine if r["nos_code"] == m[2] and r["is_bridge"] != "true"], 1, f"NOS {m[2]}")
            if int(nos[0]["s_no"]) != int(bridge[0]["s_no"]) + 1:
                raise TargetError(f"{oid}: the NOS row is not adjacent to the bridge row (no shared cell)")
            return Target(oid, file, TargetKind.COMPOSITE, bridge + nos, ov.target_field)
        sel = [r for r in mine if r["nos_code"] == rest and rest]
        return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)

    if file == "qp_nos_headers.csv":
        sel = [r for r in mine if r["nos_code"] == rest and rest]
        return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)

    if file == "facts.csv":
        sel = [r for r in mine if r["field"] == rest]
        return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)

    if file == "progression_claims.csv":
        m = _CLAIM.fullmatch(rest)
        if m:
            sel = [r for r in mine if r["claim_no"] == m[1]]
            return Target(oid, file, TargetKind.CELL, _exactly(oid, sel, 1, what), ov.target_field)
        m = _RANGE.fullmatch(rest)
        if m and int(m[1]) < int(m[2]):
            want = {str(i) for i in range(int(m[1]), int(m[2]) + 1)}
            sel = sorted((r for r in mine if r["claim_no"] in want), key=lambda r: int(r["claim_no"]))
            return Target(oid, file, TargetKind.RANGE, _exactly(oid, sel, len(want), what), ov.target_field)
        raise TargetError(f"{oid}: unknown progression_claims.csv key {rest!r}")

    raise TargetError(f"{oid}: no key grammar for {file}")


def check_source_value(ov: OverlayRow, t: Target) -> None:
    """The overlay's recorded ``source_value`` must equal what the extraction holds for the target (stale overlay =>
    ``TargetError``). Where the overlay stores a compound description, the expected string is built from the rows."""
    if t.kind is TargetKind.CELL:
        actual = t.cell
    elif t.kind is TargetKind.COMPOSITE:
        bridge, nos = t.rows
        actual = f"bridge={bridge[t.field]!r}; {nos['nos_code']}={nos[t.field]!r}"
    elif t.kind is TargetKind.SEQUENCE:
        actual = ",".join(r["s_no"] for r in t.rows)
    else:
        actual = " / ".join(r[t.field] for r in t.rows)
    if ov.source_value != actual:
        raise TargetError(
            f"{ov.overlay_id}: overlay source_value {ov.source_value!r} differs from the extraction {actual!r}; stale"
        )
