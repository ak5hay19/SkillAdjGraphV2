"""P3.6b path identity (API_SPEC §4 amendment A-6; TASKS P3.6 A-6 required tests (a)-(i)). Synthetic fixtures only.

Expected values come from the documented rule, written out independently of the code: a literal canonical-JSON string hashed
with ``hashlib`` (never produced by the code under test). Nothing here decides or changes a verdict: the tests that touch
enumeration compare against an enumeration that ignores identity.
"""

import hashlib
import inspect
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_graph_paths import DIGEST, LIMITS, code, digits, enum, profile, seqs, world

import skillgraph.graph.paths as paths_module
from skillgraph.eligibility.evaluate import (
    EngineConfig,
    ExternalQualification,
    PostSchoolCredential,
    ProfileState,
    TargetDeclaration,
    identity_profile_digest,
)
from skillgraph.graph import (
    GraphError,
    RawPath,
    Scenario,
    build_inference_edges,
    build_static_edges,
    enumerate_paths,
)
from skillgraph.logging_setup import profile_digest as logging_profile_digest
from skillgraph.model.eligibility import Verdict

SRC = Path(__file__).resolve().parents[2] / "src"
ID_FORMAT = re.compile(r"^p-[0-9a-f]{12}$")
DIGEST_FORMAT = re.compile(r"^sha256:[0-9a-f]{64}$")
OTHER_DIGEST = "sha256:" + "1" * 64


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def D(code_, years=None, rel=None) -> TargetDeclaration:
    return TargetDeclaration(target_code=code_, relevant_experience_years=years, relevant_prior_qualifications=rel)


def P(**kw) -> ProfileState:
    base = {"age_years": 30, "school_grade_passed": 10, "post_school_credentials": (), "held_qualification_codes": (),
            "external_qualifications": (), "declarations": ()}
    return ProfileState(**{**base, **kw})


def cred(t: str, label: str | None = None) -> PostSchoolCredential:
    return PostSchoolCredential(type=t, label=label)


def ext(ref: str, level: float = 4, label: str = "Some course") -> ExternalQualification:
    return ExternalQualification(ref=ref, label=label, nsqf_level=level)


# ---- (a) golden vectors computed independently ----------------------------------------------------------------------------


def test_golden_vector_of_the_profile_digest():
    state = ProfileState(age_years=30, school_grade_passed=10,
                         post_school_credentials=(cred("UG_DIPLOMA", "my diploma"), cred("OTHER")),
                         held_qualification_codes=("AMH/Q0301",), external_qualifications=None,
                         declarations=(D("AMH/Q2301", 3, ("AMH/Q0301",)),))
    literal = ('{"age_years":30,"declarations":[{"relevant_experience_years":3.0,"relevant_prior_qualifications":'
               '["AMH/Q0301"],"target_code":"AMH/Q2301"}],"external_qualifications":null,"held_qualification_codes":'
               '["AMH/Q0301"],"post_school_credentials":["OTHER","UG_DIPLOMA"],"school_grade_passed":10}')
    assert identity_profile_digest(state) == "sha256:" + sha(literal)
    # pinned: computed once with plain hashlib from the literal above; a change here is a change of every path ID
    assert identity_profile_digest(state) == "sha256:89bc429089c85d2ab560b3dbb0ae4ee08ecc4df3b5290ecb243d47b0cd70aa02"


def test_golden_vector_of_a_path_id():
    literal = ('{"config":{"nsqf_level_match":"exact"},"profile_digest":"sha256:' + "0" * 64 + '","scenario":'
               '{"assume_intermediate_relevance":false,"assumed_experience_gain_years_per_step":0.0,'
               '"incremental_hours_policy":"NONE"},"steps":["TEST/Q9001","TEST/Q9002"]}')
    expected = "p-" + sha(literal)[:12]
    assert expected == "p-c9bf1a8e330f"  # pinned: computed once with plain hashlib from the literal above
    got = paths_module._path_id(EngineConfig(nsqf_level_match="exact"), Scenario(), DIGEST, (code(1), code(2)))
    assert got == expected
    by_enumeration = {p.target_codes: p.path_id for p in enum(world({1: "M", 2: "M"}), max_steps=2, match="exact")}
    assert by_enumeration[(code(1), code(2))] == expected


