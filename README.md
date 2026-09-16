# TypeSafe AI Python SDK

Python SDK for [TypeSafe AI](https://typesafe.ai).

## Quickstart

Install the SDK:

```
uv add typesafe-sdk
```

Set `TYPESAFE_API_KEY` in your environment, then instantiate and use the client:

```python
from typesafe_sdk import Choice, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state={"document": "I was charged twice. Please fix this ASAP."},
        questions={
            "category": Choice(
                instructions="What is this ticket about?",
                criteria={"billing": None, "technical": None, "other": None},
            ),
        },
    )

print(response.choices["category"].choice)
```

learn what TypeSafe is, what it can do, and how to use it in [TypeSafe docs](https://docs.typesafe.ai/).

## Pydantic outputs

Install the optional Pydantic v2 integration:

```sh
uv add 'typesafe-sdk[pydantic]'
```

Define the output once, then receive a validated instance of that model:

```python
from typing import Literal

from pydantic import BaseModel, Field
from typesafe_sdk import TypeSafeClient


class TicketClassification(BaseModel):
    category: Literal["billing", "technical", "other"] = Field(
        description="What is this ticket about?"
    )


with TypeSafeClient() as client:
    result = client.system_one(
        input="I was charged twice.",
        response_model=TicketClassification,
    )

print(result.category)
```

`AsyncTypeSafeClient` accepts the same arguments with `await`. The result's static type is
the supplied model, so editors can complete `result.category`. `input` accepts text,
JSON objects, or arrays and is an alias for `state`; pass exactly one of them.

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

`response_model` and `questions` are mutually exclusive. With `response_model`,
`extra_body` cannot replace `state` or `questions`. The result contains only your model's
data; use the existing `questions` API when you need confidence, probability distributions,
token usage, or the raw HTTP response. Existing calls and msgspec response types are unchanged.

To run the offline tests with this integration installed:

```sh
uv sync --extra pydantic
uv run --extra pydantic pytest -m 'not integration'
uv run --extra pydantic pyrefly check
```

## Documentation

Learn more in [SDK docs](https://docs.typesafe.ai/sdk/python/).
