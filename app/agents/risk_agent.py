class RiskAgent:

    # ============================================================
    # PORTFOLIO RISK CONFIGURATION
    # ============================================================

    # Maximum size of ONE new position
    MAX_POSITION_PERCENT = 0.05

    # Maximum combined exposure across all open positions
    MAX_TOTAL_EXPOSURE_PERCENT = 0.50

    # Only accept reasonably strong AI setups
    MIN_CONFIDENCE = 0.70

    # Reject setups with excessive risk
    MAX_RISK_SCORE = 0.50

    # ============================================================
    # POSITION PROTECTION
    # ============================================================

    STOP_LOSS_PERCENT = 0.04
    TAKE_PROFIT_PERCENT = 0.30

    # Move protection after the trade reaches +10%
    BREAKEVEN_TRIGGER_PERCENT = 0.10

    # Lock approximately +0.5% above entry
    BREAKEVEN_OFFSET_PERCENT = 0.005

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

        # --------------------------------------------------------
        # BASIC VALIDATION
        # --------------------------------------------------------

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
        # NORMALIZE AI VALUES
        # --------------------------------------------------------

        try:
            confidence = float(confidence)
            risk_score = float(risk_score)
            existing_exposure = float(existing_exposure)
        except (TypeError, ValueError):

            return {
                "approved": False,
                "reason": "Invalid risk or confidence values.",
            }

        # AI outputs must remain inside valid ranges
        if not 0.0 <= confidence <= 1.0:

            return {
                "approved": False,
                "reason": "AI confidence is outside the valid range.",
            }

        if not 0.0 <= risk_score <= 1.0:

            return {
                "approved": False,
                "reason": "AI risk score is outside the valid range.",
            }

        if existing_exposure < 0:

            return {
                "approved": False,
                "reason": "Invalid existing portfolio exposure.",
            }

        # --------------------------------------------------------
        # NEW POSITION EXPOSURE
        # --------------------------------------------------------

        exposure = (
            trade_value /
            account_equity
        )

        # --------------------------------------------------------
        # INDIVIDUAL POSITION LIMIT
        # --------------------------------------------------------

        if exposure > self.MAX_POSITION_PERCENT:

            return {
                "approved": False,
                "reason": (
                    "Trade exceeds the maximum "
                    "5% position size."
                ),
                "exposure": exposure,
                "existing_exposure": existing_exposure,
            }

        # --------------------------------------------------------
        # TOTAL PORTFOLIO EXPOSURE
        # --------------------------------------------------------

        total_exposure = (
            existing_exposure +
            exposure
        )

        if (
            total_exposure >
            self.MAX_TOTAL_EXPOSURE_PERCENT
        ):

            return {
                "approved": False,
                "reason": (
                    "Trade would exceed the maximum "
                    "50% total portfolio exposure."
                ),
                "exposure": exposure,
                "existing_exposure": existing_exposure,
                "total_exposure": total_exposure,
            }

        # --------------------------------------------------------
        # AI CONFIDENCE FILTER
        # --------------------------------------------------------

        if confidence < self.MIN_CONFIDENCE:

            return {
                "approved": False,
                "reason": (
                    "AI confidence is below the "
                    "70% minimum threshold."
                ),
                "exposure": exposure,
                "confidence": confidence,
            }

        # --------------------------------------------------------
        # AI RISK FILTER
        # --------------------------------------------------------

        if risk_score > self.MAX_RISK_SCORE:

            return {
                "approved": False,
                "reason": (
                    "AI risk score is above the "
                    "50% maximum threshold."
                ),
                "exposure": exposure,
                "risk_score": risk_score,
            }

        # --------------------------------------------------------
        # APPROVED
        # --------------------------------------------------------

        return {
            "approved": True,

            "reason": "Risk limits passed.",

            # Exposure information
            "exposure": exposure,
            "existing_exposure": existing_exposure,
            "total_exposure": total_exposure,

            # AI quality
            "confidence": confidence,
            "risk_score": risk_score,

            # Position protection
            "stop_loss_percent": (
                self.STOP_LOSS_PERCENT
            ),

            "take_profit_percent": (
                self.TAKE_PROFIT_PERCENT
            ),

            "breakeven_trigger_percent": (
                self.BREAKEVEN_TRIGGER_PERCENT
            ),

            "breakeven_offset_percent": (
                self.BREAKEVEN_OFFSET_PERCENT
            ),
        }


risk_agent = RiskAgent()