def test_golden_vector_with_an_unset_config_serialises_null():
    literal = ('{"config":{"nsqf_level_match":null},"profile_digest":"' + OTHER_DIGEST + '","scenario":'
               '{"assume_intermediate_relevance":false,"assumed_experience_gain_years_per_step":0.0,'
               '"incremental_hours_policy":"NONE"},"steps":["TEST/Q9003"]}')
    assert paths_module._path_id(EngineConfig(), Scenario(), OTHER_DIGEST, (code(3),)) == "p-" + sha(literal)[:12]


# ---- (b) format --------------------------------------------------------------------------------------------------------------


def test_formats():
    reg = world({1: "M", 2: "M", 3: "C", 4: "U"})
    got = enum(reg, max_steps=3)
    assert got and all(ID_FORMAT.fullmatch(p.path_id) for p in got)
    assert DIGEST_FORMAT.fullmatch(identity_profile_digest(P()))
    assert RawPath.model_fields["path_id"].annotation  # the field is declared and required
    assert RawPath.model_fields["path_id"].is_required()


@pytest.mark.parametrize("bad", ["", "p-", "p-ABCDEF012345", "p-0123456789a", "p-0123456789abc", "P-0123456789ab",
                                 "x-0123456789ab", "p-0123456789ab\n", " p-0123456789ab", "p-0123456789ag"])
def test_a_malformed_path_id_is_refused_by_the_model(bad):
    p = enum(world({1: "M"}), max_steps=1)[0]
    with pytest.raises(ValidationError):
        RawPath(path_id=bad, steps=p.steps, verdict=p.verdict, official_hours_total=p.official_hours_total)


# ---- (c) identical across runs and processes ---------------------------------------------------------------------------------


def test_repeated_runs_and_registry_order_do_not_change_ids():
    kinds = {1: "M", 2: "C", 3: "U", 4: "M"}
    first = enum(world(kinds), max_steps=3)
    again = enum(world(kinds), max_steps=3)
    shuffled = enum(world(kinds, order=[3, 1, 4, 2]), max_steps=3)
    assert [p.path_id for p in first] == [p.path_id for p in again] == [p.path_id for p in shuffled]
    assert first == again == shuffled


def test_ids_are_unique_within_a_result():
    got = enum(world({i: "M" for i in range(1, 6)}), max_steps=3)
    assert len(got) == 5 + 5 * 4 + 5 * 4 * 3
    assert len({p.path_id for p in got}) == len(got)


_CHILD = """
import json
from skillgraph.eligibility.evaluate import EngineConfig, PostSchoolCredential, ProfileState, TargetDeclaration, identity_profile_digest
from skillgraph.graph.paths import Scenario, _path_id
s = ProfileState(age_years=30, school_grade_passed=10,
                 post_school_credentials=(PostSchoolCredential(type="OTHER"), PostSchoolCredential(type="UG_DIPLOMA")),
                 held_qualification_codes=("AMH/Q0301", "AMH/Q0103"), external_qualifications=(),
                 declarations=(TargetDeclaration(target_code="AMH/Q2301", relevant_experience_years=3,
                                                 relevant_prior_qualifications=("AMH/Q0301", "AMH/Q0103")),))
d = identity_profile_digest(s)
print(json.dumps([d, _path_id(EngineConfig(nsqf_level_match="at_least"), Scenario(), d, ("AMH/Q2101", "AMH/Q2301"))]))
"""


def _in_child(hashseed: str) -> list[str]:
    env = {**os.environ, "PYTHONHASHSEED": hashseed, "PYTHONPATH": str(SRC)}
    out = subprocess.run([sys.executable, "-B", "-c", _CHILD], env=env, capture_output=True, text=True, check=True)
    import json
    return json.loads(out.stdout)


def test_identity_is_the_same_in_other_processes_and_under_any_hash_seed():
    results = {seed: _in_child(seed) for seed in ("0", "1", "4242", "random")}
    assert len({tuple(v) for v in results.values()}) == 1
    digest_, pid = results["0"]
    assert DIGEST_FORMAT.fullmatch(digest_) and ID_FORMAT.fullmatch(pid)
    s = P(post_school_credentials=(cred("OTHER"), cred("UG_DIPLOMA")), held_qualification_codes=("AMH/Q0301", "AMH/Q0103"),
          declarations=(D("AMH/Q2301", 3, ("AMH/Q0301", "AMH/Q0103")),))
    assert identity_profile_digest(s) == digest_  # and in this process


