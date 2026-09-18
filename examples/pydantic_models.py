"""Run with TYPESAFE_API_KEY set: uv run examples/pydantic_models.py."""

from typing import Literal

from pydantic import BaseModel, Field

from typesafe_sdk import TypeSafeClient


class Ticket(BaseModel):
    category: Literal["billing", "technical", "other"] = Field(description="What is this ticket about?")
    urgent: bool = Field(description="Does this need immediate attention?")


class TicketInput(BaseModel):
    message: str
    context: dict[str, list[str]]


if __name__ == "__main__":
    with TypeSafeClient() as client:
        text_result = client.system_one(input="I was charged twice. Please fix this ASAP.", response_model=Ticket)
        model_result = client.system_one(
            input=TicketInput(message="Charged twice", context={"tags": ["billing"]}), response_model=Ticket
        )
        dict_result = client.system_one(input={"message": "Charged twice", "context": {"tags": ["billing"]}}, response_model=Ticket)
    for result in (text_result, model_result, dict_result):
        print(result.category, result.urgent)
