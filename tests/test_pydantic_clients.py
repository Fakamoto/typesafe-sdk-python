"""Typed output contracts at the HTTP boundary, for both clients."""

import subprocess
import sys
from collections.abc import Callable
from typing import Any, Literal

import httpx2
import msgspec
import pytest

pytest.importorskip("pydantic")
from pydantic import BaseModel, Field, ValidationError

from tests.conftest import ClientFactory
from typesafe_sdk import AsyncTypeSafeClient, Choice, SystemOneResponse, TypeSafeError
from typesafe_sdk._core import endpoints


class Ticket(BaseModel):
    category: Literal["billing", "technical"] = Field(description="What is this ticket about?")


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
                "category": {"type": "choice", "choice": category, "confidence": 0.9, "probabilities": {"billing": 0.9, "technical": 0.1}}
            },
        },
    )


@pytest.mark.parametrize("input_name", ["input", "state"])
async def test_typed_round_trip(clients: ClientFactory, input_name: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert msgspec.json.decode(request.content) == {
            "state": "I was charged twice.",
            "model": "jev-latest",
            "questions": {
                "category": {
                    "type": "choice",
                    "instructions": "What is this ticket about?",
                    "criteria": {"billing": None, "technical": None},
                }
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
        ({"input": "x", "questions": {}, "response_model": Ticket}, "either response_model or questions"),
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


def test_base_sdk_without_pydantic() -> None:
    # A fresh process prevents already-imported Pydantic modules from hiding an eager import.
    program = """
import importlib.abc
import sys
class NoPydantic(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "pydantic" or fullname.startswith("pydantic."):
            raise AssertionError("Base SDK imported Pydantic")
sys.meta_path.insert(0, NoPydantic())
from typesafe_sdk import TypeSafeClient, AsyncTypeSafeClient, Noul
import httpx2
import asyncio
response = {"model": "jev-latest", "usage": {}, "answers": {"q": {"type": "noul", "noul": 0.7}}}
with TypeSafeClient(api_key="test", transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=response))) as client:
    assert client.system_one("x", {"q": Noul()}).nouls["q"].noul == 0.7
async def main():
    async with AsyncTypeSafeClient(api_key="test", transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=response))) as client:
        assert (await client.system_one("x", {"q": Noul()})).nouls["q"].noul == 0.7
asyncio.run(main())
"""
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr


async def test_missing_extra_has_install_hint(clients: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> None:
        return None

    monkeypatch.setattr(endpoints, "find_spec", missing)
    with pytest.raises(TypeSafeError, match=r"typesafe-sdk\[pydantic\]"):
        await call(clients, lambda _: pytest.fail("Unexpected request"), input="x", response_model=Ticket)
