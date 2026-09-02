
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

    SCAN_INTERVAL_SECONDS = 300

    MAX_TRADE_PERCENT = 0.05

    MAX_TOTAL_EXPOSURE_PERCENT = 0.50

    # ============================================================
    # POSITION PROTECTION
    # ============================================================

    STOP_LOSS_PERCENT = 0.04
    TAKE_PROFIT_PERCENT = 0.30

    # ============================================================
    # BREAKEVEN
    # ============================================================

    BREAKEVEN_TRIGGER_PERCENT = 0.10
    BREAKEVEN_OFFSET_PERCENT = 0.005

    # ============================================================
    # EXECUTION LIMITS
    # ============================================================

    MAX_TRADES_PER_SCAN = 1
    MAX_SESSION_TRADES = 10

    # ============================================================
    # FILL HANDLING
    # ============================================================

    FILL_TIMEOUT_SECONDS = 15
    FILL_POLL_INTERVAL_SECONDS = 0.5

    # ============================================================
    # ORDER CANCELLATION
    # ============================================================

    CANCEL_TIMEOUT_SECONDS = 10
    CANCEL_POLL_INTERVAL_SECONDS = 0.5

    # ============================================================
    # MINIMUM QUANTITY
    # ============================================================

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

        self.breakeven_symbols = set()

        self.protected_symbols = set()

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
    # CALCULATE TOTAL PORTFOLIO EXPOSURE
    # ============================================================

    def _calculate_total_exposure(
        self,
        positions,
        equity: float,
    ):

        if equity <= 0:
            return 0.0

        total_market_value = 0.0

        for position in positions:

            try:

                market_value = float(
                    position.market_value
                )

                if market_value > 0:

                    total_market_value += (
                        market_value
                    )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                continue

        return (
            total_market_value
            / equity
        )

    # ============================================================
    # WAIT FOR ORDER CANCELLATION
    # ============================================================

    async def _wait_for_order_cancellation(
        self,
        order_id,
    ):

        deadline = (
            asyncio.get_running_loop().time()
            + self.CANCEL_TIMEOUT_SECONDS
        )

        last_order = None

        while (
            asyncio.get_running_loop().time()
            < deadline
        ):

            try:

                order = await asyncio.to_thread(
                    alpaca_service.client.get_order_by_id,
                    order_id,
                )

                last_order = order

                status = str(
                    order.status
                ).lower()

                if status in {
                    "canceled",
                    "cancelled",
                    "rejected",
                    "expired",
                }:

                    return True

                if status == "filled":

                    return False

            except Exception:

                pass

            await asyncio.sleep(
                self.CANCEL_POLL_INTERVAL_SECONDS
            )

        # Final verification

        try:

            order = await asyncio.to_thread(
                alpaca_service.client.get_order_by_id,
                order_id,
            )

            last_order = order

            status = str(
                order.status
            ).lower()

            return status in {
                "canceled",
                "cancelled",
                "rejected",
                "expired",
            }

        except Exception:

            return False

    # ============================================================
    # CANCEL PROTECTIVE STOP SAFELY
    # ============================================================

    async def _cancel_protective_stop_safely(
        self,
        symbol: str,
    ):

        symbol = symbol.upper().strip()

        stop_order = (
            await asyncio.to_thread(
                alpaca_service.get_active_protective_stop,
                symbol,
            )
        )

        if stop_order is None:

            self.protected_symbols.discard(
                symbol
            )

            return True

        order_id = str(
            stop_order.id
        )

        self.log(
            agent="Risk Agent",
            action=(
                "Cancelling protective stop "
                "before position exit"
            ),
            symbol=symbol,
            details={
                "order_id": order_id,
            },
        )

        try:

            await asyncio.to_thread(
                alpaca_service.client.cancel_order_by_id,
                stop_order.id,
            )

        except Exception as error:

            # The order may have already been cancelled
            # between lookup and cancellation.

            try:

                current_order = (
                    await asyncio.to_thread(
                        alpaca_service.client.get_order_by_id,
                        stop_order.id,
                    )
                )

                current_status = str(
                    current_order.status
                ).lower()

                if current_status not in {
                    "canceled",
                    "cancelled",
                    "rejected",
                    "expired",
                }:

                    raise error

            except Exception:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Protective stop cancellation failed"
                    ),
                    symbol=symbol,
                    status="error",
                    details=str(error),
                )

                return False

        # ========================================================
        # IMPORTANT:
        #
        # Alpaca cancellation is not necessarily instantaneous.
        # We MUST wait until the order is actually cancelled before
        # attempting the market sell.
        # ========================================================

        cancelled = (
            await self._wait_for_order_cancellation(
                stop_order.id
            )
        )

        if not cancelled:

            self.log(
                agent="Risk Agent",
                action=(
                    "Protective stop is not confirmed "
                    "cancelled — exit blocked"
                ),
                symbol=symbol,
                status="error",
                details={
                    "order_id": order_id,
                },
            )

            return False

        self.protected_symbols.discard(
            symbol
        )

        self.log(
            agent="Risk Agent",
            action=(
                "Protective stop fully cancelled"
            ),
            symbol=symbol,
            status="success",
            details={
                "order_id": order_id,
            },
        )

        return True

    # ============================================================
    # POSITION PROTECTION
    # ============================================================

    async def manage_positions(self):

        self.current_stage = (
            "POSITION_PROTECTION"
        )

        try:

            positions = (
                await asyncio.to_thread(
                    alpaca_service.get_positions
                )
            )

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
                    AttributeError,
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

                # =================================================
                # EXIT ALREADY IN PROGRESS
                # =================================================

                if symbol in self.exit_in_progress:

                    continue

                # =================================================
                # FIND REAL PROTECTIVE STOP
                # =================================================

                existing_stop = await asyncio.to_thread(
                    alpaca_service.get_active_protective_stop,
                    symbol,
                )

                if existing_stop is not None:

                    self.protected_symbols.add(
                        symbol
                    )

                # =================================================
                # PROTECTION RECOVERY
                # =================================================

                if existing_stop is None:

                    self.current_stage = (
                        "RECOVERING_PROTECTION"
                    )

                    self.log(
                        agent="Risk Agent",
                        action=(
                            "No active protective stop "
                            "found — recovering protection"
                        ),
                        symbol=symbol,
                    )

                    stop_order = (
                        await self._ensure_position_protection(
                            symbol=symbol,
                            quantity=position_qty,
                            entry_price=entry_price,
                        )
                    )

                    if stop_order is not None:

                        self.protected_symbols.add(
                            symbol
                        )

                # =================================================
                # PROFIT
                # =================================================

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
            # Clean local state
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

            result = await asyncio.to_thread(
                alpaca_service.move_stop_to_breakeven,
                symbol=symbol,
                stop_price=round(
                    breakeven_price,
                    2,
                ),
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
                    "new_stop": breakeven_price,
                    "current_price": current_price,
                    "profit_percent": profit_percent,
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

            return False

        self.exit_in_progress.add(
            symbol
        )

        self.current_stage = (
            "TAKE_PROFIT"
        )

        try:

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

            success = await self._execute_sell(
                symbol=symbol,
                quantity=position_qty,
                estimated_price=current_price,
                estimated_value=(
                    current_price
                    * position_qty
                ),
                confidence=1.0,
                risk_score=0.0,
                reason="TAKE_PROFIT",
            )

            return success

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

            stop_order = await asyncio.to_thread(
                alpaca_service.submit_protective_stop,
                symbol=symbol,
                quantity=round(
                    quantity,
                    9,
                ),
                stop_price=round(
                    stop_price,
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

            # ----------------------------------------------------
            # IMPORTANT:
            #
            # Emergency exit must also release any shares held
            # by existing sell orders.
            # ----------------------------------------------------

            cancelled = (
                await self._cancel_protective_stop_safely(
                    symbol
                )
            )

            if not cancelled:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Emergency exit blocked because "
                        "protective stop could not be cancelled"
                    ),
                    symbol=symbol,
                    status="error",
                )

                return None

            available_qty = await asyncio.to_thread(
                alpaca_service.get_available_sell_quantity,
                symbol,
            )

            if available_qty <= 0:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Emergency exit has no available "
                        "quantity"
                    ),
                    symbol=symbol,
                    status="error",
                )

                return None

            emergency_qty = min(
                float(quantity),
                float(available_qty),
            )

            if emergency_qty < self.MIN_QUANTITY:

                return None

            order = await asyncio.to_thread(
                alpaca_service.submit_market_order,
                symbol=symbol,
                side="sell",
                quantity=round(
                    emergency_qty,
                    9,
                ),
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
                    "quantity": emergency_qty,
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
                    1.0,
                )
            )

            quantitative_score = float(
                strategy.get(
                    "quantitative_score",
                    50.0,
                )
            )

            reasoning = strategy.get(
                "reasoning",
                "No reasoning provided.",
            )

            self.log(
                agent="Strategy Agent",
                action=(
                    f"Strategy decision: {decision}"
                ),
                symbol=symbol,
                details={
                    "decision": decision,
                    "confidence": confidence,
                    "risk_score": risk_score,
                    "quantitative_score": (
                        quantitative_score
                    ),
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
                        "Invalid strategy decision — "
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
                        "No trade — strategy recommends HOLD"
                    ),
                    symbol=symbol,
                    status="info",
                )

                continue

            # ====================================================
            # POSITIONS
            # ====================================================

            positions = (
                await asyncio.to_thread(
                    alpaca_service.get_positions
                )
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
                await asyncio.to_thread(
                    alpaca_service.get_account
                )
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
            # TOTAL EXISTING EXPOSURE
            # ====================================================

            total_existing_exposure = (
                self._calculate_total_exposure(
                    positions=positions,
                    equity=equity,
                )
            )

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

                # Do not use the full position blindly.
                #
                # The execution layer will re-check available
                # quantity after the protective stop is cancelled.

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
                    "quantitative_score": (
                        quantitative_score
                    ),
                    "equity": equity,
                    "existing_exposure": (
                        total_existing_exposure
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
                    total_existing_exposure
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
                    "estimated_value": trade_value,
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "breakeven_trigger": (
                        price
                        * (
                            1
                            + self.BREAKEVEN_TRIGGER_PERCENT
                        )
                        if decision == "BUY"
                        else None
                    ),
                    "breakeven_offset": (
                        self.BREAKEVEN_OFFSET_PERCENT
                    ),
                    "existing_exposure": (
                        total_existing_exposure
                    ),
                },
            )

            # ====================================================
            # BUY
            # ====================================================

            if decision == "BUY":

                trade_result = (
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
                )

                if trade_result:

                    trades_this_scan += 1

                break

            # ====================================================
            # SELL
            # ====================================================

            if decision == "SELL":

                trade_result = (
                    await self._execute_sell(
                        symbol=symbol,
                        quantity=quantity,
                        estimated_price=price,
                        estimated_value=trade_value,
                        confidence=confidence,
                        risk_score=risk_score,
                        reason="AI_SELL",
                    )
                )

                if trade_result:

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

        order = None

        try:

            # ====================================================
            # 1. MARKET ENTRY
            # ====================================================

            order = await asyncio.to_thread(
                alpaca_service.submit_market_order,
                symbol=symbol,
                side="buy",
                quantity=round(
                    quantity,
                    9,
                ),
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
            # 2. WAIT FOR FILL
            # ====================================================

            self.current_stage = (
                "WAITING_FOR_FILL"
            )

            filled_order = (
                await asyncio.to_thread(
                    alpaca_service.wait_for_order_fill,
                    str(order.id),
                    self.FILL_TIMEOUT_SECONDS,
                    self.FILL_POLL_INTERVAL_SECONDS,
                )
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
                    },
                )

                return False

            status = str(
                filled_order.status
            ).lower()

            if status != "filled":

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        "BUY order did not fill"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "order_id": str(
                            order.id
                        ),
                        "status": status,
                    },
                )

                return False

            # ====================================================
            # 3. ACTUAL FILL DATA
            # ====================================================

            try:

                filled_qty = float(
                    filled_order.filled_qty
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                filled_qty = 0.0

            try:

                filled_avg_price = float(
                    filled_order.filled_avg_price
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                filled_avg_price = (
                    estimated_price
                )

            if filled_qty <= 0:

                self.trades_rejected += 1

                raise RuntimeError(
                    "BUY filled with invalid quantity."
                )

            # ====================================================
            # 4. ACTUAL PROTECTION
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
            # 5. PROTECTIVE STOP
            # ====================================================

            self.current_stage = (
                "ESTABLISHING_PROTECTION"
            )

            stop_order = (
                await asyncio.to_thread(
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
                    "breakeven_trigger": (
                        filled_avg_price
                        * (
                            1
                            + self.BREAKEVEN_TRIGGER_PERCENT
                        )
                    ),
                    "breakeven_offset": (
                        self.BREAKEVEN_OFFSET_PERCENT
                    ),
                    "confidence": confidence,
                    "risk_score": risk_score,
                },
            )

            return True

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

            # ====================================================
            # CRITICAL RECOVERY
            # ====================================================

            try:

                positions = (
                    await asyncio.to_thread(
                        alpaca_service.get_positions
                    )
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

            return False

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
        reason: str = "AI_SELL",
    ):

        symbol = symbol.upper().strip()

        if symbol in self.exit_in_progress:

            self.log(
                agent="Supervisor",
                action=(
                    "SELL skipped — exit already "
                    "in progress"
                ),
                symbol=symbol,
                status="warning",
            )

            return False

        self.exit_in_progress.add(
            symbol
        )

        try:

            self.current_stage = (
                "PREPARING_EXIT"
            )

            # ====================================================
            # 1. GET CURRENT POSITION
            # ====================================================

            position = await asyncio.to_thread(
                alpaca_service.get_position,
                symbol,
            )

            if position is None:

                self.log(
                    agent="Supervisor",
                    action=(
                        "SELL skipped — position "
                        "no longer exists"
                    ),
                    symbol=symbol,
                    status="warning",
                )

                return False

            position_qty = float(
                position.qty
            )

            if position_qty <= 0:

                self.log(
                    agent="Supervisor",
                    action=(
                        "SELL skipped — position quantity "
                        "is zero"
                    ),
                    symbol=symbol,
                    status="warning",
                )

                return False

            requested_quantity = min(
                float(quantity),
                position_qty,
            )

            requested_quantity = round(
                requested_quantity,
                9,
            )

            if requested_quantity < self.MIN_QUANTITY:

                return False

            # ====================================================
            # 2. CANCEL PROTECTIVE STOP
            # ====================================================

            cancelled = (
                await self._cancel_protective_stop_safely(
                    symbol
                )
            )

            if not cancelled:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "SELL blocked — protective stop "
                        "was not fully cancelled"
                    ),
                    symbol=symbol,
                    status="error",
                )

                return False

            # ====================================================
            # 3. RE-CHECK AVAILABLE QUANTITY
            # ====================================================

            self.current_stage = (
                "VERIFYING_AVAILABLE_QUANTITY"
            )

            available_qty = (
                await asyncio.to_thread(
                    alpaca_service.get_available_sell_quantity,
                    symbol,
                )
            )

            available_qty = round(
                float(available_qty),
                9,
            )

            if available_qty <= 0:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "SELL blocked — no shares "
                        "are currently available"
                    ),
                    symbol=symbol,
                    status="error",
                    details={
                        "position_qty": position_qty,
                        "available_qty": available_qty,
                    },
                )

                return False

            # Never send more than Alpaca says is available.

            sell_quantity = min(
                requested_quantity,
                available_qty,
            )

            sell_quantity = round(
                sell_quantity,
                9,
            )

            if sell_quantity < self.MIN_QUANTITY:

                self.log(
                    agent="Risk Agent",
                    action=(
                        "SELL blocked — calculated "
                        "available quantity is too small"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "requested": requested_quantity,
                        "available": available_qty,
                    },
                )

                return False

            # ====================================================
            # 4. MARKET SELL
            # ====================================================

            self.current_stage = (
                "EXECUTING_EXIT"
            )

            self.log(
                agent="Supervisor",
                action=(
                    "Submitting SELL after protective "
                    "stop cancellation confirmed"
                ),
                symbol=symbol,
                details={
                    "reason": reason,
                    "position_quantity": position_qty,
                    "requested_quantity": requested_quantity,
                    "available_quantity": available_qty,
                    "sell_quantity": sell_quantity,
                    "estimated_price": estimated_price,
                },
            )

            order = await asyncio.to_thread(
                alpaca_service.submit_market_order,
                symbol=symbol,
                side="sell",
                quantity=sell_quantity,
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
                    "quantity": sell_quantity,
                    "estimated_price": estimated_price,
                    "estimated_value": (
                        estimated_price
                        * sell_quantity
                    ),
                    "confidence": confidence,
                    "risk_score": risk_score,
                    "reason": reason,
                },
            )

            # ====================================================
            # 5. WAIT FOR FILL
            # ====================================================

            self.current_stage = (
                "WAITING_FOR_SELL_FILL"
            )

            filled_order = (
                await asyncio.to_thread(
                    alpaca_service.wait_for_order_fill,
                    str(order.id),
                    self.FILL_TIMEOUT_SECONDS,
                    self.FILL_POLL_INTERVAL_SECONDS,
                )
            )

            if filled_order is None:

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        "SELL order did not resolve "
                        "within timeout"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "order_id": str(
                            order.id
                        ),
                    },
                )

                return False

            status = str(
                filled_order.status
            ).lower()

            # ====================================================
            # SELL REJECTED / CANCELLED
            # ====================================================

            if status != "filled":

                self.trades_rejected += 1

                self.log(
                    agent="Alpaca",
                    action=(
                        "SELL order did not fill"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "order_id": str(
                            order.id
                        ),
                        "status": status,
                    },
                )

                # ------------------------------------------------
                # Re-establish protection because the position
                # may still exist after the failed exit.
                # ------------------------------------------------

                remaining_position = (
                    await asyncio.to_thread(
                        alpaca_service.get_position,
                        symbol,
                    )
                )

                if remaining_position is not None:

                    remaining_qty = float(
                        remaining_position.qty
                    )

                    if remaining_qty > 0:

                        entry_price = float(
                            remaining_position.avg_entry_price
                        )

                        await self._ensure_position_protection(
                            symbol=symbol,
                            quantity=remaining_qty,
                            entry_price=entry_price,
                        )

                return False

            # ====================================================
            # 6. ACTUAL FILL
            # ====================================================

            try:

                filled_qty = float(
                    filled_order.filled_qty
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                filled_qty = sell_quantity

            try:

                filled_avg_price = float(
                    filled_order.filled_avg_price
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):

                filled_avg_price = (
                    estimated_price
                )

            # ====================================================
            # 7. VERIFY REMAINING POSITION
            # ====================================================

            await asyncio.sleep(
                0.5
            )

            remaining_position = (
                await asyncio.to_thread(
                    alpaca_service.get_position,
                    symbol,
                )
            )

            if remaining_position is None:

                remaining_qty = 0.0

            else:

                remaining_qty = float(
                    remaining_position.qty
                )

            # ====================================================
            # 8. RESTORE PROTECTION IF PARTIAL EXIT
            # ====================================================

            if remaining_qty > 0:

                remaining_entry = float(
                    remaining_position.avg_entry_price
                )

                self.log(
                    agent="Risk Agent",
                    action=(
                        "Partial SELL detected — "
                        "restoring protection"
                    ),
                    symbol=symbol,
                    status="warning",
                    details={
                        "remaining_quantity": remaining_qty,
                    },
                )

                stop_order = (
                    await self._ensure_position_protection(
                        symbol=symbol,
                        quantity=remaining_qty,
                        entry_price=remaining_entry,
                    )
                )

                if stop_order is not None:

                    self.protected_symbols.add(
                        symbol
                    )

            else:

                self.protected_symbols.discard(
                    symbol
                )

                self.breakeven_symbols.discard(
                    symbol
                )

            # ====================================================
            # 9. COUNT COMPLETED TRADE
            # ====================================================

            self.trades_executed += 1

            self.last_trade_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            self.log(
                agent="Alpaca",
                action=(
                    "SELL order filled"
                ),
                symbol=symbol,
                status="success",
                details={
                    "order_id": str(
                        filled_order.id
                    ),
                    "requested_quantity": (
                        sell_quantity
                    ),
                    "filled_quantity": filled_qty,
                    "filled_average_price": (
                        filled_avg_price
                    ),
                    "remaining_quantity": (
                        remaining_qty
                    ),
                    "reason": reason,
                },
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
                        filled_order.id
                    ),
                    "quantity_sold": filled_qty,
                    "fill_price": filled_avg_price,
                    "remaining_quantity": remaining_qty,
                    "reason": reason,
                },
            )

            return True

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

            # ====================================================
            # IMPORTANT RECOVERY
            #
            # If anything failed after the stop was cancelled,
            # check whether the position still exists and restore
            # protection.
            # ====================================================

            try:

                remaining_position = (
                    await asyncio.to_thread(
                        alpaca_service.get_position,
                        symbol,
                    )
                )

                if remaining_position is not None:

                    remaining_qty = float(
                        remaining_position.qty
                    )

                    if remaining_qty > 0:

                        entry_price = float(
                            remaining_position.avg_entry_price
                        )

                        await self._ensure_position_protection(
                            symbol=symbol,
                            quantity=remaining_qty,
                            entry_price=entry_price,
                        )

            except Exception as recovery_error:

                self.last_error = (
                    f"{error} | "
                    f"Protection recovery failed: "
                    f"{recovery_error}"
                )

                self.log(
                    agent="Risk Agent",
                    action=(
                        "CRITICAL — failed to restore "
                        "protection after SELL error"
                    ),
                    symbol=symbol,
                    status="error",
                    details=str(
                        recovery_error
                    ),
                )

            return False

        finally:

            self.exit_in_progress.discard(
                symbol
            )

            if self.running:

                self.current_stage = (
                    "WAITING"
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

            "max_total_exposure_percent": (
                self.MAX_TOTAL_EXPOSURE_PERCENT
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

            "cancel_timeout_seconds": (
                self.CANCEL_TIMEOUT_SECONDS
            ),

            "protected_symbols": list(
                self.protected_symbols
            ),

            "breakeven_symbols": list(
                self.breakeven_symbols
            ),

            "exit_in_progress": list(
                self.exit_in_progress
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

