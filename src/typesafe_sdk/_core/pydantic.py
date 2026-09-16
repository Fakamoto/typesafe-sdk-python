"""Optional conversion between flat Pydantic models and System One questions."""

from enum import Enum
from typing import Literal, TypeVar, get_args, get_origin

import msgspec
from pydantic import BaseModel
from pydantic.version import VERSION

from typesafe_sdk._core.errors import TypeSafeError
from typesafe_sdk._core.question_types import Choice, Noul, Question, Score
from typesafe_sdk._core.questions import normalize_questions
from typesafe_sdk._core.response_types import (
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    SystemOneResponse,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def questions_from_model(model: type[ModelT]) -> dict[str, Question]:
    """Convert supported model fields to questions, using Python field names."""
    if not (2, 11) <= tuple(int(part) for part in VERSION.split(".")[:2]) < (3, 0):
        raise TypeSafeError('Pydantic >=2.11,<3 is required. Install with: pip install "typesafe-sdk[pydantic]"')
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise TypeSafeError("response_model must be a Pydantic BaseModel subclass.")
    if model.__pydantic_root_model__ or not model.model_fields:
        raise TypeSafeError("response_model must be a nonempty flat model, not a RootModel.")
    questions: dict[str, Question] = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        metadata = [item for item in field.metadata if isinstance(item, (Noul, Choice, Score))]
        if len(metadata) > 1:
            raise TypeSafeError(f'Field "{name}" has conflicting question metadata.')
        question = metadata[0] if metadata else None
        labels = None
        if get_origin(annotation) is Literal:
            labels = get_args(annotation)
        elif isinstance(annotation, type) and issubclass(annotation, Enum):
            labels = tuple(member.value for member in annotation)
        if labels is not None:
            if not labels or not all(isinstance(label, str) for label in labels):
                raise TypeSafeError(f'Field "{name}" requires nonempty string Literal or Enum values.')
            if question is None:
                question = Choice(criteria=dict.fromkeys(labels))
            elif not isinstance(question, Choice) or set(question.criteria) != set(labels):
                raise TypeSafeError(f'Field "{name}" has incompatible Choice metadata.')
        elif annotation is bool:
            if question is None:
                question = Noul()
            elif not isinstance(question, Noul):
                raise TypeSafeError(f'Field "{name}" requires Noul metadata.')
        elif annotation is not float or not isinstance(question, (Noul, Score)):
            raise TypeSafeError(
                f'Field "{name}" has an unsupported type; use string Literal/Enum, bool, or float with Noul/Score metadata.'
            )
        if question.instructions is None and field.description is not None:
            question = msgspec.structs.replace(question, instructions=field.description)
        questions[name] = question
    return normalize_questions(questions)


def parse_model(model: type[ModelT], response: SystemOneResponse) -> ModelT:
    """Require every requested answer, then run Pydantic model validation."""
    values: dict[str, object] = {}
    for name, question in questions_from_model(model).items():
        answer = response.answers.get(name)
        if answer is None:
            raise TypeSafeError(f'Missing answer for field "{name}".')
        if isinstance(question, Choice) and isinstance(answer, ChoiceAnswer):
            if answer.choice not in question.criteria:
                raise TypeSafeError(f'Unknown choice for field "{name}": {answer.choice!r}.')
            annotation = model.model_fields[name].annotation
            values[name] = annotation(answer.choice) if isinstance(annotation, type) and issubclass(annotation, Enum) else answer.choice
        elif isinstance(question, Noul) and isinstance(answer, NoulAnswer):
            if not 0 <= answer.noul <= 1:
                raise TypeSafeError(f'Invalid probability for field "{name}"; expected a value from zero to one.')
            values[name] = answer.noul >= 0.5 if model.model_fields[name].annotation is bool else answer.noul
        elif isinstance(question, Score) and isinstance(answer, ScoreAnswer):
            if not 0 <= answer.score <= len(question.criteria) - 1:
                raise TypeSafeError(f'Invalid score for field "{name}"; expected a value within the rubric.')
            values[name] = answer.score
        else:
            raise TypeSafeError(f'Wrong answer type for field "{name}".')
    return model.model_validate(values, by_name=True, by_alias=False)
