"""Credits are never hours (ARCHITECTURE §12, decision D1), and no field models incremental retraining time."""

import inspect
import typing

import pytest
from model_factory import hours, official
from pydantic import BaseModel, ValidationError

from skillgraph.model import conflict, eligibility, evidence, occupation, qualification, source
from skillgraph.model.evidence import CreditValue
from skillgraph.model.qualification import CreditGroup, HoursBreakdown

MODULES = [evidence, source, occupation, conflict, eligibility, qualification]


def all_models() -> list[type[BaseModel]]:
    found = {}
    for mod in MODULES:
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, BaseModel) and obj.__module__ == mod.__name__ and "[" not in obj.__name__:
                found[obj.__name__] = obj
    return list(found.values())


def mentions(tp: object, target: type) -> bool:
    """True if ``tp`` is, wraps or parametrises a subclass of ``target``."""
    if isinstance(tp, type) and issubclass(tp, target):
        return True
    return any(mentions(a, target) for a in typing.get_args(tp))


def fields():
    return [(m, n, f) for m in all_models() for n, f in m.model_fields.items()]


FIELD_PARAMS = [pytest.param(m, n, f, id=f"{m.__name__}.{n}") for m, n, f in fields()]


def test_models_were_discovered():
    names = {m.__name__ for m in all_models()}
    assert {"Qualification", "NosMembership", "HoursBreakdown", "Evidence", "Conflict", "Occupation"} <= names


@pytest.mark.parametrize(("model", "name", "field"), FIELD_PARAMS)
def test_credit_fields_are_credit_values_and_nothing_else_is(model, name, field):
    # CreditGroup wraps a CreditValue (OV-034/035); it is the one credit container besides CreditValue itself.
    is_credit_typed = mentions(field.annotation, CreditValue) or mentions(field.annotation, CreditGroup)
    assert ("credit" in name.lower()) == is_credit_typed, f"{model.__name__}.{name}"
    if "hour" in name.lower():
        assert not is_credit_typed and "credit" not in name.lower()


def test_hours_fields_are_not_credit_typed():
    for name, field in HoursBreakdown.model_fields.items():
        assert not mentions(field.annotation, CreditValue), name


def test_no_model_has_an_incremental_or_retraining_field():
    banned = ("increment", "retrain", "reduced", "exempt", "rpl", "equivalen")
    offenders = [f"{m.__name__}.{n}" for m, n, _ in fields() if any(b in n.lower() for b in banned) and n != "or_equivalent"]
    assert offenders == []


def test_a_credit_value_cannot_be_supplied_where_hours_are_expected():
    # Same number, but credits carry NOT_USED while hours may not.
    with pytest.raises(ValidationError, match="never NOT_USED"):
        HoursBreakdown.model_validate({"total": official(14.0, engine_use="NOT_USED")})
    ok = HoursBreakdown.model_validate(hours())
    assert ok.is_complete and ok.total.engine_use.value == "SAFE_HOURS"


def test_membership_and_qualification_credit_fields_reject_any_other_engine_use():
    from model_factory import curated, membership

    from skillgraph.model.qualification import NosMembership, Qualification

    bad = official(4.0, engine_use="SAFE_HOURS")
    with pytest.raises(ValidationError, match="NOT_USED"):
        NosMembership.model_validate(membership(credits=bad))
    with pytest.raises(ValidationError, match="NOT_USED"):
        Qualification.model_validate(curated(credits=bad))
