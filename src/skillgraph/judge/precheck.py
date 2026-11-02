"""A small deterministic phrase scan of the candidate text. No model, no network.

It can only ADD a signal, which raises a case to REVIEW_REQUIRED; it never lowers a judge result and never decides
anything about eligibility. So a lenient or injected judge cannot turn "guaranteed placement" into a PASS.

Signal families:

* Outcome claims (``GUARANTEE``, ``OUTCOME_CLAIM``, ``EQUIVALENCE``, ``EXEMPTION``, ``REDUCED_HOURS``): a phrase list over
  each sentence. A sentence that disclaims a prediction, or says a concept is absent or undefined, is skipped whole.
* Verdict consistency (``VERDICT_CERTAINTY``, ``VERDICT_CONTRADICTION``): only when the caller passes the engine verdict.
  The engine verdict is read, never produced or changed.
  - ``UNKNOWN`` / ``CONDITIONAL``: a sentence that asserts eligibility or that the requirements are met (``VERDICT_CERTAINTY``),
    or that denies eligibility. Both turn an open result into a yes or a no.
  - ``MET``: a sentence that denies eligibility or says the requirements are not met (``VERDICT_CONTRADICTION``).
  - ``NOT_MET``: a sentence that asserts eligibility or that the requirements are met (``VERDICT_CONTRADICTION``).
  The patterns target statements about the person or about the requirements as a whole ("you are eligible", "you meet the
  requirements", "the entry rules are met", "not eligible", "the requirement is not met"). A component-level statement
  such as "the age requirement is met" is deliberately not matched: an UNKNOWN result legitimately says it.
* Reviewer-directed instructions (``REVIEWER_INSTRUCTION``): wording that tells a reviewer or AI what to do ("ignore
  previous instructions", "answer PASS", "note to the reviewer") or forges the judge's reply format. Always on, for every
  verdict, over the whole text (not sentence by sentence, and not subject to any disclaimer skip), after Unicode NFKC
  normalisation, removal of invisible format characters (such as zero-width spaces), case folding and punctuation collapse.

Limits (stated, not hidden): it is a phrase list, so it misses paraphrases, other languages and deliberate obfuscation, and it
cannot read negation reliably. (1) Outcome families: a disclaiming sentence is skipped whole, so a real claim in the same
sentence is skipped too. (2) Verdict families: a sentence containing a hedge word ("if", "cannot", "whether", "may", "unknown",
...) is skipped whole, so "this cannot be decided, but you are eligible" is missed; for the positive patterns a negation word in the same
clause (between commas, colons, dashes, "but") also skips the match, so "you are eligible, and nothing is unknown" is missed; a double negation ("this does not mean you are ineligible") on a MET result is flagged, which only sends it to review.
(3) Only explicit wording is matched: "you can enrol" or "go ahead and apply" is not. A signal is a reason for a human to look, never
a finding that the text is wrong, and a clean scan proves nothing.
"""

from __future__ import annotations

import re
import unicodedata

from skillgraph.judge.schema import PrecheckSignal

_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(rx, re.IGNORECASE)) for name, rx in (
        ("GUARANTEE", r"\bguarantee[sd]?\b|\bwill (?:definitely |certainly )?get\b|\bsure to\b|\bwill definitely\b"),
        ("OUTCOME_CLAIM", r"\beligible for (?:a |the )?jobs?\b|\bin demand\b|\bdeclining\b|\bplacements?\b|\bget (?:a |the )?jobs?\b"
                          r"|\bemployab\w*|\bemployment\b|\bearnings?\b|\bearn(?:s)?\b|\bsalar(?:y|ies)\b|\blabou?r demand\b|\bvacanc\w+"),
        ("EQUIVALENCE", r"\bequivalen(?:t|ce)\b|\bcounts? as\b|\btreated as\b|\bsame as\b"),
        ("EXEMPTION", r"\bexempt\w*|\bwaiv(?:e|ed|er|es)\b|\brecognition of prior learning\b|\bRPL\b"),
        ("REDUCED_HOURS", r"\breduced (?:training )?hours\b|\bfewer (?:training )?hours\b|\bshorter (?:course|training|duration)\b"
                          r"|\bskip(?:ped|s)? (?:the )?(?:module|training|course)\b"),
    ))
# A sentence that disclaims a prediction, or says a concept is absent or undefined ("no equivalence rule is defined", the
# engine's own honest wording for EQUIVALENCE_UNDEFINED), is an uncertainty statement, not a claim. Skipping it also skips a
# real claim made in the same sentence: that blind spot is accepted and pinned by a test; the judge model is the real detector.
_DISCLAIMER = re.compile(r"\bnot an? (?:prediction|guarantee|promise|forecast)\b|\bdoes not (?:predict|guarantee|promise)\b"
                         r"|\bno (?:prediction|guarantee)\b|\bno (?:equivalence|exemption|waiver|reduction)\b"
                         r"|\bnot (?:defined|stated|specified|modelled)\b|\bundefined\b", re.IGNORECASE)
