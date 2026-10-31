import pytest

from skillgraph.model.ids import (
    DuplicateIdError,
    IdError,
    IdKind,
    SlugCollisionError,
    SlugIndex,
    UnknownSlugError,
    code_of,
    make_id,
    slug_of,
    split_id,
)


@pytest.mark.parametrize(
    ("kind", "key", "expected_id", "expected_slug"),
    [
        (IdKind.QUAL, "AMH/Q0301", "qual:AMH/Q0301", "AMH.Q0301"),
        (IdKind.NOS, "DGT/VSQ/N0102", "nos:DGT/VSQ/N0102", "DGT.VSQ.N0102"),
        (IdKind.MOD, "AMH/Q0301/S1", "mod:AMH/Q0301/S1", "AMH.Q0301.S1"),
        (IdKind.NCO, "8153.0101", "nco:8153.0101", "8153.0101"),
        (IdKind.SRC, "A3", "src:A3", "A3"),
        (IdKind.SRC, "D2-p5", "src:D2-p5", "D2-p5"),
        (IdKind.RULE, "AMH/Q2301/E9", "rule:AMH/Q2301/E9", None),
        (IdKind.RULE, "AMH/Q2301/AGE", "rule:AMH/Q2301/AGE", None),
        (IdKind.CLAIM, "AMH/Q0301/P2", "claim:AMH/Q0301/P2", None),
        (IdKind.CONFLICT, "OV-036", "conflict:OV-036", None),
        (IdKind.EV, "3f9c1a0b2c4d5e6f", "ev:3f9c1a0b2c4d5e6f", "ev:3f9c1a0b2c4d5e6f"),
        (IdKind.CB, "1a2b3c4d5e6f", "cb-1a2b3c4d5e6f", None),
    ],
)
def test_every_kind_builds_splits_and_slugs(kind, key, expected_id, expected_slug):
    entity_id = make_id(kind, key)
    assert entity_id == expected_id
    assert split_id(entity_id) == (kind, key)
    assert slug_of(entity_id) == expected_slug


@pytest.mark.parametrize("code", ["AMH/Q0301", "AMH/Q2301", "TEST/Q9001"])
def test_round_trip_code_id_slug_registry_lookup(code):
    entity_id = make_id(IdKind.QUAL, code)
    slug = slug_of(entity_id)
    index = SlugIndex()
    index.add(entity_id)
    assert slug in index
    assert index.lookup(slug) == entity_id
    assert code_of(index.lookup(slug)) == code


def test_round_trip_through_registry_with_several_kinds():
    ids = [make_id(IdKind.QUAL, "AMH/Q0301"), make_id(IdKind.NOS, "AMH/N0301"), make_id(IdKind.MOD, "AMH/Q0301/S1"),
           make_id(IdKind.NCO, "8153.0101"), make_id(IdKind.SRC, "A3")]
    index = SlugIndex()
    for entity_id in ids:
        index.add(entity_id)
    assert len(index) == len(ids)
    assert [index.lookup(slug_of(i)) for i in ids] == ids


def test_slug_collision_raises():
    index = SlugIndex()
    index.add("qual:AMH/Q0301")
    with pytest.raises(SlugCollisionError):
        index.add("nos:AMH/N0301", slug="AMH.Q0301")  # a second id claiming an occupied slug
    assert index.lookup("AMH.Q0301") == "qual:AMH/Q0301"  # the first registration is untouched


def test_registering_one_id_twice_raises():
    index = SlugIndex()
    index.add("qual:AMH/Q0301")
    with pytest.raises(DuplicateIdError):
        index.add("qual:AMH/Q0301")


def test_unknown_slug_and_slugless_kind_raise():
    index = SlugIndex()
    with pytest.raises(UnknownSlugError):
        index.lookup("AMH.Q0301")
    with pytest.raises(IdError):
        index.add("conflict:OV-036")  # conflicts have no slug


@pytest.mark.parametrize(
    "bad",
    ["", "AMH/Q0301", "qual:amh/q0301", "qual:AMH.Q0301", "qual:AMH/Q030", "nos:AMH/Q0301", "mod:AMH/Q0301",
     "nco:8153", "ev:3f9c", "cb:1a2b3c4d5e6f", "cb-1A2B3C4D5E6F", "conflict:036", "foo:bar", "qual:AMH/Q0301 "],
)
def test_malformed_ids_are_rejected(bad):
    with pytest.raises(IdError):
        split_id(bad)


def test_make_id_rejects_a_slug_shaped_key():
    with pytest.raises(IdError):
        make_id(IdKind.QUAL, "AMH.Q0301")  # a slug is a lookup key and is never accepted as a code
