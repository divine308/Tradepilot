import json

from app.services.ai_service import ai_service


class StrategyAgent:

    def decide(
        self,
        symbol: str,
        market_data: dict,
    ):

        raw_result = ai_service.analyze_market(
            symbol,
            market_data,
        )

        result = json.loads(raw_result)

        return {
            "symbol": symbol.upper(),
            "decision": result["decision"],
            "confidence": float(
                result["confidence"]
            ),
            "risk_score": float(
                result["risk_score"]
            ),
            "reasoning": result["reasoning"],
        }


strategy_agent = StrategyAgent()