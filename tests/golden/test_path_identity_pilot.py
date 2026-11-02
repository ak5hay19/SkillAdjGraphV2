"""P3.6b golden tests: path identity over the four curated pilot qualifications of the REAL curated build (skipped when absent).

Profiles are synthetic ("a person who ..."). Nothing here is a claim about a real person or about eligibility: the tests only
check that identity is stable, unique, independent of display labels and edges, and that it changes no verdict or order.
PROVISIONAL markers carried over from P3.6a: Q-B (``undecided_level_use = COMPARE``) and the hypothetical-relevance rule.
"""

import re

from test_graph_paths_pilot import D, IC, PS, SMO, SSMO, P, _registry, e07_state, limits, paths, reg  # noqa: F401

from skillgraph.eligibility.evaluate import ExternalQualification, PostSchoolCredential, identity_profile_digest
from skillgraph.graph import build_inference_edges, build_static_edges

ID_FORMAT = re.compile(r"^p-[0-9a-f]{12}$")


def test_ids_on_the_real_build_are_well_formed_unique_and_repeatable(reg, limits):
    state = P(age=30, grade=10, creds=[], held=[], ext=())
    first, again = paths(reg, limits, state, max_steps=4), paths(reg, limits, state, max_steps=4)
    assert first
    assert all(ID_FORMAT.fullmatch(p.path_id) for p in first)
    assert len({p.path_id for p in first}) == len(first)
    assert [p.path_id for p in first] == [p.path_id for p in again]


def test_the_same_steps_for_another_person_have_other_ids(reg, limits):
    a = {p.target_codes: p.path_id for p in paths(reg, limits, P(age=30, grade=10, creds=[], held=[], ext=()))}
    b = {p.target_codes: p.path_id for p in paths(reg, limits, P(age=31, grade=10, creds=[], held=[], ext=()))}
    assert a.keys() == b.keys() and all(a[k] != b[k] for k in a)


def test_labels_and_input_order_do_not_change_ids(reg, limits):
    one = P(age=24, grade=10, creds=["OTHER", "UG_DIPLOMA"], held=[SMO, IC],
            ext=(ExternalQualification(ref="ext-a", label="Course A", nsqf_level=4),), decl=[D(SSMO, 3, [SMO, IC]), D(PS, 1, [IC])])
    two = P(age=24, grade=10, creds=["UG_DIPLOMA", "OTHER"], held=[IC, SMO],
            ext=(ExternalQualification(ref="ext-a", label="Another label entirely", nsqf_level=4),),
            decl=[D(PS, 1, [IC]), D(SSMO, 3, [IC, SMO])])
    labelled = one.model_copy(update={"post_school_credentials": (PostSchoolCredential(type="OTHER", label="a note"),
                                                                  PostSchoolCredential(type="UG_DIPLOMA"))})
    assert identity_profile_digest(one) == identity_profile_digest(two) == identity_profile_digest(labelled)
    got = [[(p.path_id, p.verdict) for p in paths(reg, limits, s, max_steps=3)] for s in (one, two, labelled)]
    assert got[0] == got[1] == got[2] and got[0]


def test_building_the_edges_changes_no_id_verdict_or_order_on_the_real_build(reg, limits):
    state = e07_state()
    before = [p.model_dump_json() for p in paths(reg, limits, state, max_steps=3)]
    assert build_static_edges(reg, include_inference=False) and build_inference_edges(reg) is not None
    build_static_edges(reg, include_inference=True)
    assert [p.model_dump_json() for p in paths(reg, limits, state, max_steps=3)] == before
    assert before