_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n+")
# The verdict checks must not be defeated by a hard line break inside a sentence ("you are\nELIGIBLE"), so they split on sentence
# punctuation and blank lines only.
_VERDICT_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n\s*\n")

# ---- verdict consistency (needs the engine verdict) ----------------------------------------------------------------------------
# Matched on text that is NFKC-normalised, stripped of invisible format characters, case-folded and without apostrophes.
_SUBJ = r"(?:you|(?:the\s+|this\s+)?(?:learner|applicant|candidate|user|person))"
_ADV = r"(?:(?:\w+ly|now|also|already)\s+)?"
_ELIG_POS = re.compile(rf"\b(?:you\s+are|youre|(?:the\s+|this\s+)?(?:learner|applicant|candidate|user|person)\s+is)\s+{_ADV}(?:eligible|qualified)\b"
                       rf"|\b{_SUBJ}\s+{_ADV}(?:qualify|qualifies)\b|\beligibility\s+is\s+(?:confirmed|established)\b")
_MEET_POS = re.compile(rf"\b{_SUBJ}\s+{_ADV}(?:meet|meets|satisfy|satisfies|fulfil|fulfils|fulfill|fulfills)\s+"
                       r"(?:(?:the|all|every|each|these|those|this|documented|entry|stated|listed|modelled)\s+)+"
                       r"(?:requirements?|rules?|criteria|conditions?)\b")
_RULES_MET_POS = re.compile(r"\b(?:(?:the|all|every)\s+)?(?:(?:documented|entry|modelled|stated|listed)\s+)*(?:requirements|rules|criteria)"
                            r"\s+(?:for\s+[^;.]{0,80}?\s)?(?:are|is)\s+(?:(?:all|fully|now)\s+)?(?:met|satisfied|fulfilled)\b"
                            r"|\b(?:documented|entry|modelled)\s+(?:requirement|rule|criterion)\s+is\s+(?:met|satisfied|fulfilled)\b")
_ELIG_NEG = re.compile(rf"\bnot\s+(?:\w+ly\s+)?eligible\b|\bineligible\b|\bnot\s+qualified\b"
                       rf"|\b{_SUBJ}\s+(?:do\s+not|dont|does\s+not|doesnt)\s+(?:meet|satisfy|qualify)\b"
                       rf"|\b{_SUBJ}\s+(?:fail|fails)\s+to\s+meet\b")
_RULES_NOT_MET = re.compile(r"\b(?:requirements?|rules?|criteria|criterion|conditions?)\s+(?:are|is|were|was)\s+not\s+(?:met|satisfied|fulfilled)\b"
                            r"|\bno\s+(?:documented\s+)?entry\s+(?:routes?|rows?|rules?)\s+(?:is|are)\s+met\b")
# A sentence with a hedge is an uncertainty or conditional statement. For the positive patterns a negation also disarms the match.
_HEDGE = re.compile(r"\b(?:if|unless|until|whether|cannot|cant|unable|unknown|undecided|undetermined|unconfirmed|unverified|conditional"
                    r"|conditionally|provided|may|might|could|would|should|once|pending)\b|\bnot\s+yet\b|\bcan\s+not\b"
                    r"|\bnot\s+(?:been\s+)?(?:decided|determined|confirmed|verified|stated|declared|known)\b")
_NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|without|nothing|dont|doesnt|isnt|arent|wasnt|werent|wont|didnt|hasnt|havent)\b")

_CLAUSE = re.compile(r"[,:;\u2014\u2013]|\b(?:but|however|although|though|yet)\b")
# verdict -> (family, positive patterns, negative patterns)
_VERDICT_RULES: dict[str, tuple[str, tuple[re.Pattern[str], ...], tuple[re.Pattern[str], ...]]] = {
    "UNKNOWN": ("VERDICT_CERTAINTY", (_ELIG_POS, _MEET_POS, _RULES_MET_POS), (_ELIG_NEG,)),
    "CONDITIONAL": ("VERDICT_CERTAINTY", (_ELIG_POS, _MEET_POS, _RULES_MET_POS), (_ELIG_NEG,)),
    "MET": ("VERDICT_CONTRADICTION", (), (_ELIG_NEG, _RULES_NOT_MET)),
    "NOT_MET": ("VERDICT_CONTRADICTION", (_ELIG_POS, _MEET_POS), ()),
}

