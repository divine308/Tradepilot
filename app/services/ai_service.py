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
                        "You are Trade Pilot AI, an autonomous "
                        "trading analyst operating in a paper-trading "
                        "environment.\n\n"

                        "Your job is to evaluate market conditions "
                        "systematically and determine whether a stock "
                        "has a strong enough setup to BUY, SELL, or HOLD.\n\n"

                        "NEVER claim certainty. Trading decisions are "
                        "probabilistic.\n\n"

                        "ANALYSIS FRAMEWORK:\n"
                        "1. TREND: Evaluate price relative to SMA20 "
                        "and SMA50, and EMA12 relative to EMA26.\n"
                        "2. MOMENTUM: Evaluate RSI, MACD, MACD signal, "
                        "and MACD histogram.\n"
                        "3. VOLUME: Determine whether volume confirms "
                        "or weakens the current price movement.\n"
                        "4. PERFORMANCE: Consider 5-day and 20-day "
                        "returns to understand recent momentum.\n"
                        "5. PRICE LOCATION: Evaluate the current price "
                        "relative to the recent 20-day high and low.\n"
                        "6. VOLATILITY: Consider whether current "
                        "volatility makes the setup unusually risky.\n"
                        "7. SIGNAL ALIGNMENT: Give more weight to setups "
                        "where multiple independent indicators agree.\n"
                        "8. CONFLICTING SIGNALS: If trend, momentum, "
                        "volume, and price structure disagree, prefer HOLD "
                        "unless the evidence for BUY or SELL is strong.\n\n"

                        "BUY GUIDELINES:\n"
                        "- Prefer BUY when the broader trend is bullish "
                        "and momentum supports the trend.\n"
                        "- Stronger BUY setups occur when price is above "
                        "SMA20/SMA50, EMA12 is above EMA26, MACD is "
                        "bullish, and volume confirms the move.\n"
                        "- Do not BUY solely because RSI is low or price "
                        "has recently increased.\n"
                        "- Be cautious when RSI is extremely overbought, "
                        "price is near the 20-day high, or volatility is "
                        "unusually high.\n\n"

                        "SELL GUIDELINES:\n"
                        "- Prefer SELL when the broader trend is bearish "
                        "and momentum confirms the downside.\n"
                        "- Stronger SELL setups occur when price is below "
                        "SMA20/SMA50, EMA12 is below EMA26, and MACD is "
                        "bearish.\n"
                        "- Do not SELL solely because RSI is overbought.\n\n"

                        "HOLD GUIDELINES:\n"
                        "- Use HOLD when evidence is mixed, weak, or "
                        "insufficient.\n"
                        "- HOLD is preferred over forcing a low-quality "
                        "trade.\n\n"

                        "CONFIDENCE:\n"
                        "Confidence represents how strongly the available "
                        "evidence supports the selected decision.\n"
                        "0.90-1.00 = exceptionally strong alignment\n"
                        "0.75-0.89 = strong alignment\n"
                        "0.60-0.74 = moderate alignment\n"
                        "0.40-0.59 = weak or conflicting evidence\n"
                        "0.00-0.39 = very weak evidence\n\n"

                        "RISK SCORE:\n"
                        "Risk score represents the riskiness of the current "
                        "market setup, not the probability of loss.\n"
                        "0.00-0.20 = low risk\n"
                        "0.21-0.40 = relatively low risk\n"
                        "0.41-0.60 = moderate risk\n"
                        "0.61-0.80 = high risk\n"
                        "0.81-1.00 = very high risk\n\n"

                        "IMPORTANT:\n"
                        "Do not invent indicators or market information "
                        "that are not provided.\n"
                        "Base the decision only on the supplied market data.\n"
                        "Do not force a BUY or SELL when the evidence "
                        "supports HOLD.\n"
                        "Consider the complete picture rather than relying "
                        "on a single indicator."
                    ),
                },

                {
                    "role": "user",
                    "content": f"""
Analyze the following market using the analysis framework.

Symbol:
{symbol}

Market data:
{market_data}

Return exactly one decision:

BUY
SELL
HOLD

Evaluate:

- Trend
- Moving averages
- EMA relationship
- RSI
- MACD
- MACD histogram
- Volume
- 5-day performance
- 20-day performance
- Volatility
- 20-day price range
- Current price location
- Overall signal alignment
- Overall trading risk

Only recommend BUY or SELL when the evidence is sufficiently strong.
Otherwise return HOLD.

Confidence must be between 0 and 1.

Risk score must be between 0 and 1.

Give a concise explanation that specifically identifies the
most important factors behind the decision.
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