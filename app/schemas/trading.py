from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
        max_length=10,
    )


class TradeRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
        max_length=10,
    )

    side: Literal["buy", "sell"]

    quantity: float = Field(
        gt=0,
    )


class AgentDecision(BaseModel):
    symbol: str
    decision: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    reasoning: str
    risk_score: float