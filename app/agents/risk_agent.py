class RiskAgent:

    MAX_POSITION_PERCENT = 0.05
    MIN_CONFIDENCE = 0.60
    MAX_RISK_SCORE = 0.70

    def evaluate(
        self,
        account_equity: float,
        trade_value: float,
        confidence: float,
        risk_score: float,
    ):

        if account_equity <= 0:
            return {
                "approved": False,
                "reason": "Invalid account equity.",
            }

        exposure = (
            trade_value /
            account_equity
        )

        if exposure > self.MAX_POSITION_PERCENT:
            return {
                "approved": False,
                "reason": (
                    "Trade exceeds the maximum "
                    "5% portfolio exposure."
                ),
            }

        if confidence < self.MIN_CONFIDENCE:
            return {
                "approved": False,
                "reason": (
                    "AI confidence is below "
                    "the minimum threshold."
                ),
            }

        if risk_score > self.MAX_RISK_SCORE:
            return {
                "approved": False,
                "reason": (
                    "AI risk score is above "
                    "the permitted threshold."
                ),
            }

        return {
            "approved": True,
            "reason": "Risk limits passed.",
            "exposure": exposure,
        }


risk_agent = RiskAgent()