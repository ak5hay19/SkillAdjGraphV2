"""Tests of the forbidden-claim lint (``explain/lint.py``) and of its application to the template source (TASKS P3.8).

The lint is a conservative pattern guard on normalised English text. These tests pin what it catches, what it deliberately
lets through (clear disclaimers), and where it cannot help; they do not claim to detect semantic paraphrase.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from skillgraph.explain import CAVEAT_TEXT
from skillgraph.explain.lint import find_forbidden

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "skillgraph" / "explain" / "templates.py"
ORIGINAL = ("guarantee", "will get", "eligible for job", "in demand", "declining")  # the TASKS P3.8 text


@pytest.mark.parametrize("phrase", ORIGINAL)
def test_the_original_phrases_are_still_forbidden_in_both_modes(phrase):
    sentence = f"This route has {phrase} for you."
    assert find_forbidden(sentence, template=True) != []
    assert find_forbidden(phrase.upper(), template=True) != []  # case


@pytest.mark.parametrize("text", [
    "You will  get a place",              # extra space
    "You will\nget a place",              # line break
    "You will get a place",          # non-breaking space
    "You will get a place",          # thin space
    "will—get",                      # dash
    "will - get",                         # spaced hyphen
    "You WILL Get a place",
    "You will definitely get a place",    # extra word
    "You will then quickly get a place",
    "You'll get a place",                 # contraction
    "You’ll get a place",
    "You will receive a place",
    "You will be offered a seat",
    "You will be admitted",
    "This will gain you a job",
    "You are eligible for a job",
    "You are eligible for the job",
    "You are eligible for jobs",
    "eligible for  job",
    "eligible for a good job",
    "You are eligible for employment",
    "You are employable",
    "Your employability is high",
    "This is an in-demand skill",
    "skills in demand",
    "a high demand sector",
    "growing demand",
    "a declining sector",
    "The sector will decline",
    "The sector declined",
    "It is guaranteed",
    "It guarantees entry",
    "This is a guarantee",
    "Employment is not guaranteed but you will get a job",   # a contrast cancels the earlier negation
    "You will not only get a job, you will receive a bonus",  # negation outside the hit's window of meaning
    "It is not a prediction of anything specific and in all of these cases you will get a job",  # negator more than 6 words back
])
def test_forbidden_claims_are_caught_across_spacing_punctuation_and_extra_words(text):
    assert find_forbidden(text) != [], text


@pytest.mark.parametrize("text", [
    "Employment is not guaranteed.",
    "This does not guarantee a job.",
    "There is no guarantee of placement.",
    "We cannot guarantee anything.",
    "This is not a prediction of admission, employability, placement or earnings.",
    "It does not mean the person is eligible for a job.",
    "You won't get a place from this alone.",
    "Without a guarantee of employment.",
    CAVEAT_TEXT,
    "Holds only if your 3 years of experience are relevant (your declaration; not verified).",
    "Unknown is not a negative result.",
    "The result would then be evaluated again and could still be not met, conditional or unknown.",
    "The requirement allows an equivalent, and no equivalence rule is defined; the named credential is not held.",
    "Official notional training hours: 420 in total. Source page: 3-4.",
])
def test_a_clear_disclaimer_and_the_engines_own_wording_are_not_rejected(text):
    assert find_forbidden(text) == [], text


def test_template_mode_is_stricter_for_the_original_phrases_only():
    assert find_forbidden("Employment is not guaranteed.") == []
    assert find_forbidden("Employment is not guaranteed.", template=True) == ["guarantee"]  # the TASKS criterion, as written
    assert find_forbidden(CAVEAT_TEXT, template=True) == []  # the wider families still allow a disclaimer


def test_the_result_is_sorted_deduplicated_and_deterministic():
    text = "You will get a job. You will receive a job. A declining, declined sector."
    first = find_forbidden(text)
    assert first == sorted(set(first)) and first == find_forbidden(text) and {"promise", "decline"} <= set(first)


def test_wrong_argument_types_are_refused():
    for bad in (None, 3, b"will get"):
        with pytest.raises(TypeError):
            find_forbidden(bad)


def test_known_limits_semantic_paraphrase_is_not_detected():
    # Documented in lint.py: a pattern guard, not a classifier. These pass because no pattern matches them.
    for text in ("You are sure to land a place.", "A place is certain.", "Employers are looking for these skills."):
        assert find_forbidden(text) == []


def test_known_limits_a_negator_in_the_window_can_mask_a_hit():
    # the six-word heuristic: documented, not claimed to be exact
    assert find_forbidden("It is not odd that you will get a job.") == []


def test_known_limits_only_listed_negators_count_so_other_disclaimers_are_flagged():
    # "nothing" is not a listed negator, so this honest disclaimer is (over-cautiously) flagged; rewording avoids it
    assert find_forbidden("Nothing here makes you employable.") == ["employability"]
    assert find_forbidden("Nothing here makes you employable.".replace("Nothing", "No claim")) == []


# ---- the template source --------------------------------------------------------------------------------------------------


def static_strings(tree: ast.AST) -> list[str]:
    """Every string a template can build from literals: each constant, each f-string with its interpolations replaced by a
    space, and each ``+`` chain of such parts (adjacent literals are already joined by the parser)."""

    def text(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else " " for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a, b = text(node.left), text(node.right)
            return None if a is None or b is None else a + b
        return None

    found = []
    for node in ast.walk(tree):
        t = text(node)
        if t is not None and t.strip():
            found.append(t)
    return found


def test_static_strings_sees_constants_fstrings_and_concatenation():
    tree = ast.parse('a = "will " + "get"\nb = f"in {x} demand"\nc = "plain"\nd = ("eligible for " "job")')
    got = static_strings(tree)
    assert "will get" in got and "in   demand" in got and "plain" in got and "eligible for job" in got  # {x} -> one space


def test_the_template_source_contains_no_forbidden_phrase_in_template_mode():
    strings = static_strings(ast.parse(TEMPLATES.read_text(encoding="utf-8")))
    assert sum(len(s) for s in strings) > 3000  # the scan really read the templates, including the guidance table
    assert [(s[:70], find_forbidden(s, template=True)) for s in strings if find_forbidden(s, template=True)] == []


def test_the_template_scan_would_catch_a_planted_phrase(tmp_path):
    p = tmp_path / "t.py"
    p.write_text('A = "This route will " + "get you a job"\nB = f"skills in {x} demand"\nC = "Result is guaranteed"\n', encoding="utf-8")
    hits = {s for s in static_strings(ast.parse(p.read_text(encoding="utf-8"))) if find_forbidden(s, template=True)}
    assert {"This route will get you a job", "skills in   demand", "Result is guaranteed"} <= hits