# ---- (d) a different identity for a different step order, step set, config, scenario or profile digest -------------------------


def test_a_different_step_order_or_step_set_gives_a_different_id():
    ids = {p.target_codes: p.path_id for p in enum(world({1: "M", 2: "M", 3: "M"}), max_steps=3)}
    assert len(ids) == 15 and len(set(ids.values())) == 15
    assert ids[(code(1), code(2))] != ids[(code(2), code(1))]  # order
    assert ids[(code(1), code(2))] != ids[(code(1), code(2), code(3))]  # prefix versus extension
    assert ids[(code(1), code(2))] != ids[(code(1), code(3))]  # set


def test_a_different_config_gives_a_different_id_for_the_same_steps():
    reg = world({1: "M", 2: "M"})
    by = {m: {p.target_codes: p.path_id for p in enum(reg, max_steps=2, match=m)} for m in ("exact", "at_least", None)}
    assert set(by["exact"]) == set(by["at_least"]) == set(by[None])
    for steps in by["exact"]:
        assert len({by["exact"][steps], by["at_least"][steps], by[None][steps]}) == 3


def test_a_different_scenario_gives_a_different_id():
    cfg, steps = EngineConfig(nsqf_level_match="exact"), (code(1),)
    base = paths_module._path_id(cfg, Scenario(), DIGEST, steps)
    others = [Scenario(assume_intermediate_relevance=True), Scenario(assumed_experience_gain_years_per_step=1),
              Scenario(incremental_hours_policy="EXCLUDE_SHARED_NOS_CODE"),
              Scenario(incremental_hours_policy="EXCLUDE_SHARED_NOS_CODE_AND_VERSION")]
    got = [paths_module._path_id(cfg, s, DIGEST, steps) for s in others]
    assert len({base, *got}) == 5
    # (non-default scenarios are still refused by enumeration itself; this only pins the identity rule)


def test_a_different_profile_digest_gives_a_different_id_and_nothing_else_changes():
    reg = world({1: "M", 2: "C", 3: "U"})
    a = enum(reg, max_steps=3, profile_digest=DIGEST)
    b = enum(reg, max_steps=3, profile_digest=OTHER_DIGEST)
    assert seqs(a) == seqs(b) and [p.verdict for p in a] == [p.verdict for p in b]
    assert [p.steps for p in a] == [p.steps for p in b]  # eligibility results, byte for byte
    assert {p.path_id for p in a}.isdisjoint({p.path_id for p in b})


# ---- (e) excluded settings: sort_by, limit, include_inference, labels, build, max_steps, target --------------------------------


def test_the_identity_has_no_ranking_or_display_parameter():
    params = set(inspect.signature(enumerate_paths).parameters)
    assert not params & {"sort_by", "limit", "include_inference", "build_id"}
    assert set(inspect.signature(paths_module._path_id).parameters) == {"config", "scenario", "profile_digest", "step_codes"}


def test_max_steps_and_target_code_do_not_change_an_id():
    reg = world({1: "M", 2: "M", 3: "M"})
    full = {p.target_codes: p.path_id for p in enum(reg, max_steps=3)}
    two = {p.target_codes: p.path_id for p in enum(reg, max_steps=2)}
    assert all(full[k] == v for k, v in two.items())
    for t in (1, 2, 3):
        for p in enum(reg, max_steps=3, target=code(t)):
            assert p.path_id == full[p.target_codes]


def test_the_limits_do_not_change_an_id():
    reg = world({1: "M", 2: "M"})
    a = enum(reg, max_steps=2)
    b = enum(reg, max_steps=2, max_expansions=4, max_steps_limit=2)
    assert [p.path_id for p in a] == [p.path_id for p in b]


def test_the_same_id_can_carry_another_verdict_under_another_build():
    a = {p.path_id: p.verdict for p in enum(world({1: "M", 2: "M"}), max_steps=2)}
    b = {p.path_id: p.verdict for p in enum(world({1: "M", 2: "U"}), max_steps=2)}
    assert a.keys() == b.keys() and a != b  # an ID identifies the query, not the result


