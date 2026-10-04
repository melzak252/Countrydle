from datetime import datetime, timezone

import pytest


@pytest.mark.parametrize("schema_path", [
    "schemas.countrydle.FullQuestionDisplay",
    "schemas.continental.ContinentalQuestionDisplay",
    "schemas.us_statedle.USStateQuestionDisplay",
    "schemas.powiatdle.PowiatQuestionDisplay",
    "schemas.wojewodztwodle.WojewodztwoQuestionDisplay",
])
def test_public_question_context_is_available_internally_but_not_serialized(schema_path):
    from importlib import import_module

    module_name, class_name = schema_path.rsplit(".", 1)
    schema = getattr(import_module(module_name), class_name)
    data = {
        "id": 7,
        "original_question": "Is this the target?",
        "question": "Is the target in Europe?",
        "valid": True,
        "answer": True,
        "explanation": "The recorded evidence confirms this.",
        "asked_at": datetime(2026, 10, 4, tzinfo=timezone.utc),
        "context": "Private server retrieval content.",
    }
    if class_name != "ContinentalQuestionDisplay":
        data.update(user_id=None, day_id=4)

    response = schema(**data)
    assert response.context == "Private server retrieval content."
    assert "context" not in response.model_dump(mode="json")
