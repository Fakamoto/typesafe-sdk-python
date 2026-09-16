from typing import Literal

from pydantic import BaseModel
from typing_extensions import assert_type

from typesafe_sdk import AsyncTypeSafeClient, Noul, SystemOneResponse, TypeSafeClient


class Ticket(BaseModel):
    category: Literal["billing", "technical"]


def sync(client: TypeSafeClient) -> None:
    assert_type(client.system_one(input="x", response_model=Ticket), Ticket)
    assert_type(client.system_one("x", response_model=Ticket), Ticket)
    assert_type(client.system_one(input="x", questions={"q": Noul()}), SystemOneResponse)


async def asynchronous(client: AsyncTypeSafeClient) -> None:
    assert_type(await client.system_one(input="x", response_model=Ticket), Ticket)
    assert_type(await client.system_one(state="x", response_model=Ticket), Ticket)
    assert_type(await client.system_one(input="x", questions={"q": Noul()}), SystemOneResponse)