def test_display_labels_do_not_change_the_profile_digest_or_any_id():
    plain = P(post_school_credentials=(cred("OTHER"),), external_qualifications=(ext("ext-a", 4, "A"),))
    relabelled = P(post_school_credentials=(cred("OTHER", "Some other certificate"),),
                   external_qualifications=(ext("ext-a", 4, "A completely different label ünïcode"),))
    assert plain != relabelled  # the models do differ ...
    assert identity_profile_digest(plain) == identity_profile_digest(relabelled)  # ... the identity does not
    reg = world({1: "M", 2: "M"})
    a = enumerate_paths(plain, reg, EngineConfig(), Scenario(), 2, None, max_expansions=100, max_steps_limit=4,
                        profile_digest=identity_profile_digest(plain))
    b = enumerate_paths(relabelled, reg, EngineConfig(), Scenario(), 2, None, max_expansions=100, max_steps_limit=4,
                        profile_digest=identity_profile_digest(relabelled))
    assert [p.path_id for p in a] == [p.path_id for p in b]


# ---- (f) the profile digest ------------------------------------------------------------------------------------------------------


def test_it_is_not_the_logging_digest():
    assert identity_profile_digest is not logging_profile_digest
    # the logging digest hashes the raw mapping, so it follows list order and labels; the identity digest does not
    a = P(held_qualification_codes=("AMH/Q0301", "AMH/Q0103"), post_school_credentials=(cred("OTHER", "x"),))
    b = P(held_qualification_codes=("AMH/Q0103", "AMH/Q0301"), post_school_credentials=(cred("OTHER", "y"),))
    assert identity_profile_digest(a) == identity_profile_digest(b)
    assert logging_profile_digest(a.model_dump(mode="json")) != logging_profile_digest(b.model_dump(mode="json"))
    # the logging digest keeps its documented behaviour: sorted compact JSON of the raw mapping, key order irrelevant
    assert logging_profile_digest({"b": 1, "a": 2}) == logging_profile_digest({"a": 2, "b": 1})
    assert logging_profile_digest({"a": 2}) == "sha256:" + sha('{"a":2}')


def test_set_like_fields_are_normalised():
    a = P(post_school_credentials=(cred("OTHER"), cred("UG_DIPLOMA")), held_qualification_codes=("AMH/Q0301", "AMH/Q0103"),
          external_qualifications=(ext("ext-a", 4), ext("ext-b", 5)),
          declarations=(D("AMH/Q2301", 3, ("AMH/Q0301", "ext-a", "ext-b")), D("AMH/Q2101", 1, ("AMH/Q0103",))))
    expected = identity_profile_digest(a)
    for creds in itertools.permutations((cred("OTHER"), cred("UG_DIPLOMA"))):
        for codes in itertools.permutations(("AMH/Q0301", "AMH/Q0103")):
            for exts in itertools.permutations((ext("ext-a", 4), ext("ext-b", 5))):
                for rel in itertools.permutations(("AMH/Q0301", "ext-a", "ext-b")):
                    for decls in itertools.permutations((("AMH/Q2301", 3, rel), ("AMH/Q2101", 1, ("AMH/Q0103",)))):
                        b = P(post_school_credentials=creds, held_qualification_codes=codes, external_qualifications=exts,
                              declarations=tuple(D(*d) for d in decls))
                        assert identity_profile_digest(b) == expected


def test_none_and_empty_stay_distinct_for_every_nullable_field():
    held = {"held_qualification_codes": ("AMH/Q0301",), "external_qualifications": (ext("ext-a"),)}
    pairs = [
        ("post_school_credentials", None, ()),
        ("held_qualification_codes", None, ()),
        ("external_qualifications", None, ()),
        ("age_years", None, 30),
        ("school_grade_passed", None, 0),
    ]
    for name, absent, present in pairs:
        assert identity_profile_digest(P(**{name: absent})) != identity_profile_digest(P(**{name: present})), name
    # per-declaration nullable fields
    base = P(**held)

    def with_decl(**kw):
        return P(**held, declarations=(D("AMH/Q2301", **kw),))

    assert identity_profile_digest(with_decl(rel=None)) != identity_profile_digest(with_decl(rel=()))
    assert identity_profile_digest(with_decl(years=None)) != identity_profile_digest(with_decl(years=0))
    assert identity_profile_digest(base) != identity_profile_digest(with_decl())  # a declaration of nothing is a declaration


