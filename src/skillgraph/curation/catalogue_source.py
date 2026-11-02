"""Verify the catalogue CSV against the AMHSSC approved-qualifications page (manifest item A1) it was parsed from.

``approved_qualifications_parsed.csv`` is a derived file. Catalogue-only values are labelled OFFICIAL and cite A1, so
the build re-parses A1's HTML table with the standard library and requires every catalogue row to agree with it
field by field. Only whitespace is normalised (runs collapsed, ends stripped), which is also what the acquisition
script's cleaner does; no character, case or number is altered, so the S.No. 27 en dash is compared as an en dash.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .errors import BuildError
from .inputs import Row

# CSV column -> header text of the A1 table (case-insensitive, whitespace collapsed).
COLUMNS: dict[str, str] = {
    "sno": "s.no.", "qp_name": "qp name", "qp_code": "qp code", "nqr_code": "nqr code", "qp_version": "qp version",
    "nsqf_level": "nsqf level", "notional_hours": "notional hours", "credits": "credits", "ccn": "ccn",
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_collapse("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_a1(content: bytes) -> list[dict[str, str]]:
    """The data rows of A1's qualification table as {csv column: text}. Raises BuildError if it cannot be read."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BuildError(f"A1 is not valid UTF-8, so the catalogue cannot be verified: {exc}") from None
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    wanted = list(COLUMNS.values())
    for table in parser.tables:
        if not table:
            continue
        header = [_collapse(h).lower() for h in table[0]]
        if "qp code" not in header:
            continue
        missing = [h for h in wanted if h not in header]
        if missing:
            raise BuildError(f"A1's qualification table lacks the column(s) {', '.join(missing)}; header is {header}")
        index = {csv_col: header.index(h) for csv_col, h in COLUMNS.items()}
        rows = []
        for cells in table[1:]:
            if not cells:
                continue
            if len(cells) < len(header):
                raise BuildError(f"A1 table row {cells[:2]} has {len(cells)} cells, expected {len(header)}")
            rows.append({c: cells[i] for c, i in index.items()})
        if not rows:
            raise BuildError("A1's qualification table has no data rows")
        return rows
    raise BuildError("A1 contains no qualification table (a table with a 'QP Code' column), so the catalogue cannot be verified")


def verify_catalogue(catalogue: list[Row], a1_content: bytes) -> int:
    """Require the parsed catalogue CSV to equal A1's table. Returns the number of rows verified."""
    html_rows = parse_a1(a1_content)
    by_sno: dict[str, dict[str, str]] = {}
    for r in html_rows:
        if r["sno"] in by_sno:
            raise BuildError(f"A1 lists S.No. {r['sno']} twice")
        by_sno[r["sno"]] = r
    csv_snos: set[str] = set()
    problems: list[str] = []
    for row in catalogue:
        sno = _collapse(row["sno"])
        if sno in csv_snos:
            raise BuildError(f"the catalogue CSV lists S.No. {sno} twice")
        csv_snos.add(sno)
        src = by_sno.get(sno)
        if src is None:
            problems.append(f"S.No. {sno} ({row['qp_code']}) is not in A1")
            continue
        for col in COLUMNS:
            if _collapse(row[col]) != src[col]:
                problems.append(f"S.No. {sno} {col}: catalogue {row[col]!r} differs from A1 {src[col]!r}")
    for sno in sorted(set(by_sno) - csv_snos, key=lambda s: (len(s), s)):
        problems.append(f"S.No. {sno} ({by_sno[sno]['qp_code']}) is in A1 but not in the catalogue CSV")
    if problems:
        shown = "; ".join(problems[:5]) + (f"; and {len(problems) - 5} more" if len(problems) > 5 else "")
        raise BuildError(f"the catalogue CSV does not match its source A1: {shown}")
    return len(catalogue)
