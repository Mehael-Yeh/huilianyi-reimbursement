"""Public structured inputs used by the SDK and MCP schema generator."""

from pydantic import BaseModel, Field


class TravelBudgetLine(BaseModel):
    expenseType: str = Field(min_length=1, description="Exact Huilianyi expense-type name")
    amount: float = Field(gt=0, description="Positive planned amount in the report currency")
