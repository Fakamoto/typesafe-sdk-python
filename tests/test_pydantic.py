from enum import Enum
from typing import Annotated, Literal

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    create_model,
    field_validator,
)

from typesafe_sdk import (
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeError,
    Usage,
)
from typesafe_sdk._core.pydantic import parse_model, questions_from_model


class Tone(Enum):
    CALM = "calm"
    LOUD = "loud"


class Result(BaseModel):
    model_config = ConfigDict(strict=True)
    category: Literal["a", "b"] = Field(description="Pick a category")
    tone: Tone
    accepted: bool = Field(alias="isAccepted", default=False)
    probability: Annotated[float, Noul(instructions="Explicit instruction")]
    quality: Annotated[float, Score(criteria=["bad", "good"])] = Field(description="Quality")


def response(**answers: NoulAnswer | ChoiceAnswer | ScoreAnswer) -> SystemOneResponse:
    return SystemOneResponse(model="test", usage=Usage(), answers=answers)


def test_conversion_and_validation() -> None:
    questions = questions_from_model(Result)
    assert questions == {
        "category": Choice(criteria={"a": None, "b": None}, instructions="Pick a category"),
        "tone": Choice(criteria={"calm": None, "loud": None}),
        "accepted": Noul(),
        "probability": Noul(instructions="Explicit instruction"),
        "quality": Score(criteria=["bad", "good"], instructions="Quality"),
    }
    result = parse_model(
        Result,
        response(
            category=ChoiceAnswer(choice="a", confidence=1, probabilities={"a": 1}),
            tone=ChoiceAnswer(choice="calm", confidence=1, probabilities={"calm": 1}),
            accepted=NoulAnswer(noul=0.5),
            probability=NoulAnswer(noul=0.7),
            quality=ScoreAnswer(
                score=0.8,
                confidence=1,
                probabilities={0: 0.2, 1: 0.8},
                legend={0: "bad", 1: "good"},
            ),
        ),
    )
    assert result.category == "a" and result.tone is Tone.CALM
    assert result.accepted is True and result.probability == 0.7 and result.quality == 0.8


@pytest.mark.parametrize(
    "annotation",
    [str, int, float, list[str], dict[str, bool], bool | None, Literal[1], Result],
)
def test_unsupported_fields(annotation: object) -> None:
    model = create_model("Unsupported", value=(annotation, ...))
    with pytest.raises(TypeSafeError, match="value"):
        questions_from_model(model)


@pytest.mark.parametrize("model", [BaseModel, RootModel[bool]])
def test_unsupported_model(model: type[BaseModel]) -> None:
    with pytest.raises(TypeSafeError, match="nonempty flat"):
        questions_from_model(model)


def test_conflicting_metadata() -> None:
    class Conflict(BaseModel):
        value: Annotated[float, Noul(), Score(criteria=["bad", "good"])]

    with pytest.raises(TypeSafeError, match="conflicting"):
        questions_from_model(Conflict)


def test_defaults_do_not_mask_missing_answers() -> None:
    class Default(BaseModel):
        value: bool = False

    with pytest.raises(TypeSafeError, match="Missing answer"):
        parse_model(Default, response())
    assert parse_model(Default, response(value=NoulAnswer(noul=0.49))).value is False
    with pytest.raises(TypeSafeError, match="Wrong answer type"):
        parse_model(
            Default,
            response(value=ChoiceAnswer(choice="yes", confidence=1, probabilities={})),
        )
    for probability in (-0.1, 1.1, float("nan"), float("inf")):
        with pytest.raises(TypeSafeError, match="Invalid probability"):
            parse_model(Default, response(value=NoulAnswer(noul=probability)))


def test_unknown_choice_and_validators() -> None:
    class Validated(BaseModel):
        value: Literal["a", "b"]

        @field_validator("value")
        @classmethod
        def reject_b(cls, value: str) -> str:
            if value == "b":
                raise ValueError("b rejected")
            return value

    with pytest.raises(TypeSafeError, match="Unknown choice"):
        parse_model(
            Validated,
            response(value=ChoiceAnswer(choice="c", confidence=1, probabilities={})),
        )
    with pytest.raises(ValidationError, match="b rejected"):
        parse_model(
            Validated,
            response(value=ChoiceAnswer(choice="b", confidence=1, probabilities={})),
        )


def test_metadata_instructions_and_criteria() -> None:
    noul = Noul()

    class Described(BaseModel):
        value: Annotated[float, noul] = Field(description="Fallback")
        explicit: Annotated[bool, Noul(instructions="Keep")] = Field(description="Discard")

    assert questions_from_model(Described)["value"] == Noul(instructions="Fallback")
    assert questions_from_model(Described)["explicit"] == Noul(instructions="Keep")
    assert noul.instructions is None

    class EmptyScore(BaseModel):
        value: Annotated[float, Score(criteria=[])]

    with pytest.raises(TypeSafeError, match="no criteria"):
        questions_from_model(EmptyScore)


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf")])
def test_score_within_rubric(score: float) -> None:
    class Scored(BaseModel):
        value: Annotated[float, Score(criteria=["low", "high"])]

    with pytest.raises(TypeSafeError, match="Invalid score"):
        parse_model(Scored, response(value=ScoreAnswer(score=score, confidence=1, probabilities={}, legend={})))
