"""Judge input preparation over the REAL curated build (skipped when absent). No judge is called and nothing is sent anywhere.

It checks that packets built from the real pilot results are complete, resolve every cited evidence id, carry no contact
detail and no profile field, and that the demo's own deterministic wording raises no precheck signal. It makes no claim about
how any model would judge these texts. PROVISIONAL: Q-B (no level comparison set, so level rules stay UNKNOWN).
"""

import json

import pytest

from skillgraph.api.demo_app import _load_default
from skillgraph.api.demo_explore import HEADLINES, ExploreRequest, _curated, _why, build_profile
from skillgraph.eligibility.evaluate import EngineConfig, evaluate
from skillgraph.judge import build_packet, precheck
from skillgraph.judge.prompt import build_request
from skillgraph.model.eligibility import Verdict

BODIES = (
    {"current_kind": "GARMENT_WORK_NO_QUALIFICATION", "education": "G10", "years_in_job": 2, "age_years": 30},
    {"current_kind": "GARMENT_WORK_NO_QUALIFICATION", "education": "G10", "years_in_job": 1, "age_years": 17},
    {"current_kind": "GARMENT_WORK_NO_QUALIFICATION", "education": "NOT_STATED"},
)


@pytest.fixture(scope="module")
def registry(settings, build_dir):
    reg = _load_default(settings)
    assert reg is not None and reg.build is not None and reg.build.validation == "PASSED"
    return reg


def cases(registry):
    for i, body in enumerate(BODIES):
        profile, _ = build_profile(ExploreRequest(**body), registry)
        for q in _curated(registry):
            res = evaluate(q.eligibility, profile, EngineConfig(), registry)
            text = HEADLINES[res.verdict] + " " + " ".join(_why(res))
            yield f"real-{i}-{q.code.replace('/', '-')}", res, text


def test_packets_build_for_every_pilot_result_and_resolve_all_evidence(registry):
    n = 0
    verdicts = set()
    for case_id, res, text in cases(registry):
        before = res.model_dump(mode="json")
        packet = build_packet(case_id, res, registry, text)
        assert res.model_dump(mode="json") == before            # the engine result is untouched
        assert packet.verdict == res.verdict.value and packet.evidence
        assert all(e.evidence_class and (e.source_title or e.evidence_class != "OFFICIAL") for e in packet.evidence.values())
        assert json.loads(build_request(packet).user)["candidate_text"] == text
        verdicts.add(packet.verdict)
        n += 1
    assert n == 12 and verdicts <= {v.value for v in Verdict}


def json_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from json_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_keys(v)


def test_real_packets_carry_no_profile_field_no_path_field_and_no_contact_detail(registry):
    # JSON KEYS, not substrings: the engine's own condition keys and inputs_used field names legitimately read
    # "declarations[...]". Constructing the packet already ran the contact-detail check on every free-text field.
    for case_id, res, text in cases(registry):
        keys = set(json_keys(build_packet(case_id, res, registry, text).model_dump(mode="json")))
        assert not keys & {"declarations", "held_qualification_codes", "external_qualifications", "post_school_credentials",
                           "age_years", "school_grade_passed", "path_id", "profile_digest", "path_ids"}, case_id


def test_the_demos_own_wording_raises_no_precheck_signal(registry):
    for case_id, res, text in cases(registry):
        assert precheck.scan(text) == (), (case_id, text)


def test_the_demos_own_wording_raises_no_signal_when_the_engine_verdict_is_given(registry):
    # The verdict-consistency and instruction checks must not flag the engine's own honest wording on any of the 12 real results.
    n = 0
    for case_id, res, text in cases(registry):
        assert precheck.scan(text, res.verdict.value) == (), (case_id, res.verdict.value, text)
        n += 1
    assert n == 12


def test_the_p38_templates_raise_no_verdict_or_instruction_signal_on_the_real_results(registry):
    # Not a claim about any model: only that the deterministic templates, which cite engine strings, do not trip the new checks.
    from skillgraph.explain import for_eligibility
    n = 0
    for case_id, res, _ in cases(registry):
        text = "\n".join(i.text for i in for_eligibility(res, registry))
        found = {s.family for s in precheck.scan(text, res.verdict.value)}
        assert not found & {"VERDICT_CERTAINTY", "VERDICT_CONTRADICTION", "REVIEWER_INSTRUCTION"}, (case_id, found)
        n += 1
    assert n == 12