def test_a_duplicate_credential_changes_the_digest_but_order_does_not():
    one = P(post_school_credentials=(cred("UG_CERTIFICATE"),))
    two = P(post_school_credentials=(cred("UG_CERTIFICATE"), cred("UG_CERTIFICATE")))
    assert identity_profile_digest(one) != identity_profile_digest(two)
    assert identity_profile_digest(P(post_school_credentials=(cred("UG_CERTIFICATE"), cred("OTHER"), cred("UG_CERTIFICATE")))) \
        == identity_profile_digest(P(post_school_credentials=(cred("OTHER"), cred("UG_CERTIFICATE"), cred("UG_CERTIFICATE"))))


def test_numbers_are_canonical():
    assert identity_profile_digest(P(held_qualification_codes=("AMH/Q0301",), declarations=(D("AMH/Q2301", 3),))) \
        == identity_profile_digest(P(held_qualification_codes=("AMH/Q0301",), declarations=(D("AMH/Q2301", 3.0),)))
    assert identity_profile_digest(P(external_qualifications=(ext("ext-a", 4),))) \
        == identity_profile_digest(P(external_qualifications=(ext("ext-a", 4.0),)))


@pytest.mark.parametrize("change", [
    {"age_years": 31}, {"school_grade_passed": 9}, {"post_school_credentials": (PostSchoolCredential(type="OTHER"),)},
    {"held_qualification_codes": ("AMH/Q0301",)}, {"external_qualifications": (ext("ext-a", 4),)},
    {"declarations": (D("AMH/Q2301", 1),)},
], ids=["age", "grade", "credential", "held code", "external", "declaration"])
def test_any_engine_relevant_value_changes_the_digest(change):
    assert identity_profile_digest(P(**change)) != identity_profile_digest(P())


def test_every_leaf_of_a_rich_profile_is_part_of_the_identity():
    def build(age=30, grade=10, ctype="OTHER", code_="AMH/Q0301", ref="ext-a", level=4, target="AMH/Q2301", years=3,
              rel=("AMH/Q0301",)):
        return P(age_years=age, school_grade_passed=grade, post_school_credentials=(cred(ctype),),
                 held_qualification_codes=(code_,), external_qualifications=(ext(ref, level),),
                 declarations=(D(target, years, rel),))

    base = identity_profile_digest(build())
    variants = [build(age=31), build(grade=11), build(ctype="UG_DIPLOMA"), build(code_="AMH/Q0103", rel=("AMH/Q0103",)),
                build(ref="ext-b"), build(level=5), build(target="AMH/Q2101"), build(years=4), build(rel=("ext-a",)),
                build(rel=())]
    assert len({base, *(identity_profile_digest(v) for v in variants)}) == len(variants) + 1


def test_the_digest_requires_a_profile_state():
    for bad in (None, {}, P().model_dump(), "x"):
        with pytest.raises(TypeError):
            identity_profile_digest(bad)  # type: ignore[arg-type]


def test_the_digest_does_not_touch_its_input():
    state = P(post_school_credentials=(cred("OTHER"), cred("OTHER")), held_qualification_codes=("AMH/Q0301", "AMH/Q0103"))
    before = state.model_dump_json()
    identity_profile_digest(state)
    assert state.model_dump_json() == before and state.held_qualification_codes == ("AMH/Q0301", "AMH/Q0103")


# ---- (g) the supplied digest is validated before anything is enumerated --------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, 0, b"sha256:" + b"0" * 64, ["sha256:" + "0" * 64]])
def test_a_non_string_digest_is_a_type_error(bad, spy):
    with pytest.raises(TypeError, match="profile_digest"):
        enum(world({1: "M"}), max_steps=1, profile_digest=bad)
    assert spy == []


@pytest.mark.parametrize("bad", ["", "sha256:", "0" * 64, "sha256:" + "0" * 63, "sha256:" + "0" * 65, "sha256:" + "A" * 64,
                                 "sha256:" + "g" * 64, "SHA256:" + "0" * 64, "sha1:" + "0" * 64, "sha256:" + "0" * 64 + "\n",
                                 " sha256:" + "0" * 64, "sha256: " + "0" * 64])
def test_a_malformed_digest_is_a_value_error(bad, spy):
    with pytest.raises(ValueError, match="profile_digest"):
        enum(world({1: "M"}), max_steps=1, profile_digest=bad)
    assert spy == []


