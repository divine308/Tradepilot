# class RiskAgent:

#     MAX_POSITION_PERCENT = 0.05
#     MIN_CONFIDENCE = 0.60
#     MAX_RISK_SCORE = 0.70

#     def evaluate(
#         self,
#         account_equity: float,
#         trade_value: float,
#         confidence: float,
#         risk_score: float,
#     ):

#         if account_equity <= 0:
#             return {
#                 "approved": False,
#                 "reason": "Invalid account equity.",
#             }

#         exposure = (
#             trade_value /
#             account_equity
#         )

#         if exposure > self.MAX_POSITION_PERCENT:
#             return {
#                 "approved": False,
#                 "reason": (
#                     "Trade exceeds the maximum "
#                     "5% portfolio exposure."
#                 ),
#             }

#         if confidence < self.MIN_CONFIDENCE:
#             return {
#                 "approved": False,
#                 "reason": (
#                     "AI confidence is below "
#                     "the minimum threshold."
#                 ),
#             }

#         if risk_score > self.MAX_RISK_SCORE:
#             return {
#                 "approved": False,
#                 "reason": (
#                     "AI risk score is above "
#                     "the permitted threshold."
#                 ),
#             }

#         return {
#             "approved": True,
#             "reason": "Risk limits passed.",
#             "exposure": exposure,
#         }


# risk_agent = RiskAgent()


class RiskAgent:

    # ============================================================
    # RISK CONFIGURATION
    # ============================================================

    MAX_POSITION_PERCENT = 0.05

    MIN_CONFIDENCE = 0.60
    MAX_RISK_SCORE = 0.70

    STOP_LOSS_PERCENT = 0.02
    TAKE_PROFIT_PERCENT = 0.04

    BREAKEVEN_TRIGGER_PERCENT = 0.02
    BREAKEVEN_OFFSET_PERCENT = 0.0005

    # ============================================================
    # TRADE EVALUATION
    # ============================================================

    def evaluate(
        self,
        account_equity: float,
        trade_value: float,
        confidence: float,
        risk_score: float,
        existing_exposure: float = 0.0,
    ):

        if account_equity <= 0:

            return {
                "approved": False,
                "reason": "Invalid account equity.",
            }

        if trade_value <= 0:

            return {
                "approved": False,
                "reason": "Invalid trade value.",
            }

        # --------------------------------------------------------
        # NEW TRADE EXPOSURE
        # --------------------------------------------------------

        exposure = (
            trade_value /
            account_equity
        )

        # --------------------------------------------------------
        # EXISTING PORTFOLIO EXPOSURE
        # --------------------------------------------------------

        total_exposure = (
            existing_exposure +
            exposure
        )

        if exposure > self.MAX_POSITION_PERCENT:

            return {
                "approved": False,
                "reason": (
                    "Trade exceeds the maximum "
                    "5% position size."
                ),
                "exposure": exposure,
            }

        # --------------------------------------------------------
        # AI CONFIDENCE
        # --------------------------------------------------------

        if confidence < self.MIN_CONFIDENCE:

            return {
                "approved": False,
                "reason": (
                    "AI confidence is below "
                    "the minimum threshold."
                ),
                "exposure": exposure,
            }

        # --------------------------------------------------------
        # AI RISK SCORE
        # --------------------------------------------------------

        if risk_score > self.MAX_RISK_SCORE:

            return {
                "approved": False,
                "reason": (
                    "AI risk score is above "
                    "the permitted threshold."
                ),
                "exposure": exposure,
            }

        # --------------------------------------------------------
        # APPROVED
        # --------------------------------------------------------

        return {
            "approved": True,
            "reason": "Risk limits passed.",
            "exposure": exposure,
            "existing_exposure": existing_exposure,
            "total_exposure": total_exposure,

            "stop_loss_percent": (
                self.STOP_LOSS_PERCENT
            ),

            "take_profit_percent": (
                self.TAKE_PROFIT_PERCENT
            ),

            "breakeven_trigger_percent": (
                self.BREAKEVEN_TRIGGER_PERCENT
            ),
        }


risk_agent = RiskAgent()