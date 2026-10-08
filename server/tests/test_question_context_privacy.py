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


COUNTRY_DISPLAYS = [
    "schemas.countrydle.FullQuestionDisplay",
    "schemas.continental.ContinentalQuestionDisplay",
    "schemas.flagdle.FlagdleQuestionDisplay",
]


def question_display(schema_path, *, valid=True, answer=True, terminal=False):
    from importlib import import_module

    module_name, class_name = schema_path.rsplit(".", 1)
    schema = getattr(import_module(module_name), class_name)
    return schema.model_validate({
        "id": 7, "user_id": None, "day_id": 4,
        "original_question": "Is it in Europe?",
        "question": "Is Poland, whose capital is Warsaw, in Europe?",
        "valid": valid, "answer": answer,
        "explanation": "Poland is in Europe; its capital is Warsaw.",
        "asked_at": datetime(2026, 10, 4, tzinfo=timezone.utc),
        "context": "Private retrieved facts about Poland and Warsaw",
    }, context={"terminal": terminal})


@pytest.mark.parametrize("schema_path", COUNTRY_DISPLAYS)
def test_country_explanation_is_disclosed_only_after_an_answered_game_ends(schema_path):
    active = question_display(schema_path).model_dump(mode="json")
    # The original/rewrite is handled separately; private factual explanation
    # must not be available to a player inspecting the active HTTP payload.
    assert active["explanation"] in (None, "")
    terminal = question_display(schema_path, terminal=True).model_dump(mode="json")
    assert "Poland" in terminal["explanation"]
    assert "Europe" in terminal["explanation"]
    assert "Warsaw" in terminal["explanation"]


@pytest.mark.parametrize("question_schema,state_schema", [
    ("schemas.countrydle.FullQuestionDisplay", "schemas.countrydle.CountrydleStateResponse"),
    ("schemas.continental.ContinentalQuestionDisplay", "schemas.continental.ContinentalStateResponse"),
    ("schemas.flagdle.FlagdleQuestionDisplay", "schemas.flagdle.FlagdleStateResponse"),
])
def test_terminal_explanations_survive_enclosing_state_serialization(question_schema, state_schema):
    from importlib import import_module

    module_name, class_name = state_schema.rsplit(".", 1)
    schema = getattr(import_module(module_name), class_name)
    terminal = question_display(question_schema, terminal=True)
    response = schema(
        date="2026-10-04",
        state={
            "remaining_questions": 9, "remaining_guesses": 3,
            "questions_asked": 1, "guesses_made": 0, "is_game_over": True, "won": True,
        },
        questions=[terminal], guesses=[],
    )
    explanation = response.model_dump(mode="json")["questions"][0]["explanation"]
    assert "Poland" in explanation and "Warsaw" in explanation


@pytest.mark.parametrize("schema_path", [
    "schemas.countrydle.InvalidQuestionDisplay",
    "schemas.continental.InvalidContinentalQuestionDisplay",
    *COUNTRY_DISPLAYS,
    "schemas.us_statedle.USStateQuestionDisplay",
    "schemas.powiatdle.PowiatQuestionDisplay",
    "schemas.wojewodztwodle.WojewodztwoQuestionDisplay",
])
@pytest.mark.parametrize("valid,answer", [(False, None), (True, None)])
@pytest.mark.parametrize("terminal", [False, True])
def test_invalid_or_unverified_feedback_never_discloses_target_facts(schema_path, valid, answer, terminal):
    payload = question_display(schema_path, valid=valid, answer=answer, terminal=terminal).model_dump(mode="json")
    assert payload["original_question"] == "Is it in Europe?"
    assert "Poland" not in payload["explanation"]
    assert "Warsaw" not in payload["explanation"]
    assert payload.get("question") in (None, payload["original_question"])
    assert "Private retrieved facts" not in str(payload)