def test_the_digest_cannot_be_omitted_or_positional():
    args = (profile(), world({1: "M"}), EngineConfig(), Scenario(), 1, None)
    with pytest.raises(TypeError):
        enumerate_paths(*args, max_expansions=10, max_steps_limit=4)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        enumerate_paths(*args, 10, 4, DIGEST)  # type: ignore[call-arg]


@pytest.fixture
def spy(monkeypatch):
    calls = []
    real = paths_module.evaluate

    def wrapped(*a, **kw):
        calls.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(paths_module, "evaluate", wrapped)
    return calls


# ---- (h) duplicate IDs -------------------------------------------------------------------------------------------------------------


def test_duplicate_ids_in_one_result_raise_graph_error(monkeypatch):
    monkeypatch.setattr(paths_module, "_path_id", lambda *a, **k: "p-000000000000")
    with pytest.raises(GraphError, match="duplicate path_id p-000000000000"):
        enum(world({1: "M", 2: "M"}), max_steps=2)


def test_a_single_path_cannot_collide_with_itself(monkeypatch):
    monkeypatch.setattr(paths_module, "_path_id", lambda *a, **k: "p-000000000000")
    assert [p.path_id for p in enum(world({1: "M"}), max_steps=1)] == ["p-000000000000"]


def test_the_check_is_exposed_as_the_documented_error_type():
    assert issubclass(GraphError, Exception) and not issubclass(GraphError, (TypeError, ValueError))
    with pytest.raises(GraphError):
        paths_module._require_unique_ids(enum(world({1: "M"}), max_steps=1) * 2)


# ---- (i) inference and static edges change no ID, verdict or order ---------------------------------------------------------------------


def test_building_the_edges_changes_no_id_verdict_or_order():
    reg = world({1: "M", 2: "C", 3: "U", 4: "M"})
    before = [p.model_dump_json() for p in enum(reg, max_steps=3)]
    static = build_static_edges(reg, include_inference=False)
    inferred = build_inference_edges(reg)
    with_inference = build_static_edges(reg, include_inference=True)
    assert static is not None and inferred is not None and with_inference is not None
    after = [p.model_dump_json() for p in enum(reg, max_steps=3)]
    assert after == before


# ---- caller contract (TASKS P3.6 O-9, option (a)): a static check, no change to the function contract ------------------------------------


def _enumerate_paths_call_violations(source: str, filename: str = "<src>") -> tuple[int, list[str]]:
    """Parse ``source`` and check every use of ``enumerate_paths``: it must be a direct call whose ``profile_digest`` keyword is
    ``identity_profile_digest(X)`` with ``X`` the very expression passed as the profile (first positional or ``state=``).
    Returns ``(number of calls found, violations)``. Anything it cannot verify (``**kwargs``, ``*args`` in front, an alias or a
    reference that is not a direct call, a digest function that is not the imported ``identity_profile_digest``) is a violation."""
    import ast
    tree = ast.parse(source)
    names = {"enumerate_paths"}  # local names bound to the function, including ``import ... as``
    digest_names = {"identity_profile_digest"}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == "enumerate_paths":
                    names.add(a.asname or a.name)
                if a.name == "identity_profile_digest":
                    digest_names.add(a.asname or a.name)

    def is_target(f: ast.expr) -> bool:
        return (isinstance(f, ast.Name) and f.id in names) or (isinstance(f, ast.Attribute) and f.attr == "enumerate_paths")

    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and is_target(n.func)]
    refs = [n for n in ast.walk(tree) if (isinstance(n, ast.Name) and n.id in names)
            or (isinstance(n, ast.Attribute) and n.attr == "enumerate_paths")]
    bad: list[str] = []
    if len(refs) != len(calls):
        bad.append(f"{filename}: enumerate_paths is referenced other than by a direct call")
    for c in calls:
        where = f"{filename}:{c.lineno}"
        if any(isinstance(a, ast.Starred) for a in c.args) or any(k.arg is None for k in c.keywords):
            bad.append(f"{where}: *args/**kwargs hide the arguments")
            continue
        state = c.args[0] if c.args else next((k.value for k in c.keywords if k.arg == "state"), None)
        digest = [k.value for k in c.keywords if k.arg == "profile_digest"]
        if state is None or len(digest) != 1:
            bad.append(f"{where}: needs a profile argument and exactly one profile_digest keyword")
            continue
        d = digest[0]
        ok = (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in digest_names
              and len(d.args) == 1 and not d.keywords and ast.dump(d.args[0]) == ast.dump(state))
        if not ok:
            bad.append(f"{where}: profile_digest must be identity_profile_digest(<the profile argument>), got {ast.unparse(d)}")
    return len(calls), bad


