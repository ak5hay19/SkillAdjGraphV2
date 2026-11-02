"""Demo journey tests (PROTOTYPE_NOT_API_SPEC): the /demo endpoints over the REAL curated build (skipped when absent).

Expected verdicts are the engine's own for hypothetical profiles ("a person who ...") and follow the printed rules; they are not
claims about real people. PROVISIONAL: Q-B (no level comparison set here, so level rules stay UNKNOWN) and the hypothetical-
relevance rule. These tests do not touch the data build or any config file.
"""

import pytest
from fastapi.testclient import TestClient

from skillgraph.api.demo_app import create_app

IC, SMO, PS, SSMO = "AMH/Q0103", "AMH/Q0301", "AMH/Q2101", "AMH/Q2301"
CLASS = {"MET": 0, "CONDITIONAL": 1, "UNKNOWN": 2, "NOT_MET": 3}


@pytest.fixture(scope="module")
def client(settings, build_dir):
    return TestClient(create_app(settings))


def explore(client, **body):
    body.setdefault("current_kind", "GARMENT_WORK_NO_QUALIFICATION")
    return client.post("/demo/explore", json=body)


def test_status_serving_and_module_a_deferred(client):
    s = client.get("/demo/status").json()
    assert s["serving"] is True and s["validation"] == "PASSED" and s["module_a"] == "NO_GO"


def test_qualifications_lists_four_pilots_with_hours(client):
    r = client.get("/demo/qualifications")
    assert r.status_code == 200
    items = {i["code"]: i for i in r.json()["curated"]}
    assert set(items) == {IC, SMO, PS, SSMO}
    assert items[SMO]["hours"]["total"] == 300.0 and items[PS]["hours"]["total"] == 570.0


def test_index_serves_the_frontend(client):
    r = client.get("/")
    assert r.status_code == 200 and "SkillPath India" in r.text


def test_helper_profile_gives_three_ordered_cards_and_one_more_option(client):
    d = explore(client, education="G10", years_in_job=2, age_years=30).json()
    assert [(c["code"], c["verdict"]) for c in d["cards"]] == [(SMO, "MET"), (IC, "CONDITIONAL"), (SSMO, "UNKNOWN")]
    assert [c["code"] for c in d["more_options"]] == [PS] and d["not_open"] == []
    assert d["cards"][0]["official_total_hours"] == 300.0


def test_ordering_is_verdict_class_then_hours(client):
    for body in ({"education": "G10", "years_in_job": 3, "age_years": 30},
                 {"current_kind": "HOLDS_QUALIFICATION", "held_code": SMO, "education": "G12", "years_in_job": 6,
                  "age_years": 35, "nsqf_level_match": "at_least"}):
        d = explore(client, **body).json()
        every = d["cards"] + d["more_options"] + d["not_open"]
        keys = [(CLASS[v["verdict"]], v["official_total_hours"]) for v in every]
        assert keys == sorted(keys)


def test_held_qualification_is_not_offered_again(client):
    d = explore(client, current_kind="HOLDS_QUALIFICATION", held_code=SMO, education="G10", years_in_job=3, age_years=30).json()
    shown = [v["code"] for v in d["cards"] + d["more_options"] + d["not_open"]]
    assert SMO not in shown and d["held"] == [SMO]


def test_under_age_profile_has_no_open_option(client):
    d = explore(client, education="G10", years_in_job=1, age_years=17).json()
    assert d["cards"] == [] and len(d["not_open"]) == 4
    assert all(v["verdict"] == "NOT_MET" for v in d["not_open"])


def test_without_age_nothing_is_met(client):
    d = explore(client, education="G10", years_in_job=2).json()
    assert all(v["verdict"] != "MET" for v in d["cards"] + d["more_options"])


def test_every_card_carries_evidence_and_unverified_enrolment(client):
    d = explore(client, education="G10", years_in_job=2, age_years=30).json()
    for v in d["cards"]:
        assert v["enrolment"]["status"] == "NOT_VERIFIED" and v["deadline"]["status"] == "NOT_VERIFIED"
        assert v["evidence"] and v["eligibility"]["rows"] and v["facts"]["hours"]["total"] == v["official_total_hours"]
        assert any(e["source_title"] for e in v["evidence"].values())


def test_envelope_is_marked_prototype_and_lists_notices(client):
    d = explore(client, education="G10", age_years=30).json()
    assert d["contract"] == "PROTOTYPE_NOT_API_SPEC" and d["validation"] == "PASSED"
    assert {"NOT_A_PREDICTION", "MODULE_A_NO_GO", "ENROLMENT_AND_DEADLINES_NOT_VERIFIED"} <= {n["code"] for n in d["notices"]}


@pytest.mark.parametrize("body, status", [
    ({"current_kind": "HOLDS_QUALIFICATION"}, 422),                                   # held code missing
    ({"current_kind": "HOLDS_QUALIFICATION", "held_code": "AMH/Q9999"}, 422),         # not in the registry
    ({"current_kind": "OTHER_WORK", "age_years": 5}, 422),                            # out of range
    ({"current_kind": "OTHER_WORK", "years_in_job": -1}, 422),
    ({"current_kind": "OTHER_WORK", "education": "PHD"}, 422),
    ({"current_kind": "OTHER_WORK", "unexpected": 1}, 422),                           # extra fields forbidden
    ({"current_kind": "OTHER_WORK", "nsqf_level_match": "whatever"}, 422),
])
def test_invalid_requests_are_rejected(client, body, status):
    assert client.post("/demo/explore", json=body).status_code == status


def test_catalogue_only_qualification_cannot_be_held(client, settings):
    from skillgraph.model.qualification import Coverage
    reg = client.app  # noqa: F841 (keeps the app alive)
    from skillgraph.api.demo_app import _load_default
    registry = _load_default(settings)
    cat = next(q.code for q in registry.qualifications() if q.coverage is Coverage.CATALOGUE_ONLY)
    r = explore(client, current_kind="HOLDS_QUALIFICATION", held_code=cat)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "TARGET_NOT_EVALUABLE"


def test_no_build_answers_503_never_a_result(settings):
    c = TestClient(create_app(settings, loader=lambda _s: None))
    r = c.post("/demo/explore", json={"current_kind": "OTHER_WORK"})
    assert r.status_code == 503 and r.json()["error"] == "DATA_NOT_BUILT"
    assert c.get("/demo/status").json()["serving"] is False
