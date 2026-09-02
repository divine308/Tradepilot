from app.agents.market_agent import market_agent
from app.agents.strategy_agent import strategy_agent
from app.agents.risk_agent import risk_agent
from app.services.alpaca_service import alpaca_service


class SupervisorAgent:

    # ============================================================
    # ANALYZE
    # ============================================================

    def analyze(self, symbol: str):

        symbol = symbol.upper().strip()

        # --------------------------------------------------------
        # 1. MARKET ANALYSIS
        # --------------------------------------------------------

        market = market_agent.analyze(symbol)

        if not market.get("available"):

            return {
                "symbol": symbol,
                "status": "analysis_failed",
                "reason": market.get(
                    "reason",
                    "Market data unavailable.",
                ),
            }

        # --------------------------------------------------------
        # 2. STRATEGY ANALYSIS
        # --------------------------------------------------------

        strategy = strategy_agent.decide(
            symbol,
            market,
        )

        return {
            "symbol": symbol,
            "status": "analysis_complete",
            "market": market,
            "strategy": strategy,
        }

    # ============================================================
    # EXISTING PORTFOLIO EXPOSURE
    # ============================================================

    def _get_existing_exposure(
        self,
        account_equity: float,
    ):

        if account_equity <= 0:
            return 0.0

        try:

            positions = (
                alpaca_service.get_positions()
            )

        except Exception:

            # Fail closed.
            # If we cannot determine existing exposure,
            # do not assume the portfolio is empty.
            return None

        total_market_value = 0.0

        for position in positions:

            try:

                market_value = float(
                    position.market_value
                )

                # Only count long exposure.
                if market_value > 0:
                    total_market_value += market_value

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                continue

        return (
            total_market_value /
            account_equity
        )

    # ============================================================
    # EXECUTE TRADE
    # ============================================================

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ):

        symbol = symbol.upper().strip()
        side = side.lower().strip()

        # --------------------------------------------------------
        # BASIC VALIDATION
        # --------------------------------------------------------

        if side not in {"buy", "sell"}:

            return {
                "executed": False,
                "reason": (
                    "Invalid order side. "
                    "Use buy or sell."
                ),
            }

        if quantity <= 0:

            return {
                "executed": False,
                "reason": (
                    "Quantity must be greater than zero."
                ),
            }

        # --------------------------------------------------------
        # 1. ACCOUNT
        # --------------------------------------------------------

        try:

            account = alpaca_service.get_account()

            equity = float(
                account.equity
            )

        except Exception as exc:

            return {
                "executed": False,
                "reason": (
                    "Unable to retrieve trading account."
                ),
                "error": str(exc),
            }

        if equity <= 0:

            return {
                "executed": False,
                "reason": (
                    "Invalid account equity."
                ),
            }

        # --------------------------------------------------------
        # 2. MARKET ANALYSIS
        # --------------------------------------------------------

        market = market_agent.analyze(
            symbol
        )

        if not market.get("available"):

            return {
                "executed": False,
                "reason": market.get(
                    "reason",
                    "Market data unavailable.",
                ),
            }

        # --------------------------------------------------------
        # 3. CURRENT PRICE
        # --------------------------------------------------------

        try:

            price = float(
                market["price"]["current"]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):

            return {
                "executed": False,
                "reason": (
                    "Unable to determine current market price."
                ),
            }

        if price <= 0:

            return {
                "executed": False,
                "reason": (
                    "Invalid market price."
                ),
            }

        trade_value = (
            price * quantity
        )

        # --------------------------------------------------------
        # 4. STRATEGY
        # --------------------------------------------------------

        strategy = strategy_agent.decide(
            symbol,
            market,
        )

        decision = str(
            strategy.get(
                "decision",
                "HOLD",
            )
        ).upper()

        confidence = float(
            strategy.get(
                "confidence",
                0.0,
            )
        )

        risk_score = float(
            strategy.get(
                "risk_score",
                1.0,
            )
        )

        quantitative_score = float(
            strategy.get(
                "quantitative_score",
                50.0,
            )
        )

        # --------------------------------------------------------
        # 5. STRATEGY MUST AGREE WITH REQUESTED SIDE
        # --------------------------------------------------------

        requested_decision = side.upper()

        if decision == "HOLD":

            return {
                "executed": False,
                "reason": (
                    "Strategy recommends HOLD. "
                    "No trade was executed."
                ),
                "strategy": strategy,
            }

        if decision != requested_decision:

            return {
                "executed": False,
                "reason": (
                    f"Requested {requested_decision}, "
                    f"but strategy recommends {decision}."
                ),
                "strategy": strategy,
            }

        # --------------------------------------------------------
        # 6. GET EXISTING EXPOSURE
        # --------------------------------------------------------

        existing_exposure = (
            self._get_existing_exposure(
                account_equity=equity,
            )
        )

        if existing_exposure is None:

            return {
                "executed": False,
                "reason": (
                    "Unable to determine existing "
                    "portfolio exposure. "
                    "Trade rejected for safety."
                ),
                "strategy": strategy,
            }

        # --------------------------------------------------------
        # 7. RISK MANAGEMENT
        # --------------------------------------------------------

        risk = risk_agent.evaluate(
            account_equity=equity,
            trade_value=trade_value,
            confidence=confidence,
            risk_score=risk_score,
            existing_exposure=existing_exposure,
        )

        if not risk.get("approved", False):

            return {
                "executed": False,
                "reason": (
                    "Trade rejected by risk management."
                ),
                "risk": risk,
                "strategy": strategy,
            }

        # --------------------------------------------------------
        # 8. EXECUTE
        # --------------------------------------------------------

        try:

            order = (
                alpaca_service.submit_market_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                )
            )

        except Exception as exc:

            return {
                "executed": False,
                "reason": (
                    "Order submission failed."
                ),
                "error": str(exc),
                "risk": risk,
                "strategy": strategy,
            }

        # --------------------------------------------------------
        # 9. RETURN COMPLETE RESULT
        # --------------------------------------------------------

        return {
            "executed": True,

            "order_id": str(
                order.id
            ),

            "symbol": symbol,

            "side": side,

            "quantity": quantity,

            "estimated_price": price,

            "estimated_value": trade_value,

            "strategy": strategy,

            "risk": risk,

            "market": {
                "price": price,

                "trend": market.get(
                    "trend"
                ),

                "quantitative_score": (
                    quantitative_score
                ),

                "signal_strength": (
                    market.get(
                        "quantitative_signal",
                        {},
                    ).get(
                        "strength"
                    )
                ),

                "rsi": market.get(
                    "momentum",
                    {},
                ).get(
                    "rsi_14"
                ),

                "macd": market.get(
                    "momentum",
                    {},
                ).get(
                    "macd"
                ),

                "macd_momentum": market.get(
                    "momentum",
                    {},
                ).get(
                    "macd_momentum"
                ),

                "structure": market.get(
                    "structure",
                    {},
                ).get(
                    "signal"
                ),
            },
        }


supervisor_agent = SupervisorAgent()