def test_every_production_caller_passes_the_identity_digest_of_the_profile_it_enumerates():
    total, bad = 0, []
    for path in sorted((SRC / "skillgraph").rglob("*.py")):
        if path.name == "paths.py" and path.parent.name == "graph":
            continue  # the definition
        n, v = _enumerate_paths_call_violations(path.read_text(encoding="utf-8"), str(path.relative_to(SRC)))
        total += n
        bad += v
    assert bad == []
    assert total >= 2  # the scanner does see the two demo callers (guards against a check that silently finds nothing)


@pytest.mark.parametrize("snippet", [
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest='sha256:' + '0' * 64)",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=DIGEST)",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=identity_profile_digest(other))",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=identity_profile_digest(state.model_copy()))",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=logging_profile_digest(state))",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=identity_profile_digest(state, x))",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1)",
    "enumerate_paths(state, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=a, profile_digest2=b)",
    "enumerate_paths(state, r, c, s, 3, None, **limits)",
    "enumerate_paths(*args, profile_digest=identity_profile_digest(state))",
    "f = enumerate_paths\nf(state, r, c, s, 3, None, profile_digest=identity_profile_digest(state))",
    "graph.enumerate_paths(state, r, c, s, 3, None, profile_digest=DIGEST)",
    "from skillgraph.graph import enumerate_paths as ep\nep(state, r, c, s, 3, None, profile_digest=DIGEST)",
    "enumerate_paths(state=state, registry=r, profile_digest=identity_profile_digest(other))",
], ids=["inline-constant", "named-constant", "other-profile", "different-expression", "logging-digest", "extra-argument",
        "no-digest", "no-digest-keyword", "kwargs", "starargs", "alias-assignment", "attribute-constant", "import-alias",
        "state-keyword"])
def test_the_caller_check_rejects_a_constant_unrelated_or_unverifiable_digest(snippet):
    _, bad = _enumerate_paths_call_violations(snippet)
    assert bad, snippet


@pytest.mark.parametrize("snippet", [
    "enumerate_paths(profile, r, c, s, 3, None, max_expansions=1, max_steps_limit=1, profile_digest=identity_profile_digest(profile))",
    "enumerate_paths(req.profile, r, c, s, 3, None, profile_digest=identity_profile_digest(req.profile))",
    "graph.enumerate_paths(state, r, c, s, 3, None, profile_digest=identity_profile_digest(state))",
    "from skillgraph.graph import enumerate_paths as ep\nfrom skillgraph.eligibility.evaluate import identity_profile_digest as ipd\n"
    "ep(state, r, c, s, 3, None, profile_digest=ipd(state))",
    "enumerate_paths(state=p, registry=r, profile_digest=identity_profile_digest(p))",
])
def test_the_caller_check_accepts_the_documented_form(snippet):
    n, bad = _enumerate_paths_call_violations(snippet)
    assert n == 1 and bad == []


# ---- identity changes nothing about eligibility or enumeration -------------------------------------------------------------------------


def test_identity_leaves_verdicts_and_enumeration_semantics_unchanged():
    kinds = {1: "M", 2: "C", 3: "U", 4: "N", 5: "M"}
    reg = world(kinds)
    got = enum(reg, max_steps=3)
    assert all(Verdict.NOT_MET not in [s.eligibility.verdict for s in p.steps] for p in got)  # still never emitted
    assert not any(code(4) in p.target_codes for p in got)  # a NOT_MET first step is not extended
    stripped = [(p.target_codes, p.verdict, p.steps) for p in got]
    assert stripped == [(p.target_codes, p.verdict, p.steps) for p in enum(reg, max_steps=3, profile_digest=OTHER_DIGEST)]
    assert digits(got)[0] == (1,) and digits(got)[1] == (1, 2)  # depth-first pre-order (P-1) as before
