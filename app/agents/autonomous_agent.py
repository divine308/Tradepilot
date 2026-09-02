import asyncio

from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import select

from app.agents.market_agent import market_agent
from app.agents.strategy_agent import strategy_agent
from app.agents.risk_agent import risk_agent

from app.core.config import settings

from app.database.database import AsyncSessionLocal

from app.models.autonomous_agent import (
    AutonomousAgentState,
)

from app.services.alpaca_service import (
    alpaca_service,
)


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

    # Scan every 5 minutes
    SCAN_INTERVAL_SECONDS = 300

    # Maximum value of a NEW position
    MAX_TRADE_PERCENT = 0.05

    # ------------------------------------------------------------
    # Position protection
    # ------------------------------------------------------------

    STOP_LOSS_PERCENT = 0.04
    TAKE_PROFIT_PERCENT = 0.30

    # ------------------------------------------------------------
    # Breakeven
    # ------------------------------------------------------------

    BREAKEVEN_TRIGGER_PERCENT = 0.10
    BREAKEVEN_OFFSET_PERCENT = 0.0005

    # ------------------------------------------------------------
    # Execution limits
    # ------------------------------------------------------------

    MAX_TRADES_PER_SCAN = 1
    MAX_SESSION_TRADES = 10

    # ------------------------------------------------------------
    # Fill handling
    # ------------------------------------------------------------

    FILL_TIMEOUT_SECONDS = 15
    FILL_POLL_INTERVAL_SECONDS = 0.5

    # ------------------------------------------------------------
    # Minimum quantity
    # ------------------------------------------------------------

    MIN_QUANTITY = 0.000001

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self):

        self.running = False

        self.task: Optional[
            asyncio.Task
        ] = None

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

        # --------------------------------------------------------
        # Local protection state
        # --------------------------------------------------------

        # Symbols whose stop has already been moved to breakeven
        self.breakeven_symbols = set()

        # Symbols for which the agent has established protection
        self.protected_symbols = set()

        # Symbols currently being exited
        self.exit_in_progress = set()

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

            state = (
                result.scalar_one_or_none()
            )

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

                state.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            await session.commit()

    async def _get_persistent_enabled(
        self,
    ):

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(
                    AutonomousAgentState.enabled
                ).where(
                    AutonomousAgentState.id == 1
                )
            )

            enabled = (
                result.scalar_one_or_none()
            )

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
        details: Any = None,
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

        self.activity = (
            self.activity[:100]
        )

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
                    "Autonomous agent "
                    "is already running."
                ),
                "status": self.status(),
            }

        # ========================================================
        # PAPER TRADING SAFETY
        # ========================================================

        if not settings.alpaca_paper:

            raise RuntimeError(
                "Autonomous trading is disabled "
                "because Alpaca paper trading "
                "is not enabled."
            )

        if persist:

            await self._set_persistent_enabled(
                True
            )

        self.running = True

        self.started_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self.last_error = None

        self.current_stage = "STARTING"

        self.log(
            agent="Supervisor",
            action=(
                "Autonomous trading engine started"
            ),
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

        if persist:

            await self._set_persistent_enabled(
                False
            )

        if not self.running:

            self.current_stage = "IDLE"

            return {
                "success": False,
                "message": (
                    "Autonomous agent "
                    "is already stopped."
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
                # SESSION LIMIT
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

                    await (
                        self._set_persistent_enabled(
                            False
                        )
                    )

                    break

                # ------------------------------------------------
                # MANAGE EXISTING POSITIONS
                # ------------------------------------------------

                await self.manage_positions()

                # ------------------------------------------------
                # FIND NEW TRADES
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

            if self.running:

                self.current_stage = "WAITING"

                await asyncio.sleep(
                    self.SCAN_INTERVAL_SECONDS
                )

    # ============================================================
    # POSITION PROTECTION
    # ============================================================

    async def manage_positions(self):

        self.current_stage = (
            "POSITION_PROTECTION"
        )

        try:

            positions = (
                alpaca_service.get_positions()
            )

            # ----------------------------------------------------
            # No positions
            # ----------------------------------------------------

            if not positions:

                self.breakeven_symbols.clear()
                self.protected_symbols.clear()

                return

            active_symbols = set()

            for position in positions:

                symbol = (
                    position.symbol.upper()
                )

                active_symbols.add(symbol)

                # =================================================
                # POSITION DATA
                # =================================================

                try:

                    entry_price = float(
                        position.avg_entry_price
                    )

                    current_price = float(
                        position.current_price
                    )

                    position_qty = float(
                        position.qty
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    self.log(
                        agent="Risk Agent",
                        action=(
                            "Invalid position data"
                        ),
                        symbol=symbol,
                        status="error",
                    )

                    continue

                if entry_price <= 0:
                    continue

                if current_price <= 0:
                    continue

                if position_qty <= 0:
                    continue

                # ------------------------------------------------
                # Only long positions for now
                # ------------------------------------------------

                if current_price <= entry_price:

                    continue

                profit_percent = (
                    (
                        current_price
                        - entry_price
                    )
                    / entry_price
                )

                # =================================================
                # TAKE PROFIT
                # =================================================

                if (
                    profit_percent
                    >= self.TAKE_PROFIT_PERCENT
                ):

                    await self._handle_take_profit(
                        symbol=symbol,
                        position_qty=position_qty,
                        entry_price=entry_price,
                        current_price=current_price,
                        profit_percent=profit_percent,
                    )

                    # Do not continue managing
                    # this position during the
                    # same cycle.
                    continue

                # =================================================
                # BREAKEVEN
                # =================================================

                if (
                    profit_percent
                    < self.BREAKEVEN_TRIGGER_PERCENT
                ):

                    continue

                if (
                    symbol
                    in self.breakeven_symbols
                ):

                    continue

                await self._move_to_breakeven(
                    symbol=symbol,
                    entry_price=entry_price,
                    current_price=current_price,
                    profit_percent=profit_percent,
                )

            # ----------------------------------------------------
            # Clean local state for positions that no longer exist
            # ----------------------------------------------------

            self.breakeven_symbols.intersection_update(
                active_symbols
            )

            self.protected_symbols.intersection_update(
                active_symbols
            )

            self.exit_in_progress.intersection_update(
                active_symbols
            )

        finally:

            if self.running:

                self.current_stage = (
                    "WAITING"
                )

    # ============================================================
    # MOVE STOP TO BREAKEVEN
    # ============================================================

    async def _move_to_breakeven(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        profit_percent: float,
    ):

        breakeven_price = (
            entry_price
            * (
                1
                + self.BREAKEVEN_OFFSET_PERCENT
            )
        )

        self.log(
            agent="Risk Agent",
            action=(
                "Breakeven trigger reached"
            ),
            symbol=symbol,
            details={
                "entry_price": entry_price,
                "current_price": current_price,
                "profit_percent": profit_percent,
                "breakeven_price": breakeven_price,
            },
        )

        try:

            result = (
                alpaca_service
                .move_stop_to_breakeven(
                    symbol=symbol,
                    stop_price=(
                        breakeven_price
                    ),
                )
            )

            if result is None:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Breakeven failed — "
                        "no active stop order found"
                    ),
                    symbol=symbol,
                    status="warning",
                )

                return

            self.breakeven_symbols.add(
                symbol
            )

            self.protected_symbols.add(
                symbol
            )

            self.log(
                agent="Risk Agent",
                action=(
                    "Stop loss moved to breakeven"
                ),
                symbol=symbol,
                status="success",
                details={
                    "new_stop": (
                        breakeven_price
                    ),
                    "current_price": (
                        current_price
                    ),
                    "profit_percent": (
                        profit_percent
                    ),
                },
            )

        except Exception as error:

            self.last_error = str(error)

            self.log(
                agent="Risk Agent",
                action=(
                    "Failed to move stop to breakeven"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

    # ============================================================
    # TAKE PROFIT
    # ============================================================

    async def _handle_take_profit(
        self,
        symbol: str,
        position_qty: float,
        entry_price: float,
        current_price: float,
        profit_percent: float,
    ):

        if symbol in self.exit_in_progress:

            return

        self.exit_in_progress.add(
            symbol
        )

        self.current_stage = (
            "TAKE_PROFIT"
        )

        self.log(
            agent="Strategy Agent",
            action=(
                "Take-profit target reached"
            ),
            symbol=symbol,
            details={
                "entry_price": entry_price,
                "current_price": current_price,
                "profit_percent": profit_percent,
                "target_percent": (
                    self.TAKE_PROFIT_PERCENT
                ),
                "quantity": position_qty,
            },
        )

        # ========================================================
        # CANCEL PROTECTIVE STOP
        # ========================================================

        try:

            alpaca_service.cancel_protective_stop(
                symbol
            )

            self.log(
                agent="Risk Agent",
                action=(
                    "Protective stop cancelled "
                    "before take-profit exit"
                ),
                symbol=symbol,
                status="success",
            )

        except Exception as error:

            self.last_error = str(error)

            self.log(
                agent="Risk Agent",
                action=(
                    "Unable to cancel protective stop — "
                    "take-profit exit blocked"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

            self.exit_in_progress.discard(
                symbol
            )

            return

        # ========================================================
        # EXIT POSITION
        # ========================================================

        try:

            exit_order = (
                alpaca_service.submit_market_order(
                    symbol=symbol,
                    side="sell",
                    quantity=round(
                        position_qty,
                        9,
                    ),
                )
            )

            self.log(
                agent="Alpaca",
                action=(
                    "Take-profit market exit submitted"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        exit_order.id
                    ),
                    "quantity": position_qty,
                    "estimated_price": (
                        current_price
                    ),
                    "profit_percent": (
                        profit_percent
                    ),
                },
            )

            self.breakeven_symbols.discard(
                symbol
            )

            self.protected_symbols.discard(
                symbol
            )

        except Exception as error:

            self.last_error = str(error)

            self.log(
                agent="Alpaca",
                action=(
                    "Take-profit exit failed"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

        finally:

            self.exit_in_progress.discard(
                symbol
            )

            if self.running:

                self.current_stage = (
                    "WAITING"
                )

    # ============================================================
    # POSITION PROTECTION RECOVERY
    # ============================================================

    async def _ensure_position_protection(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
    ):

        stop_price = (
            entry_price
            * (
                1
                - self.STOP_LOSS_PERCENT
            )
        )

        self.log(
            agent="Risk Agent",
            action=(
                "Establishing protective stop"
            ),
            symbol=symbol,
            details={
                "entry_price": entry_price,
                "stop_price": stop_price,
                "quantity": quantity,
            },
        )

        try:

            stop_order = (
                alpaca_service
                .submit_protective_stop(
                    symbol=symbol,
                    quantity=round(
                        quantity,
                        9,
                    ),
                    stop_price=(
                        stop_price
                    ),
                )
            )

            self.protected_symbols.add(
                symbol
            )

            self.log(
                agent="Risk Agent",
                action=(
                    "Protective stop established"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        stop_order.id
                    ),
                    "quantity": quantity,
                    "stop_price": stop_price,
                },
            )

            return stop_order

        except Exception as error:

            self.last_error = str(error)

            self.log(
                agent="Risk Agent",
                action=(
                    "Protective stop establishment failed"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

            return None

    # ============================================================
    # EMERGENCY POSITION CLOSE
    # ============================================================

    async def _emergency_close_position(
        self,
        symbol: str,
        quantity: float,
        reason: str,
    ):

        self.current_stage = (
            "EMERGENCY_EXIT"
        )

        self.log(
            agent="Risk Agent",
            action=(
                "Emergency position protection activated"
            ),
            symbol=symbol,
            status="warning",
            details={
                "reason": reason,
                "quantity": quantity,
            },
        )

        try:

            order = (
                alpaca_service
                .submit_market_order(
                    symbol=symbol,
                    side="sell",
                    quantity=round(
                        quantity,
                        9,
                    ),
                )
            )

            self.log(
                agent="Alpaca",
                action=(
                    "Emergency position close submitted"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        order.id
                    ),
                    "quantity": quantity,
                    "reason": reason,
                },
            )

            return order

        except Exception as error:

            self.last_error = str(error)

            self.log(
                agent="Risk Agent",
                action=(
                    "CRITICAL — emergency position "
                    "close failed"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

            return None

    # ============================================================
    # MANUAL SCAN
    # ============================================================

    async def scan(self):

        if not settings.alpaca_paper:

            raise RuntimeError(
                "Autonomous trading is disabled "
                "because Alpaca paper trading "
                "is not enabled."
            )

        self.scan_count += 1

        self.last_scan_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

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
            # Allow manual scans while agent is stopped.
            # But stop background scan immediately if stopped.
            # ----------------------------------------------------

            if (
                not self.running
                and self.task
            ):

                break

            if (
                trades_this_scan
                >= self.MAX_TRADES_PER_SCAN
            ):

                break

            self.current_symbol = symbol

            # ====================================================
            # MARKET
            # ====================================================

            self.current_stage = (
                "MARKET_ANALYSIS"
            )

            self.log(
                agent="Market Agent",
                action=(
                    "Analyzing market conditions"
                ),
                symbol=symbol,
            )

            market = (
                market_agent.analyze(
                    symbol
                )
            )

            if not market.get(
                "available"
            ):

                self.log(
                    agent="Market Agent",
                    action=(
                        "Market data unavailable"
                    ),
                    symbol=symbol,
                    status="warning",
                    details=market.get(
                        "reason"
                    ),
                )

                continue

            # ====================================================
            # STRATEGY
            # ====================================================

            self.current_stage = (
                "AI_ANALYSIS"
            )

            self.log(
                agent="Strategy Agent",
                action=(
                    "AI evaluating opportunity"
                ),
                symbol=symbol,
            )

            strategy = (
                strategy_agent.decide(
                    symbol,
                    market,
                )
            )

            self.signals_count += 1

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
            # VALIDATION
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
            # POSITIONS
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

            # ====================================================
            # BUY ALREADY HELD
            # ====================================================

            if (
                decision == "BUY"
                and existing_position is not None
            ):

                self.log(
                    agent="Supervisor",
                    action=(
                        "BUY skipped — "
                        "position already exists"
                    ),
                    symbol=symbol,
                    status="info",
                )

                continue

            # ====================================================
            # SELL WITHOUT POSITION
            # ====================================================

            if (
                decision == "SELL"
                and existing_position is None
            ):

                self.log(
                    agent="Supervisor",
                    action=(
                        "SELL skipped — "
                        "no position available"
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
                )

                continue

            if price <= 0:

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

            # ----------------------------------------------------
            # IMPORTANT:
            #
            # Keep fractional quantity.
            #
            # Alpaca supports fractional quantities for
            # supported DAY equity orders.
            #
            # Do NOT round this to an integer.
            # ----------------------------------------------------

            quantity = round(
                quantity,
                9,
            )

            if quantity < self.MIN_QUANTITY:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Calculated quantity is "
                        "below minimum threshold"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "quantity": quantity,
                    },
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
                    9,
                )

                trade_value = (
                    price
                    * quantity
                )

            if quantity < self.MIN_QUANTITY:

                continue

            # ====================================================
            # EXISTING EXPOSURE
            # ====================================================

            existing_exposure = 0.0

            if existing_position is not None:

                existing_market_value = (
                    abs(
                        float(
                            existing_position.market_value
                        )
                    )
                )

                existing_exposure = (
                    existing_market_value
                    / equity
                )

            # ====================================================
            # RISK
            # ====================================================

            self.current_stage = (
                "RISK_CHECK"
            )

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
                    "equity": equity,
                    "existing_exposure": (
                        existing_exposure
                    ),
                    "quantity": quantity,
                },
            )

            risk = risk_agent.evaluate(
                account_equity=equity,
                trade_value=trade_value,
                confidence=confidence,
                risk_score=risk_score,
                existing_exposure=(
                    existing_exposure
                ),
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
            # PROTECTIVE LEVELS
            # ====================================================

            if decision == "BUY":

                stop_loss_price = (
                    price
                    * (
                        1
                        - self.STOP_LOSS_PERCENT
                    )
                )

                take_profit_price = (
                    price
                    * (
                        1
                        + self.TAKE_PROFIT_PERCENT
                    )
                )

            else:

                stop_loss_price = None

                take_profit_price = None

            # ====================================================
            # FINAL PAPER SAFETY
            # ====================================================

            if not settings.alpaca_paper:

                self.trades_rejected += 1

                self.log(
                    agent="Supervisor",
                    action=(
                        "Trade blocked — "
                        "paper trading disabled"
                    ),
                    symbol=symbol,
                    status="error",
                )

                continue

            # ====================================================
            # EXECUTION
            # ====================================================

            self.current_stage = (
                "EXECUTING"
            )

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
                    "estimated_value": (
                        trade_value
                    ),
                    "stop_loss": (
                        stop_loss_price
                    ),
                    "take_profit": (
                        take_profit_price
                    ),
                    "breakeven_trigger": (
                        price
                        * (
                            1
                            + self.BREAKEVEN_TRIGGER_PERCENT
                        )
                        if decision == "BUY"
                        else None
                    ),
                },
            )

            # ====================================================
            # BUY EXECUTION
            #
            # IMPORTANT:
            #
            # We intentionally DO NOT send SL/TP to
            # submit_market_order().
            #
            # The entry is a SIMPLE fractional market order.
            #
            # After it fills:
            #
            #     entry
            #       ↓
            #     wait for fill
            #       ↓
            #     protective stop
            #       ↓
            #     monitor position
            #       ↓
            #     breakeven
            #       ↓
            #     take profit
            #
            # This avoids Alpaca's fractional + bracket
            # rejection.
            # ====================================================

            if decision == "BUY":

                await self._execute_buy(
                    symbol=symbol,
                    quantity=quantity,
                    estimated_price=price,
                    estimated_value=trade_value,
                    stop_loss_price=(
                        stop_loss_price
                    ),
                    take_profit_price=(
                        take_profit_price
                    ),
                    confidence=confidence,
                    risk_score=risk_score,
                )

                trades_this_scan += 1

                break

            # ====================================================
            # SELL EXECUTION
            # ====================================================

            if decision == "SELL":

                await self._execute_sell(
                    symbol=symbol,
                    quantity=quantity,
                    estimated_price=price,
                    estimated_value=trade_value,
                    confidence=confidence,
                    risk_score=risk_score,
                )

                trades_this_scan += 1

                break

        # ========================================================
        # COMPLETE
        # ========================================================

        self.current_symbol = None

        if self.running:

            self.current_stage = (
                "WAITING"
            )

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
    # BUY EXECUTION
    # ============================================================

    async def _execute_buy(
        self,
        symbol: str,
        quantity: float,
        estimated_price: float,
        estimated_value: float,
        stop_loss_price: float,
        take_profit_price: float,
        confidence: float,
        risk_score: float,
    ):

        try:

            # ====================================================
            # 1. SIMPLE MARKET ENTRY
            # ====================================================

            order = (
                alpaca_service.submit_market_order(
                    symbol=symbol,
                    side="buy",
                    quantity=round(
                        quantity,
                        9,
                    ),
                )
            )

            self.log(
                agent="Alpaca",
                action=(
                    "BUY market order submitted"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        order.id
                    ),
                    "requested_quantity": quantity,
                    "estimated_price": (
                        estimated_price
                    ),
                    "estimated_value": (
                        estimated_value
                    ),
                },
            )

            # ====================================================
            # 2. WAIT FOR ACTUAL FILL
            # ====================================================

            self.current_stage = (
                "WAITING_FOR_FILL"
            )

            filled_order = await asyncio.to_thread(
                alpaca_service.wait_for_order_fill,
                str(order.id),
                self.FILL_TIMEOUT_SECONDS,
                self.FILL_POLL_INTERVAL_SECONDS,
            )

            if filled_order is None:

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        "BUY order did not fill "
                        "within timeout"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "order_id": str(
                            order.id
                        ),
                        "timeout_seconds": (
                            self.FILL_TIMEOUT_SECONDS
                        ),
                    },
                )

                return

            # ====================================================
            # 3. ACTUAL FILL DATA
            # ====================================================

            try:

                filled_qty = float(
                    filled_order.filled_qty
                )

            except (
                TypeError,
                ValueError,
            ):

                filled_qty = quantity

            try:

                filled_avg_price = float(
                    filled_order.filled_avg_price
                )

            except (
                TypeError,
                ValueError,
            ):

                filled_avg_price = (
                    estimated_price
                )

            if filled_qty <= 0:

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        "BUY filled with invalid quantity"
                    ),
                    symbol=symbol,
                    status="error",
                    details={
                        "order_id": str(
                            order.id
                        ),
                        "filled_qty": filled_qty,
                    },
                )

                return

            # ====================================================
            # 4. RECALCULATE PROTECTION FROM ACTUAL FILL
            # ====================================================

            actual_stop_price = (
                filled_avg_price
                * (
                    1
                    - self.STOP_LOSS_PERCENT
                )
            )

            actual_take_profit = (
                filled_avg_price
                * (
                    1
                    + self.TAKE_PROFIT_PERCENT
                )
            )

            self.log(
                agent="Market Agent",
                action=(
                    "BUY position filled"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        order.id
                    ),
                    "requested_quantity": quantity,
                    "filled_quantity": filled_qty,
                    "filled_average_price": (
                        filled_avg_price
                    ),
                    "position_value": (
                        filled_qty
                        * filled_avg_price
                    ),
                    "stop_loss": (
                        actual_stop_price
                    ),
                    "take_profit": (
                        actual_take_profit
                    ),
                },
            )

            # ====================================================
            # 5. CREATE PROTECTIVE STOP
            # ====================================================

            self.current_stage = (
                "ESTABLISHING_PROTECTION"
            )

            stop_order = await asyncio.to_thread(
                alpaca_service.submit_protective_stop,
                symbol,
                round(
                    filled_qty,
                    9,
                ),
                round(
                    actual_stop_price,
                    2,
                ),
            )

            if stop_order is None:

                raise RuntimeError(
                    "Protective stop was not created."
                )

            self.protected_symbols.add(
                symbol
            )

            self.log(
                agent="Risk Agent",
                action=(
                    "Protective stop placed"
                ),
                symbol=symbol,
                status="success",
                details={
                    "stop_order_id": str(
                        stop_order.id
                    ),
                    "quantity": filled_qty,
                    "stop_price": (
                        actual_stop_price
                    ),
                    "entry_price": (
                        filled_avg_price
                    ),
                },
            )

            # ====================================================
            # 6. SUCCESS
            # ====================================================

            self.trades_executed += 1

            self.last_trade_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            self.log(
                agent="Supervisor",
                action=(
                    "Autonomous BUY completed "
                    "and protected"
                ),
                symbol=symbol,
                status="success",
                details={
                    "entry_order_id": str(
                        order.id
                    ),
                    "stop_order_id": str(
                        stop_order.id
                    ),
                    "quantity": filled_qty,
                    "entry_price": (
                        filled_avg_price
                    ),
                    "stop_loss": (
                        actual_stop_price
                    ),
                    "take_profit": (
                        actual_take_profit
                    ),
                    "confidence": confidence,
                    "risk_score": risk_score,
                },
            )

        except Exception as error:

            self.last_error = str(error)

            self.trades_rejected += 1

            self.log(
                agent="Alpaca",
                action=(
                    "Autonomous BUY execution failed"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

            # ----------------------------------------------------
            # CRITICAL:
            #
            # If the BUY filled but the protective stop failed,
            # try to close the position.
            #
            # We first inspect the current position so that we
            # don't blindly sell the originally requested qty.
            # ----------------------------------------------------

            try:

                positions = (
                    alpaca_service.get_positions()
                )

                position = next(
                    (
                        p
                        for p in positions
                        if p.symbol.upper()
                        == symbol
                    ),
                    None,
                )

                if position is not None:

                    emergency_qty = float(
                        position.qty
                    )

                    if emergency_qty > 0:

                        await self._emergency_close_position(
                            symbol=symbol,
                            quantity=emergency_qty,
                            reason=(
                                "BUY entry was filled "
                                "but protective stop "
                                "could not be established."
                            ),
                        )

            except Exception as emergency_error:

                self.last_error = (
                    f"{error} | "
                    f"Emergency close failed: "
                    f"{emergency_error}"
                )

                self.log(
                    agent="Risk Agent",
                    action=(
                        "CRITICAL — unable to verify "
                        "or close unprotected position"
                    ),
                    symbol=symbol,
                    status="error",
                    details=str(
                        emergency_error
                    ),
                )

    # ============================================================
    # SELL EXECUTION
    # ============================================================

    async def _execute_sell(
        self,
        symbol: str,
        quantity: float,
        estimated_price: float,
        estimated_value: float,
        confidence: float,
        risk_score: float,
    ):

        try:

            # ====================================================
            # CANCEL PROTECTIVE STOP FIRST
            # ====================================================

            try:

                alpaca_service.cancel_protective_stop(
                    symbol
                )

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Protective stop cancelled "
                        "before SELL exit"
                    ),
                    symbol=symbol,
                    status="success",
                )

            except Exception as error:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Unable to cancel protective stop"
                    ),
                    symbol=symbol,
                    status="warning",
                    details=str(error),
                )

            # ====================================================
            # SIMPLE MARKET SELL
            # ====================================================

            order = (
                alpaca_service.submit_market_order(
                    symbol=symbol,
                    side="sell",
                    quantity=round(
                        quantity,
                        9,
                    ),
                )
            )

            self.log(
                agent="Alpaca",
                action=(
                    "SELL market order submitted"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        order.id
                    ),
                    "quantity": quantity,
                    "estimated_price": (
                        estimated_price
                    ),
                    "estimated_value": (
                        estimated_value
                    ),
                    "confidence": confidence,
                    "risk_score": risk_score,
                },
            )

            self.trades_executed += 1

            self.last_trade_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            self.breakeven_symbols.discard(
                symbol
            )

            self.protected_symbols.discard(
                symbol
            )

            self.log(
                agent="Supervisor",
                action=(
                    "Autonomous SELL completed"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        order.id
                    ),
                    "quantity": quantity,
                },
            )

        except Exception as error:

            self.last_error = str(error)

            self.trades_rejected += 1

            self.log(
                agent="Alpaca",
                action=(
                    "Autonomous SELL execution failed"
                ),
                symbol=symbol,
                status="error",
                details=str(error),
            )

    # ============================================================
    # STATUS
    # ============================================================

    def status(self):

        return {
            "running": self.running,

            "stage": self.current_stage,

            "current_symbol": (
                self.current_symbol
            ),

            "started_at": self.started_at,

            "last_scan_at": (
                self.last_scan_at
            ),

            "last_trade_at": (
                self.last_trade_at
            ),

            "scan_count": self.scan_count,

            "signals_count": (
                self.signals_count
            ),

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

            "max_trades_per_scan": (
                self.MAX_TRADES_PER_SCAN
            ),

            "max_session_trades": (
                self.MAX_SESSION_TRADES
            ),

            "fill_timeout_seconds": (
                self.FILL_TIMEOUT_SECONDS
            ),

            "protected_symbols": list(
                self.protected_symbols
            ),

            "breakeven_symbols": list(
                self.breakeven_symbols
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
# SINGLE INSTANCE
# ================================================================

autonomous_agent = (
    AutonomousTradingAgent()
)