# ---- reviewer-directed instructions (always on) ----------------------------------------------------------------------------------
_FILLER = r"(?:(?:with|as|only|just|simply|exactly|the|word|all|every|each|dimensions?|categories|outcomes?|ratings?|verdicts?|and|on|for|to)\s+){0,6}"
_INJECTION: tuple[re.Pattern[str], ...] = tuple(re.compile(rx) for rx in (
    r"\b(?:ignore|disregard|forget|override)\s+(?:(?:all|any|the|your|my|these|those|every)\s+)*"
    r"(?:previous|prior|above|earlier|preceding|system|reviewer|original|safety)\s+(?:instructions?|prompts?|rules|guidelines|directions|messages?)\b",
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+|everything\s+)?(?:the\s+)?(?:above|preceding)\b",
    rf"\b(?:answer|respond|reply|output|return|mark|rate|label|score|set|say|write|report)\s+{_FILLER}(?:pass|passed)\b",
    r"\b(?:approve|accept|pass)\s+(?:this|the|my)\s+(?:explanation|text|answer|response|candidate)\b",
    r"\b(?:note|message|instructions?)\s+(?:to|for)\s+(?:the\s+)?(?:reviewer|judge|evaluator|grader|llm|ai)\b",
    r"\b(?:dear|attention|hey|hello)\s+(?:the\s+)?(?:reviewer|judge|evaluator|grader|llm)\b",
    r"\b(?:new|updated|revised)\s+instructions\b|\bsystem\s+(?:prompt|message)\b|\bjailbreak\b",
))
_FORGED_REPLY = re.compile(r"""["']\s*(?:dimensions|outcome|findings)\s*["']\s*:""")


_APOSTROPHES = re.compile("['’]")


def _clean(text: str) -> str:
    """NFKC, no invisible format characters (zero-width space and similar), case-folded, no apostrophes, one space per run."""
    t = unicodedata.normalize("NFKC", text)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Cf")
    return " ".join(_APOSTROPHES.sub("", t.casefold()).split())


def _clause(clean: str, start: int, end: int) -> str:
    """The part of the sentence between the delimiters (comma, colon, dash, "but", "however", ...) around ``[start, end)``."""
    lo, hi = 0, len(clean)
    for d in _CLAUSE.finditer(clean):
        if d.end() <= start:
            lo = d.end()
        elif d.start() >= end:
            hi = d.start()
            break
    return clean[lo:hi]


def _verdict_signals(sentence: str, verdict: str) -> list[PrecheckSignal]:
    family, positives, negatives = _VERDICT_RULES[verdict]
    clean = _clean(sentence)
    if _HEDGE.search(clean):
        return []
    hits: list[str] = []
    for rx in positives:
        m = rx.search(clean)
        if m and not _NEGATION.search(_clause(clean, m.start(), m.end())):  # "not a prediction, and you are eligible" is still a claim
            hits.append(m.group())
    for rx in negatives:
        m = rx.search(clean)
        if m:
            hits.append(m.group())
    return [PrecheckSignal(family=family, phrase=hit, sentence=sentence[:400]) for hit in hits[:1]]


def _injection_signals(text: str) -> list[PrecheckSignal]:
    flat = "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")
    out: list[PrecheckSignal] = []
    m = _FORGED_REPLY.search(flat)
    if m:
        out.append(PrecheckSignal(family="REVIEWER_INSTRUCTION", phrase=m.group(), sentence=flat[max(0, m.start() - 60):m.end() + 60][:400]))
    words = " ".join(re.sub(r"[^0-9a-z]+", " ", _clean(text)).split())
    seen: set[str] = set()
    for rx in _INJECTION:
        for m in rx.finditer(words):
            if m.group() not in seen:
                seen.add(m.group())
                out.append(PrecheckSignal(family="REVIEWER_INSTRUCTION", phrase=m.group(),
                                          sentence=words[max(0, m.start() - 60):m.end() + 60][:400]))
    return out


def scan(text: str, verdict: object = None) -> tuple[PrecheckSignal, ...]:
    """Outcome signals, then verdict signals, then reviewer-instruction signals, each in order of appearance; the same family
    and phrase in one sentence is reported once.

    ``verdict`` is the engine verdict of the result the text explains (``"MET"``, ``"NOT_MET"``, ``"UNKNOWN"``,
    ``"CONDITIONAL"``, or the enum); it is optional and read-only. Without it, or with any other value, only the outcome and
    reviewer-instruction families run.
    """
    v = str(getattr(verdict, "value", verdict)) if verdict is not None else None
    out: list[PrecheckSignal] = []
    for sentence in (s.strip() for s in _SENTENCES.split(text)):
        if not sentence or _DISCLAIMER.search(sentence):
            continue
        seen: set[tuple[str, str]] = set()
        for family, rx in _FAMILIES:
            for m in rx.finditer(sentence):
                key = (family, m.group().lower())
                if key not in seen:
                    seen.add(key)
                    out.append(PrecheckSignal(family=family, phrase=m.group(), sentence=sentence[:400]))
    if v in _VERDICT_RULES:  # not subject to the disclaimer skip above: "this is not a prediction, and you are eligible" is flagged
        for sentence in (s.strip() for s in _VERDICT_SENTENCES.split(text)):
            if sentence:
                out.extend(_verdict_signals(sentence, v))
    out.extend(_injection_signals(text))
    return tuple(out)
