# from app.agents.market_agent import market_agent
# from app.agents.strategy_agent import strategy_agent
# from app.agents.risk_agent import risk_agent
# from app.services.alpaca_service import alpaca_service


# class SupervisorAgent:

#     def analyze(self, symbol: str):

#         symbol = symbol.upper()

#         market = market_agent.analyze(
#             symbol
#         )

#         if not market.get("available"):
#             return {
#                 "symbol": symbol,
#                 "status": "analysis_failed",
#                 "reason": "Market data unavailable.",
#             }

#         strategy = strategy_agent.decide(
#             symbol,
#             market,
#         )

#         return {
#             "symbol": symbol,
#             "market": market,
#             "strategy": strategy,
#             "status": "analysis_complete",
#         }

#     def execute(
#         self,
#         symbol: str,
#         side: str,
#         quantity: float,
#     ):

#         symbol = symbol.upper()
#         side = side.lower()

#         if side not in {"buy", "sell"}:
#             return {
#                 "executed": False,
#                 "reason": "Invalid order side.",
#             }

#         if quantity <= 0:
#             return {
#                 "executed": False,
#                 "reason": "Quantity must be greater than zero.",
#             }

#         account = alpaca_service.get_account()

#         equity = float(
#             account.equity
#         )

#         market = market_agent.analyze(
#             symbol
#         )

#         if not market.get("available"):
#             return {
#                 "executed": False,
#                 "reason": "Market data unavailable.",
#             }

#         price = float(
#             market["close"]
#         )

#         trade_value = price * quantity

#         # Manual execution still goes through
#         # the portfolio exposure limit.
#         risk = risk_agent.evaluate(
#             account_equity=equity,
#             trade_value=trade_value,
#             confidence=1.0,
#             risk_score=0.0,
#         )

#         if not risk["approved"]:
#             return {
#                 "executed": False,
#                 "risk": risk,
#             }

#         order = alpaca_service.submit_market_order(
#             symbol=symbol,
#             side=side,
#             quantity=quantity,
#         )

#         return {
#             "executed": True,
#             "risk": risk,
#             "order_id": str(order.id),
#             "symbol": symbol,
#             "side": side,
#             "quantity": quantity,
#             "estimated_price": price,
#             "estimated_value": trade_value,
#         }


# supervisor_agent = SupervisorAgent()



from app.agents.market_agent import market_agent
from app.agents.strategy_agent import strategy_agent
from app.agents.risk_agent import risk_agent
from app.services.alpaca_service import alpaca_service


class SupervisorAgent:

    def analyze(self, symbol: str):

        symbol = symbol.upper().strip()

        # --------------------------------------------------
        # 1. MARKET ANALYSIS
        # --------------------------------------------------

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

        # --------------------------------------------------
        # 2. AI STRATEGY
        # --------------------------------------------------

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

    # ======================================================
    # EXECUTE TRADE
    # ======================================================

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ):

        symbol = symbol.upper().strip()
        side = side.lower().strip()

        # --------------------------------------------------
        # BASIC VALIDATION
        # --------------------------------------------------

        if side not in {"buy", "sell"}:
            return {
                "executed": False,
                "reason": "Invalid order side. Use buy or sell.",
            }

        if quantity <= 0:
            return {
                "executed": False,
                "reason": "Quantity must be greater than zero.",
            }

        # --------------------------------------------------
        # 1. GET ACCOUNT
        # --------------------------------------------------

        account = alpaca_service.get_account()

        equity = float(account.equity)

        if equity <= 0:
            return {
                "executed": False,
                "reason": "Invalid account equity.",
            }

        # --------------------------------------------------
        # 2. RE-ANALYZE MARKET
        # --------------------------------------------------

        market = market_agent.analyze(symbol)

        if not market.get("available"):
            return {
                "executed": False,
                "reason": "Market data unavailable.",
            }

        # --------------------------------------------------
        # 3. GET CURRENT PRICE
        # --------------------------------------------------

        price = float(
            market["price"]["current"]
        )

        trade_value = price * quantity

        # --------------------------------------------------
        # 4. GET AI STRATEGY
        # --------------------------------------------------

        strategy = strategy_agent.decide(
            symbol,
            market,
        )

        decision = strategy["decision"]
        confidence = float(
            strategy["confidence"]
        )
        risk_score = float(
            strategy["risk_score"]
        )

        # --------------------------------------------------
        # 5. MAKE SURE REQUESTED SIDE MATCHES AI DECISION
        # --------------------------------------------------

        requested_decision = side.upper()

        if decision == "HOLD":

            return {
                "executed": False,
                "reason": (
                    "AI strategy recommends HOLD. "
                    "No trade was executed."
                ),
                "strategy": strategy,
            }

        if decision != requested_decision:

            return {
                "executed": False,
                "reason": (
                    f"Requested {requested_decision}, "
                    f"but AI strategy recommends {decision}."
                ),
                "strategy": strategy,
            }

        # --------------------------------------------------
        # 6. RISK CHECK
        # --------------------------------------------------

        risk = risk_agent.evaluate(
            account_equity=equity,
            trade_value=trade_value,
            confidence=confidence,
            risk_score=risk_score,
        )

        if not risk["approved"]:

            return {
                "executed": False,
                "reason": "Trade rejected by risk management.",
                "risk": risk,
                "strategy": strategy,
            }

        # --------------------------------------------------
        # 7. EXECUTE THROUGH ALPACA
        # --------------------------------------------------

        order = alpaca_service.submit_market_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
        )

        # --------------------------------------------------
        # 8. RETURN COMPLETE TRADE RESULT
        # --------------------------------------------------

        return {
            "executed": True,

            "order_id": str(order.id),

            "symbol": symbol,

            "side": side,

            "quantity": quantity,

            "estimated_price": price,

            "estimated_value": trade_value,

            "strategy": strategy,

            "risk": risk,

            "market": {
                "price": price,
                "trend": market.get("trend"),
                "rsi": market.get(
                    "momentum",
                    {},
                ).get("rsi_14"),
                "macd": market.get(
                    "momentum",
                    {},
                ).get("macd"),
            },
        }


supervisor_agent = SupervisorAgent()
