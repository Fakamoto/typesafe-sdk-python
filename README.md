# TypeSafe AI Python SDK

Python SDK for [TypeSafe AI](https://typesafe.ai).

## Quickstart

This fork adds inferred output models on top of the official v0.7.0 SDK.
Install this fork from main (Pydantic is already included):

```sh
uv add 'typesafe-sdk @ git+https://github.com/Fakamoto/typesafe-sdk-python.git@feat/1_pydantic_outputs'
```

Define the output once, then receive a validated instance of that model:

```python
from typing import Literal

from pydantic import BaseModel, Field
from typesafe_sdk import TypeSafeClient


class Ticket(BaseModel):
    category: Literal["billing", "technical", "other"] = Field(
        description="What is this ticket about?"
    )
    urgent: bool = Field(description="Does this need immediate attention?")


with TypeSafeClient() as client:
    result = client.system_one(
        input="I was charged twice.",
        response_model=Ticket,
    )

print(result.category, result.urgent)
```

`AsyncTypeSafeClient` accepts the same arguments with `await`. The result's static type is
the supplied model, so editors can complete `result.category`. `input` accepts text,
JSON objects, arrays, or a Pydantic model instance and is an alias for `state`; pass
exactly one of them. Input models use `model_dump(mode="json")`, including nested data
and JSON conversion of dates and enums. Models that serialize to scalar numbers,
booleans, or null are rejected.

```python
class TicketInput(BaseModel):
    message: str
    context: dict[str, list[str]]


with TypeSafeClient() as client:
    from_model = client.system_one(
        input=TicketInput(message="Charged twice", context={"tags": ["billing"]}),
        response_model=Ticket,
    )
    from_dict = client.system_one(
        input={"message": "Charged twice", "context": {"tags": ["billing"]}},
        response_model=Ticket,
    )
```

Supported fields map to Jev's existing primitives:

| Model field | Question | Model value |
| --- | --- | --- |
| String `Literal` or string-valued `Enum` | `Choice` | Selected literal or enum member |
| `bool` | `Noul` | `True` when the probability is at least 0.5 |
| `Annotated[float, Noul(...)]` | `Noul` | Probability from 0 to 1 |
| `Annotated[float, Score(criteria=[...])]` | `Score` | Expected score, possibly fractional |

Use `Field(description=...)` for instructions. For probabilities and scores, reuse
the existing question types as field metadata; their explicit instructions take precedence:

```python
from typing import Annotated

from pydantic import BaseModel, Field
from typesafe_sdk import Noul, Score


class TicketSignals(BaseModel):
    urgency: Annotated[float, Noul()] = Field(description="Does this need immediate attention?")
    sentiment: Annotated[float, Score(criteria=["negative", "neutral", "positive"])] = Field(
        description="What is the customer's sentiment?"
    )
```

For a different boolean threshold, request the probability and compare it in your code.
Field names identify questions internally, including when a field has a Pydantic alias.
Every declared field is requested; defaults do not replace missing API answers. Pydantic
constraints and validators run on the result, and their validation errors propagate.

Unsupported shapes (including free-form strings, bare numbers, unions, nested models,
lists, and root models) fail before a network request. This integration does not add
text generation or general JSON Schema support to Jev.

When `questions` is omitted, fields define questions and the result contains your model's
values. In this mode, `extra_body` cannot replace `state` or `questions`.

When `questions` is supplied, the official v0.7.0 behavior stays unchanged:
`response_model` validates the full response envelope (including nested answers).
Omit `response_model` to receive `SystemOneResponse`, with confidence, probability
distributions, token usage, and the raw HTTP response.

To run the offline tests with this integration installed:

```sh
uv sync
uv run pytest -m 'not integration'
uv run pyrefly check
```

## Documentation

Learn more in [SDK docs](https://docs.typesafe.ai/sdk/python/).
