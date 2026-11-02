"""A conservative, deterministic text lint for explanation wording (TASKS P3.8: forbidden claim families).

``find_forbidden(text)`` returns the sorted labels of the forbidden claim families found in ``text``. It is a *guard rail*, not
a classifier: it matches patterns on normalised English text and does not understand meaning.

Normalisation (so that spacing and punctuation cannot hide a phrase): Unicode NFKC, case-folding, ``'ll`` read as ``will`` and
``n't`` as ``not``, every other apostrophe dropped, and every run of anything that is not a letter or a digit (spaces, line
breaks, non-breaking spaces, hyphens, dashes, punctuation) collapsed to one space.

Families:

* The five phrases of the TASKS criterion, matched on word boundaries after normalisation: ``guarantee`` (also guaranteed,
  guarantees), ``will get``, ``eligible for job`` (also jobs), ``in demand`` (also in-demand), ``declining``. With
  ``template=True`` they are forbidden outright, as the criterion says for templates, disclaimers included.
* Wider families, always reported unless negated: promises (``will``/``shall``/``'ll`` followed within two words by get,
  receive, gain, obtain, secure, or ``be`` offered, admitted, hired, placed, selected, employed, accepted, eligible), job
  eligibility (``eligible for [a|the] [word] job|jobs|employment|placement``), demand (``in/high/rising/growing/strong/great
  demand``), decline (``decline``, ``declines``, ``declined``, ``declining``), employability (``employable``,
  ``employability``) and ``guarantee`` itself.

Negation (disclaimers): outside ``template=True``, and for the wider families inside it, a hit is ignored when one of
``not no never cannot without nor neither none`` stands within the six words before it in the same sentence and no contrast
word (``but however yet although though while``) comes between. So "employment is not guaranteed" and "not a prediction of
admission, employability" pass, while "employment is not guaranteed but you will get a job" does not.

Limits, stated plainly: English only; no paraphrase or semantic detection ("you are sure to land a place" is not caught);
negation is a six-word heuristic, so an unusual construction can be wrongly passed or wrongly flagged; spelling variants
outside the patterns are not matched; text is not checked for being *true*. A clean result means only that none of these
patterns matched.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["find_forbidden"]

_ORIGINAL = {
    "guarantee": re.compile(r"\bguarantee"),
    "will get": re.compile(r"\bwill get\b"),
    "eligible for job": re.compile(r"\beligible for jobs?\b"),
    "in demand": re.compile(r"\bin demand\b"),
    "declining": re.compile(r"\bdeclining\b"),
}
_FAMILIES = {
    "guarantee": re.compile(r"\bguarantee\w*"),
    "promise": re.compile(
        r"\b(?:will|shall)\s+(?:\w+\s+){0,2}?(?:gets?|receive|gain|obtain|secure|"
        r"be\s+(?:offered|admitted|hired|placed|selected|employed|accepted|eligible))\b"),
    "job eligibility": re.compile(
        r"\beligible\s+for\s+(?:(?:an?|the|any|that|this|every)\s+)?(?:\w+\s+)?(?:jobs?|employment|placements?)\b"),
    "demand": re.compile(r"\b(?:in|high|rising|growing|strong|great)\s+demand\b"),
    "decline": re.compile(r"\bdeclin(?:e|es|ed|ing)\b"),
    "employability": re.compile(r"\bemployab(?:le|ility)\b"),
}
_SENTENCE = re.compile(r"[.!?;:]+")  # a line break is not a sentence break: wrapped text must not hide a phrase
_NEGATORS = frozenset({"not", "no", "never", "cannot", "without", "nor", "neither", "none"})
_CONTRAST = frozenset({"but", "however", "yet", "although", "though", "while"})
_WINDOW = 6


def _normalise(text: str) -> str:
    s = unicodedata.normalize("NFKC", text).casefold()
    s = re.sub("['\N{RIGHT SINGLE QUOTATION MARK}]ll\\b", " will", s)  # you'll -> you will (straight or curly apostrophe)
    s = re.sub("n['\N{RIGHT SINGLE QUOTATION MARK}]t\\b", " not", s)  # don't -> do not
    s = re.sub("['\N{RIGHT SINGLE QUOTATION MARK}]", "", s)
    return " ".join(re.sub(r"[\W_]+", " ", s).split())


def _negated(sentence: str, start: int) -> bool:
    for token in reversed(sentence[:start].split()[-_WINDOW:]):
        if token in _CONTRAST:
            return False
        if token in _NEGATORS:
            return True
    return False


def find_forbidden(text: str, *, template: bool = False) -> list[str]:
    """Sorted, de-duplicated labels of the forbidden claim families found in ``text`` (empty list: none matched).

    ``template=True`` applies the five original phrases without any negation allowance (the TASKS criterion for template
    wording); the default treats a clearly negated mention as a disclaimer. See the module notes for the limits."""
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    found: set[str] = set()
    if template:
        whole = _normalise(text)
        found |= {label for label, rx in _ORIGINAL.items() if rx.search(whole)}
    for part in _SENTENCE.split(unicodedata.normalize("NFKC", text)):
        sentence = _normalise(part)
        if not sentence:
            continue
        for label, rx in _FAMILIES.items():
            if any(not _negated(sentence, m.start()) for m in rx.finditer(sentence)):
                found.add(label)
    return sorted(found)
