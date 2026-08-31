from openai import OpenAI

from app.core.config import settings


class AIService:

    def __init__(self):

        self.client = OpenAI(
            api_key=settings.openai_api_key
        )

    def analyze_market(
        self,
        symbol: str,
        market_data: dict,
    ):

        response = self.client.responses.create(

            model=settings.openai_model,

            input=[
                {
                    "role": "system",
                    "content": (
                        "You are Trade Pilot AI, an "
                        "AI trading analyst operating "
                        "in a paper-trading environment. "
                        "Analyze market information "
                        "carefully. Never claim certainty."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Analyze this market.

Symbol:
{symbol}

Market data:
{market_data}

Determine whether the current setup suggests:

BUY
SELL
HOLD

Confidence must be between 0 and 1.

Risk score must be between 0 and 1.

Give a concise explanation.
""",
                },
            ],

            text={
                "format": {
                    "type": "json_schema",
                    "name": "trade_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "decision": {
                                "type": "string",
                                "enum": [
                                    "BUY",
                                    "SELL",
                                    "HOLD",
                                ],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "risk_score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "reasoning": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "decision",
                            "confidence",
                            "risk_score",
                            "reasoning",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
        )

        return response.output_text


ai_service = AIService()