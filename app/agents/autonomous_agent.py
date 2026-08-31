import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.agents.market_agent import market_agent
from app.agents.strategy_agent import strategy_agent
from app.agents.risk_agent import risk_agent
from app.core.config import settings
from app.database.database import AsyncSessionLocal
from app.models.autonomous_agent import (
    AutonomousAgentState,
)
from app.services.alpaca_service import alpaca_service


class AutonomousTradingAgent:

    # ============================================================
    # CONFIGURATION
    # ============================================================

    WATCHLIST = [
        "AAPL",
        "NVDA",
        "MSFT",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
    ]

    SCAN_INTERVAL_SECONDS = 300

    MAX_TRADE_PERCENT = 0.05

    MAX_TRADES_PER_SCAN = 1

    MAX_SESSION_TRADES = 10

    def __init__(self):

        self.running = False

        self.task: Optional[asyncio.Task] = None

        self.started_at = None
        self.last_scan_at = None
        self.last_trade_at = None

        self.scan_count = 0
        self.signals_count = 0
        self.trades_executed = 0
        self.trades_rejected = 0

        self.activity = []

        self.current_symbol = None
        self.current_stage = "IDLE"

        self.last_error = None

    # ============================================================
    # DATABASE STATE
    # ============================================================

    async def _set_persistent_enabled(
        self,
        enabled: bool,
    ):

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(
                    AutonomousAgentState
                ).where(
                    AutonomousAgentState.id == 1
                )
            )

            state = result.scalar_one_or_none()

            if state is None:

                state = AutonomousAgentState(
                    id=1,
                    enabled=enabled,
                    updated_at=datetime.now(
                        timezone.utc
                    ),
                )

                session.add(state)

            else:

                state.enabled = enabled

                state.updated_at = datetime.now(
                    timezone.utc
                )

            await session.commit()

    async def _get_persistent_enabled(self):

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(
                    AutonomousAgentState.enabled
                ).where(
                    AutonomousAgentState.id == 1
                )
            )

            enabled = result.scalar_one_or_none()

            if enabled is None:

                return False

            return bool(enabled)

    # ============================================================
    # ACTIVITY LOGGER
    # ============================================================

    def log(
        self,
        agent: str,
        action: str,
        symbol: Optional[str] = None,
        status: str = "success",
        details=None,
    ):

        item = {
            "time": datetime.now(
                timezone.utc
            ).isoformat(),

            "agent": agent,

            "action": action,

            "symbol": symbol,

            "status": status,

            "details": details,
        }

        self.activity.insert(
            0,
            item,
        )

        self.activity = self.activity[:100]

        return item

    # ============================================================
    # START
    # ============================================================

    async def start(
        self,
        persist: bool = True,
    ):

        if self.running:

            return {
                "success": False,
                "message": (
                    "Autonomous agent is already running."
                ),
                "status": self.status(),
            }

        # ========================================================
        # HARD PAPER-TRADING SAFETY
        # ========================================================

        if not settings.alpaca_paper:

            raise RuntimeError(
                "Autonomous trading is disabled because "
                "Alpaca paper trading is not enabled."
            )

        # ========================================================
        # PERSIST ENABLED STATE
        # ========================================================

        if persist:

            await self._set_persistent_enabled(
                True
            )

        # ========================================================
        # START ENGINE
        # ========================================================

        self.running = True

        self.started_at = datetime.now(
            timezone.utc
        ).isoformat()

        self.last_error = None

        self.current_stage = "STARTING"

        self.log(
            agent="Supervisor",
            action=(
                "Autonomous trading engine started"
            ),
            status="success",
        )

        self.current_stage = "WAITING"

        self.task = asyncio.create_task(
            self._run_loop()
        )

        return {
            "success": True,
            "message": (
                "Autonomous trading agent started."
            ),
            "status": self.status(),
        }

    # ============================================================
    # STOP
    # ============================================================

    async def stop(
        self,
        persist: bool = True,
    ):

        # ========================================================
        # PERSIST DISABLED STATE
        # ========================================================

        if persist:

            await self._set_persistent_enabled(
                False
            )

        if not self.running:

            self.current_stage = "IDLE"

            return {
                "success": False,
                "message": (
                    "Autonomous agent is already stopped."
                ),
                "status": self.status(),
            }

        self.running = False

        self.current_stage = "STOPPING"

        self.log(
            agent="Supervisor",
            action=(
                "Autonomous trading engine stopped"
            ),
            status="success",
        )

        if self.task:

            self.task.cancel()

            try:

                await self.task

            except asyncio.CancelledError:

                pass

            self.task = None

        self.current_symbol = None

        self.current_stage = "IDLE"

        return {
            "success": True,
            "message": (
                "Autonomous trading agent stopped."
            ),
            "status": self.status(),
        }

    # ============================================================
    # BACKGROUND LOOP
    # ============================================================

    async def _run_loop(self):

        while self.running:

            try:

                # ------------------------------------------------
                # SESSION TRADE LIMIT
                # ------------------------------------------------

                if (
                    self.trades_executed
                    >= self.MAX_SESSION_TRADES
                ):

                    self.log(
                        agent="Supervisor",
                        action=(
                            "Session trade limit reached. "
                            "Autonomous execution paused."
                        ),
                        status="warning",
                    )

                    self.running = False

                    self.current_stage = (
                        "LIMIT_REACHED"
                    )

                    # Important:
                    # Since this was an automatic stop caused
                    # by the session limit, persist it too.

                    await self._set_persistent_enabled(
                        False
                    )

                    break

                # ------------------------------------------------
                # SCAN
                # ------------------------------------------------

                await self.scan()

            except asyncio.CancelledError:

                break

            except Exception as error:

                self.last_error = str(error)

                self.log(
                    agent="Supervisor",
                    action=(
                        "Autonomous scan failed"
                    ),
                    status="error",
                    details=str(error),
                )

            # ----------------------------------------------------
            # WAIT
            # ----------------------------------------------------

            if self.running:

                self.current_stage = "WAITING"

                await asyncio.sleep(
                    self.SCAN_INTERVAL_SECONDS
                )

    # ============================================================
    # MANUAL SCAN
    # ============================================================

    async def scan(self):

        if not settings.alpaca_paper:

            raise RuntimeError(
                "Autonomous trading is disabled because "
                "Alpaca paper trading is not enabled."
            )

        self.scan_count += 1

        self.last_scan_at = datetime.now(
            timezone.utc
        ).isoformat()

        self.current_stage = "SCANNING"

        self.log(
            agent="Supervisor",
            action=(
                "Autonomous market scan started"
            ),
        )

        trades_this_scan = 0

        for symbol in self.WATCHLIST:

            # ----------------------------------------------------
            # STOP CHECK
            # ----------------------------------------------------

            if not self.running and self.task:

                break

            # ----------------------------------------------------
            # PER-SCAN TRADE LIMIT
            # ----------------------------------------------------

            if (
                trades_this_scan
                >= self.MAX_TRADES_PER_SCAN
            ):

                break

            self.current_symbol = symbol

            # ====================================================
            # MARKET AGENT
            # ====================================================

            self.current_stage = "MARKET_ANALYSIS"

            self.log(
                agent="Market Agent",
                action=(
                    "Analyzing market conditions"
                ),
                symbol=symbol,
            )

            market = market_agent.analyze(
                symbol
            )

            if not market.get("available"):

                self.log(
                    agent="Market Agent",
                    action=(
                        "Market data unavailable"
                    ),
                    symbol=symbol,
                    status="warning",
                    details=market.get("reason"),
                )

                continue

            # ====================================================
            # STRATEGY AGENT
            # ====================================================

            self.current_stage = "AI_ANALYSIS"

            self.log(
                agent="Strategy Agent",
                action=(
                    "AI evaluating opportunity"
                ),
                symbol=symbol,
            )

            strategy = strategy_agent.decide(
                symbol,
                market,
            )

            self.signals_count += 1

            # ----------------------------------------------------
            # VALIDATE STRATEGY RESPONSE
            # ----------------------------------------------------

            decision = str(
                strategy.get(
                    "decision",
                    "HOLD",
                )
            ).upper()

            confidence = float(
                strategy.get(
                    "confidence",
                    0,
                )
            )

            risk_score = float(
                strategy.get(
                    "risk_score",
                    100,
                )
            )

            reasoning = strategy.get(
                "reasoning",
                "No reasoning provided.",
            )

            self.log(
                agent="Strategy Agent",
                action=(
                    f"AI decision: {decision}"
                ),
                symbol=symbol,
                details={
                    "decision": decision,
                    "confidence": confidence,
                    "risk_score": risk_score,
                    "reasoning": reasoning,
                },
            )

            # ====================================================
            # INVALID DECISION
            # ====================================================

            if decision not in {
                "BUY",
                "SELL",
                "HOLD",
            }:

                self.log(
                    agent="Strategy Agent",
                    action=(
                        "Invalid AI decision — "
                        "trade skipped"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "decision": decision,
                    },
                )

                continue

            # ====================================================
            # HOLD
            # ====================================================

            if decision == "HOLD":

                self.log(
                    agent="Strategy Agent",
                    action=(
                        "No trade — AI recommends HOLD"
                    ),
                    symbol=symbol,
                    status="info",
                )

                continue

            # ====================================================
            # POSITION CHECK
            # ====================================================

            positions = (
                alpaca_service.get_positions()
            )

            existing_position = next(
                (
                    position
                    for position in positions
                    if position.symbol.upper()
                    == symbol
                ),
                None,
            )

            # ----------------------------------------------------
            # BUY ALREADY HELD
            # ----------------------------------------------------

            if (
                decision == "BUY"
                and existing_position is not None
            ):

                self.log(
                    agent="Supervisor",
                    action=(
                        "BUY skipped — position "
                        "already exists"
                    ),
                    symbol=symbol,
                    status="info",
                )

                continue

            # ----------------------------------------------------
            # SELL WITHOUT POSITION
            # ----------------------------------------------------

            if (
                decision == "SELL"
                and existing_position is None
            ):

                self.log(
                    agent="Supervisor",
                    action=(
                        "SELL skipped — no position "
                        "available to sell"
                    ),
                    symbol=symbol,
                    status="info",
                )

                continue

            # ====================================================
            # ACCOUNT
            # ====================================================

            account = (
                alpaca_service.get_account()
            )

            equity = float(
                account.equity
            )

            if equity <= 0:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Invalid account equity"
                    ),
                    symbol=symbol,
                    status="error",
                )

                continue

            # ====================================================
            # PRICE
            # ====================================================

            try:

                price = float(
                    market["price"]["current"]
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):

                self.log(
                    agent="Market Agent",
                    action=(
                        "Invalid market price data"
                    ),
                    symbol=symbol,
                    status="error",
                    details=market.get("price"),
                )

                continue

            if price <= 0:

                self.log(
                    agent="Market Agent",
                    action=(
                        "Invalid market price"
                    ),
                    symbol=symbol,
                    status="error",
                )

                continue

            # ====================================================
            # POSITION SIZING
            # ====================================================

            max_trade_value = (
                equity
                * self.MAX_TRADE_PERCENT
            )

            quantity = (
                max_trade_value
                / price
            )

            quantity = round(
                quantity,
                4,
            )

            if quantity <= 0:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Calculated quantity is zero"
                    ),
                    symbol=symbol,
                    status="warning",
                )

                continue

            trade_value = (
                price
                * quantity
            )

            # ====================================================
            # SELL QUANTITY
            # ====================================================

            if (
                decision == "SELL"
                and existing_position is not None
            ):

                position_qty = float(
                    existing_position.qty
                )

                quantity = min(
                    quantity,
                    position_qty,
                )

                quantity = round(
                    quantity,
                    4,
                )

                trade_value = (
                    price
                    * quantity
                )

            if quantity <= 0:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Sell quantity is zero"
                    ),
                    symbol=symbol,
                    status="warning",
                )

                continue

            # ====================================================
            # RISK AGENT
            # ====================================================

            self.current_stage = "RISK_CHECK"

            self.log(
                agent="Risk Agent",
                action=(
                    "Evaluating trade risk"
                ),
                symbol=symbol,
                details={
                    "trade_value": trade_value,
                    "confidence": confidence,
                    "risk_score": risk_score,
                },
            )

            risk = risk_agent.evaluate(
                account_equity=equity,
                trade_value=trade_value,
                confidence=confidence,
                risk_score=risk_score,
            )

            if not risk.get(
                "approved",
                False,
            ):

                self.trades_rejected += 1

                self.log(
                    agent="Risk Agent",
                    action="Trade rejected",
                    symbol=symbol,
                    status="warning",
                    details=risk,
                )

                continue

            # ====================================================
            # FINAL PAPER SAFETY
            # ====================================================

            if not settings.alpaca_paper:

                self.trades_rejected += 1

                self.log(
                    agent="Supervisor",
                    action=(
                        "Trade blocked — Alpaca is not "
                        "configured for paper trading."
                    ),
                    symbol=symbol,
                    status="error",
                )

                continue

            # ====================================================
            # EXECUTION
            # ====================================================

            self.current_stage = "EXECUTING"

            self.log(
                agent="Supervisor",
                action=(
                    f"Executing autonomous "
                    f"{decision} order"
                ),
                symbol=symbol,
                details={
                    "quantity": quantity,
                    "estimated_price": price,
                    "estimated_value": trade_value,
                },
            )

            try:

                order = (
                    alpaca_service.submit_market_order(
                        symbol=symbol,
                        side=decision.lower(),
                        quantity=quantity,
                    )
                )

            except Exception as error:

                self.last_error = str(error)

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        f"{decision} order failed"
                    ),
                    symbol=symbol,
                    status="error",
                    details=str(error),
                )

                continue

            # ====================================================
            # SUCCESS
            # ====================================================

            self.trades_executed += 1

            trades_this_scan += 1

            self.last_trade_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            self.log(
                agent="Alpaca",
                action=(
                    f"{decision} order submitted"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(order.id),
                    "quantity": quantity,
                    "price": price,
                    "trade_value": trade_value,
                    "confidence": confidence,
                    "risk_score": risk_score,
                },
            )

            break

        # ========================================================
        # SCAN COMPLETE
        # ========================================================

        self.current_symbol = None

        if self.running:

            self.current_stage = "WAITING"

        self.log(
            agent="Supervisor",
            action=(
                "Autonomous market scan completed"
            ),
        )

        return {
            "success": True,
            "scan_count": self.scan_count,
            "signals_count": self.signals_count,
            "trades_executed": (
                self.trades_executed
            ),
            "trades_rejected": (
                self.trades_rejected
            ),
        }

    # ============================================================
    # STATUS
    # ============================================================

    def status(self):

        return {
            "running": self.running,

            "stage": self.current_stage,

            "current_symbol": self.current_symbol,

            "started_at": self.started_at,

            "last_scan_at": self.last_scan_at,

            "last_trade_at": self.last_trade_at,

            "scan_count": self.scan_count,

            "signals_count": self.signals_count,

            "trades_executed": (
                self.trades_executed
            ),

            "trades_rejected": (
                self.trades_rejected
            ),

            "watchlist": self.WATCHLIST,

            "scan_interval_seconds": (
                self.SCAN_INTERVAL_SECONDS
            ),

            "max_trade_percent": (
                self.MAX_TRADE_PERCENT
            ),

            "max_trades_per_scan": (
                self.MAX_TRADES_PER_SCAN
            ),

            "max_session_trades": (
                self.MAX_SESSION_TRADES
            ),

            "last_error": self.last_error,

            "paper_trading": bool(
                settings.alpaca_paper
            ),
        }

    # ============================================================
    # ACTIVITY
    # ============================================================

    def get_activity(
        self,
        limit: int = 50,
    ):

        limit = max(
            1,
            min(int(limit), 100),
        )

        return self.activity[:limit]


# ================================================================
# SINGLE AUTONOMOUS AGENT INSTANCE
# ================================================================

autonomous_agent = AutonomousTradingAgent()