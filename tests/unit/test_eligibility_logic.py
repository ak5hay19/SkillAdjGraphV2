"""P3.2 verdict logic: exhaustive truth tables for and_/or_ (ARCHITECTURE §11.1).

The expected tables are written out by hand from the lattice NOT_MET < UNKNOWN < CONDITIONAL < MET; they are not computed
from ``Verdict.rank``, so a wrong rank order would fail here.
"""

import itertools
from functools import reduce

import pytest

from skillgraph.eligibility.logic import and_, or_
from skillgraph.model.eligibility import Verdict

N, U, C, M = Verdict.NOT_MET, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.MET
ORDER = [N, U, C, M]

# rows: left operand, columns: right operand, both in ORDER
AND_TABLE = {
    N: {N: N, U: N, C: N, M: N},
    U: {N: N, U: U, C: U, M: U},
    C: {N: N, U: U, C: C, M: C},
    M: {N: N, U: U, C: C, M: M},
}
OR_TABLE = {
    N: {N: N, U: U, C: C, M: M},
    U: {N: U, U: U, C: C, M: M},
    C: {N: C, U: C, C: C, M: M},
    M: {N: M, U: M, C: M, M: M},
}


def test_the_four_verdicts_are_the_documented_ones():
    assert {v.value for v in Verdict} == {"MET", "NOT_MET", "UNKNOWN", "CONDITIONAL"}
    assert [v.rank for v in ORDER] == sorted(v.rank for v in ORDER)


@pytest.mark.parametrize(("a", "b"), list(itertools.product(ORDER, ORDER)))
def test_and_truth_table(a, b):
    assert and_(a, b) is AND_TABLE[a][b]


@pytest.mark.parametrize(("a", "b"), list(itertools.product(ORDER, ORDER)))
def test_or_truth_table(a, b):
    assert or_(a, b) is OR_TABLE[a][b]


def test_the_tables_have_16_entries_each():
    assert sum(len(r) for r in AND_TABLE.values()) == sum(len(r) for r in OR_TABLE.values()) == 16


@pytest.mark.parametrize(("a", "b"), list(itertools.product(ORDER, ORDER)))
def test_both_are_commutative(a, b):
    assert and_(a, b) is and_(b, a) and or_(a, b) is or_(b, a)


@pytest.mark.parametrize("a", ORDER)
def test_both_are_idempotent_and_a_single_operand_is_itself(a):
    assert and_(a, a) is a and or_(a, a) is a and and_(a) is a and or_(a) is a


@pytest.mark.parametrize(("a", "b", "c"), list(itertools.product(ORDER, repeat=3)))
def test_n_ary_associativity(a, b, c):
    assert and_(a, b, c) is and_(and_(a, b), c) is and_(a, and_(b, c))
    assert or_(a, b, c) is or_(or_(a, b), c) is or_(a, or_(b, c))
    # the n-ary result is the left fold of the hand-written pairwise table
    assert and_(a, b, c) is AND_TABLE[AND_TABLE[a][b]][c]
    assert or_(a, b, c) is OR_TABLE[OR_TABLE[a][b]][c]


@pytest.mark.parametrize("operands", [p for n in (4, 5) for p in itertools.product(ORDER, repeat=n)])
def test_n_ary_equals_the_fold_for_longer_inputs(operands):
    assert and_(*operands) is reduce(lambda x, y: AND_TABLE[x][y], operands)
    assert or_(*operands) is reduce(lambda x, y: OR_TABLE[x][y], operands)


def test_the_documented_semantics():
    assert and_(N, U) is N  # one definite failure fails a conjunction
    assert and_(U, M) is U  # an unknown never becomes a pass
    assert or_(C, U) is C  # a conditional route beats an unknown one
    assert and_(C, M) is C and or_(N, N) is N
    assert or_(N, U) is U  # unknown is not NOT_MET: missing evidence never becomes a failure either


def test_target_shape_and_age_with_or_of_rows():
    # Target = AND(age, OR(rows))
    assert and_(M, or_(U, N, C)) is C
    assert and_(N, or_(M, M)) is N
    assert and_(M, or_(N, N)) is N
    assert and_(M, or_(U, U)) is U


def test_an_empty_call_raises_rather_than_inventing_an_identity():
    with pytest.raises(ValueError):
        and_()
    with pytest.raises(ValueError):
        or_()


@pytest.mark.parametrize("bad", ["MET", None, 3, True, object()])
def test_non_verdict_operands_are_rejected_not_coerced(bad):
    with pytest.raises(TypeError):
        and_(M, bad)
    with pytest.raises(TypeError):
        or_(bad, N)


def test_the_result_is_always_one_of_the_operands():
    for a, b in itertools.product(ORDER, ORDER):
        assert and_(a, b) in (a, b) and or_(a, b) in (a, b)
