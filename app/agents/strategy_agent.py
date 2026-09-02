import json

from app.services.ai_service import ai_service


class StrategyAgent:

    # ============================================================
    # STRATEGY CONFIGURATION
    # ============================================================

    # Minimum quantitative score required for a BUY
    MIN_BUY_SCORE = 70

    # Minimum quantitative score required for a SELL
    MIN_SELL_SCORE = 30

    # AI confidence required for an actionable signal
    MIN_CONFIDENCE = 0.70

    # Maximum acceptable AI risk
    MAX_RISK_SCORE = 0.50

    # ============================================================
    # DECISION
    # ============================================================

    def decide(
        self,
        symbol: str,
        market_data: dict,
    ):

        symbol = symbol.upper().strip()

        # --------------------------------------------------------
        # MARKET DATA VALIDATION
        # --------------------------------------------------------

        if not market_data.get("available", False):

            return {
                "symbol": symbol,
                "decision": "HOLD",
                "confidence": 0.0,
                "risk_score": 1.0,
                "reasoning": (
                    "Market data is unavailable. "
                    "No trade should be taken."
                ),
                "quantitative_score": 0,
                "signal_strength": "UNAVAILABLE",
            }

        # --------------------------------------------------------
        # GET QUANTITATIVE SIGNAL
        # --------------------------------------------------------

        quantitative_data = (
            market_data.get(
                "quantitative_signal",
                {},
            )
        )

        quantitative_score = float(
            quantitative_data.get(
                "score",
                50,
            )
        )

        signal_strength = quantitative_data.get(
            "strength",
            "NEUTRAL",
        )

        # --------------------------------------------------------
        # AI ANALYSIS
        # --------------------------------------------------------

        try:

            raw_result = ai_service.analyze_market(
                symbol,
                market_data,
            )

            result = json.loads(raw_result)

        except Exception as exc:

            return {
                "symbol": symbol,
                "decision": "HOLD",
                "confidence": 0.0,
                "risk_score": 1.0,
                "reasoning": (
                    "AI analysis failed. "
                    "Trade rejected safely. "
                    f"Error: {str(exc)}"
                ),
                "quantitative_score": quantitative_score,
                "signal_strength": signal_strength,
            }

        # --------------------------------------------------------
        # NORMALIZE AI VALUES
        # --------------------------------------------------------

        ai_decision = str(
            result.get(
                "decision",
                "HOLD",
            )
        ).upper()

        confidence = float(
            result.get(
                "confidence",
                0.0,
            )
        )

        risk_score = float(
            result.get(
                "risk_score",
                1.0,
            )
        )

        reasoning = str(
            result.get(
                "reasoning",
                "",
            )
        )

        # --------------------------------------------------------
        # VALIDATE AI OUTPUT
        # --------------------------------------------------------

        if ai_decision not in {
            "BUY",
            "SELL",
            "HOLD",
        }:

            return {
                "symbol": symbol,
                "decision": "HOLD",
                "confidence": confidence,
                "risk_score": risk_score,
                "reasoning": (
                    "Invalid AI decision. "
                    "Trade rejected safely."
                ),
                "quantitative_score": quantitative_score,
                "signal_strength": signal_strength,
            }

        if not 0.0 <= confidence <= 1.0:

            return {
                "symbol": symbol,
                "decision": "HOLD",
                "confidence": 0.0,
                "risk_score": risk_score,
                "reasoning": (
                    "Invalid AI confidence. "
                    "Trade rejected safely."
                ),
                "quantitative_score": quantitative_score,
                "signal_strength": signal_strength,
            }

        if not 0.0 <= risk_score <= 1.0:

            return {
                "symbol": symbol,
                "decision": "HOLD",
                "confidence": confidence,
                "risk_score": 1.0,
                "reasoning": (
                    "Invalid AI risk score. "
                    "Trade rejected safely."
                ),
                "quantitative_score": quantitative_score,
                "signal_strength": signal_strength,
            }

        # ========================================================
        # FINAL STRATEGY FILTER
        # ========================================================

        final_decision = "HOLD"
        rejection_reason = None

        # --------------------------------------------------------
        # AI HOLD
        # --------------------------------------------------------

        if ai_decision == "HOLD":

            final_decision = "HOLD"

            rejection_reason = (
                "AI does not see a sufficiently strong setup."
            )

        # --------------------------------------------------------
        # BUY
        # --------------------------------------------------------

        elif ai_decision == "BUY":

            if quantitative_score < self.MIN_BUY_SCORE:

                final_decision = "HOLD"

                rejection_reason = (
                    "AI suggested BUY, but the "
                    f"quantitative score ({quantitative_score:.1f}) "
                    "is below the 70 threshold."
                )

            elif confidence < self.MIN_CONFIDENCE:

                final_decision = "HOLD"

                rejection_reason = (
                    "BUY rejected because AI confidence "
                    "is below 70%."
                )

            elif risk_score > self.MAX_RISK_SCORE:

                final_decision = "HOLD"

                rejection_reason = (
                    "BUY rejected because AI risk "
                    "score is above 50%."
                )

            else:

                final_decision = "BUY"

        # --------------------------------------------------------
        # SELL
        # --------------------------------------------------------

        elif ai_decision == "SELL":

            if quantitative_score > self.MIN_SELL_SCORE:

                final_decision = "HOLD"

                rejection_reason = (
                    "AI suggested SELL, but the "
                    f"quantitative score ({quantitative_score:.1f}) "
                    "does not confirm a sufficiently bearish setup."
                )

            elif confidence < self.MIN_CONFIDENCE:

                final_decision = "HOLD"

                rejection_reason = (
                    "SELL rejected because AI confidence "
                    "is below 70%."
                )

            elif risk_score > self.MAX_RISK_SCORE:

                final_decision = "HOLD"

                rejection_reason = (
                    "SELL rejected because AI risk "
                    "score is above 50%."
                )

            else:

                final_decision = "SELL"

        # ========================================================
        # FINAL REASONING
        # ========================================================

        if final_decision == "HOLD" and rejection_reason:

            final_reasoning = (
                reasoning
                + " "
                + rejection_reason
            )

        else:

            final_reasoning = reasoning

        # ========================================================
        # RETURN COMPLETE STRATEGY
        # ========================================================

        return {
            "symbol": symbol,

            "decision": final_decision,

            "ai_decision": ai_decision,

            "confidence": confidence,

            "risk_score": risk_score,

            "quantitative_score": quantitative_score,

            "signal_strength": signal_strength,

            "reasoning": final_reasoning,

            "filters": {
                "minimum_buy_score": (
                    self.MIN_BUY_SCORE
                ),

                "maximum_sell_score": (
                    self.MIN_SELL_SCORE
                ),

                "minimum_confidence": (
                    self.MIN_CONFIDENCE
                ),

                "maximum_risk_score": (
                    self.MAX_RISK_SCORE
                ),
            },
        }


strategy_agent = StrategyAgent()