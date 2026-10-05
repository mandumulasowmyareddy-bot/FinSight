from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: str
    password: str


class TransactionInput(BaseModel):
    type: Literal["income", "expense"]
    amount: float = Field(gt=0, le=100_000_000)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=240)
    date: date
    payment_method: str = Field(default="Other", max_length=40)


class BudgetInput(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0, le=100_000_000)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class GoalInput(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    target_amount: float = Field(gt=0, le=100_000_000)
    current_amount: float = Field(default=0, ge=0, le=100_000_000)
    deadline: date | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
