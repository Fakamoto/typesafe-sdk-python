"""Typed output contracts at the HTTP boundary, for both clients."""

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

import httpx2
import pytest
from pydantic import BaseModel, Field, RootModel, ValidationError

from tests.conftest import ClientFactory
from typesafe_sdk import AsyncTypeSafeClient, Choice, SystemOneResponse, TypeSafeError


class Ticket(BaseModel):
    category: Literal["billing", "technical"] = Field(description="What is this ticket about?")
    urgent: bool = Field(description="Does this need immediate attention?")


async def call(clients: ClientFactory, handler: Callable[[httpx2.Request], httpx2.Response], **kwargs: Any) -> Any:
    client = clients(handler)
    if isinstance(client, AsyncTypeSafeClient):
        return await client.system_one(**kwargs)
    return client.system_one(**kwargs)


def reply(category: str = "billing") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "model": "jev-latest",
            "usage": {},
            "answers": {
                "category": {"type": "choice", "choice": category, "confidence": 0.9, "probabilities": {"billing": 0.9, "technical": 0.1}},
                "urgent": {"type": "noul", "noul": 0.5}
            },
        },
    )


@pytest.mark.parametrize("input_name", ["input", "state"])
async def test_typed_round_trip(clients: ClientFactory, input_name: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert json.loads(request.content) == {
            "state": "I was charged twice.",
            "model": "jev-latest",
            "questions": {
                "category": {
                    "type": "choice",
                    "instructions": "What is this ticket about?",
                    "criteria": {"billing": None, "technical": None},
                },
                "urgent": {"type": "noul", "instructions": "Does this need immediate attention?"}
            },
            "custom": True,
        }
        assert request.headers["x-test"] == "typed"
        return reply()

    result = await call(
        clients,
        handler,
        **{input_name: "I was charged twice."},
        response_model=Ticket,
        extra_headers={"x-test": "typed"},
        extra_body={"custom": True},
    )
    assert isinstance(result, Ticket)
    assert result.category == "billing"
    assert result.urgent is True


async def test_input_alias_for_existing_questions(clients: ClientFactory) -> None:
    result = await call(
        clients, lambda _: reply(), input="x", questions={"category": Choice(criteria={"billing": None, "technical": None})}
    )
    assert isinstance(result, SystemOneResponse)
    assert result.choices["category"].choice == "billing"


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"input": "x", "state": "y", "response_model": Ticket}, "either input or state"),
        ({"response_model": Ticket}, "input or state is required"),
        ({"input": "x"}, "questions or a response_model"),
        ({"input": "x", "questions": {}, "response_model": Ticket}, "At least one question"),
        ({"input": "x", "response_model": Ticket, "extra_body": {"questions": {}}}, "cannot override"),
        ({"input": "x", "response_model": Ticket, "extra_body": {"state": "y"}}, "cannot override"),
    ],
)
async def test_invalid_arguments_do_not_send(clients: ClientFactory, kwargs: dict[str, Any], message: str) -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid request reached the network")

    with pytest.raises(TypeSafeError, match=message):
        await call(clients, handler, **kwargs)


async def test_unsupported_schema_does_not_send(clients: ClientFactory) -> None:
    class Unsupported(BaseModel):
        message: str

    def handler(_: httpx2.Request) -> httpx2.Response:
        pytest.fail("Unsupported schema reached the network")

    with pytest.raises(TypeSafeError):
        await call(clients, handler, input="x", response_model=Unsupported)


async def test_validation_failure_is_not_retried(clients: ClientFactory) -> None:
    attempts = 0

    def handler(_: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return reply("unknown")

    with pytest.raises((TypeSafeError, ValidationError)):
        await call(clients, handler, input="x", response_model=Ticket)
    assert attempts == 1


class CustomerInput(BaseModel):
    message: str
    received: datetime
    context: dict[str, list[str | None]]


@pytest.mark.parametrize("as_model", [False, True])
async def test_structured_input(clients: ClientFactory, as_model: bool) -> None:
    model = CustomerInput(message="Charged twice", received=datetime(2026, 9, 18, tzinfo=timezone.utc), context={"tags": ["billing", None]})
    value = model if as_model else model.model_dump(mode="json")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert json.loads(request.content)["state"] == {"message": "Charged twice", "received": "2026-09-18T00:00:00Z", "context": {"tags": ["billing", None]}}
        return reply()

    result = await call(clients, handler, input=value, response_model=Ticket)
    assert isinstance(result, Ticket) and result.urgent is True


@pytest.mark.parametrize("value", [None, 1, True])
async def test_scalar_root_input_does_not_send(clients: ClientFactory, value: Any) -> None:
    with pytest.raises(TypeSafeError, match="must serialize"):
        await call(clients, lambda _: pytest.fail("Invalid input reached HTTP"), input=RootModel[Any](value), response_model=Ticket)


async def test_explicit_questions_keep_envelope_model(clients: ClientFactory) -> None:
    class Envelope(BaseModel):
        model: str
        answers: dict[str, Any]

    result = await call(clients, lambda _: reply(), input="x", questions={"category": Choice(criteria={"billing": None})}, response_model=Envelope)
    assert isinstance(result, Envelope)
    assert result.answers["category"]["choice"] == "billing"
