"""Endpoint-specific request builders, layered over the generic `transport.prepare`."""

from collections.abc import Mapping
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

import httpx2
from msgspec import UNSET, UnsetType

from typesafe_sdk._core.config import Config
from typesafe_sdk._core.constants import MODELS_PATH, SYSTEM_ONE_PATH
from typesafe_sdk._core.errors import TypeSafeError
from typesafe_sdk._core.json_types import JSONContent, JSONValue
from typesafe_sdk._core.question_types import Question
from typesafe_sdk._core.questions import normalize_questions
from typesafe_sdk._core.response_types import ListModelsResponse, SystemOneResponse
from typesafe_sdk._core.transport import Request, prepare

if TYPE_CHECKING:
    from pydantic import BaseModel


def prepare_system_one(
    config: Config,
    state: JSONContent | UnsetType,
    questions: Mapping[str, Question] | None,
    model: str | None,
    extra_body: Mapping[str, JSONValue | None] | None,
    timeout: float | httpx2.Timeout | None,
    headers: Mapping[str, str] | None,
    *,
    input: JSONContent | UnsetType = UNSET,
    response_model: "type[BaseModel] | None" = None,
) -> Request[SystemOneResponse]:
    if not isinstance(state, UnsetType) and not isinstance(input, UnsetType):
        raise TypeSafeError("Pass either input or state, not both.")
    state = input if not isinstance(input, UnsetType) else state
    if isinstance(state, UnsetType) or state is None:
        raise TypeSafeError("An input or state is required.")
    if response_model is not None:
        if questions is not None:
            raise TypeSafeError("Pass either response_model or questions, not both.")
        if extra_body is not None and {"state", "questions"}.intersection(extra_body):
            raise TypeSafeError("extra_body cannot override state or questions when using response_model.")
        if find_spec("pydantic") is None:
            raise TypeSafeError('Install Pydantic support with: pip install "typesafe-sdk[pydantic]"')
        from typesafe_sdk._core.pydantic import questions_from_model

        questions = questions_from_model(response_model)
    if questions is None:
        raise TypeSafeError("Pass questions or a response_model.")
    body: dict[str, Any] = {
        "state": state,
        "model": config.default_model if model is None else model,
        "questions": normalize_questions(questions),
    }
    if extra_body is not None:
        body.update(extra_body)
    return prepare(config, "POST", SYSTEM_ONE_PATH, body, timeout, headers, SystemOneResponse)


def prepare_models(
    config: Config, timeout: float | httpx2.Timeout | None, headers: Mapping[str, str] | None
) -> Request[ListModelsResponse]:
    return prepare(config, "GET", MODELS_PATH, None, timeout, headers, ListModelsResponse)
