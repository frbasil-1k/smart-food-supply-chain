from __future__ import annotations

import pytest

from sfc_api.errors import ApiError
from sfc_api.validation import StrictModel, parse_json


class ExampleRequest(StrictModel):
    quantity: str


def test_parse_json_returns_a_validated_model() -> None:
    parsed = parse_json(ExampleRequest, {"quantity": "2.50"})
    assert parsed.quantity == "2.50"


def test_parse_json_rejects_unknown_fields() -> None:
    with pytest.raises(ApiError) as caught:
        parse_json(ExampleRequest, {"quantity": "1.00", "status": "DELIVERED"})

    error = caught.value
    assert error.status_code == 422
    assert error.code == "validation_error"
    assert any(detail["field"] == "status" for detail in error.details)


def test_parse_json_rejects_a_non_object_body() -> None:
    with pytest.raises(ApiError):
        parse_json(ExampleRequest, None)
