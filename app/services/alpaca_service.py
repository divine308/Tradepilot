
from datetime import datetime, timedelta, timezone
import time

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    OrderType,
)

from alpaca.trading.requests import (
    MarketOrderRequest,
    StopOrderRequest,
    ReplaceOrderRequest,
)

from app.core.config import settings


class AlpacaService:

    def __init__(self):

        # ========================================================
        # TRADING CLIENT
        # ========================================================

        self.client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=settings.alpaca_paper,
        )

        # ========================================================
        # MARKET DATA CLIENT
        # ========================================================

        self.data_client = StockHistoricalDataClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
        )

    # ============================================================
    # ACCOUNT
    # ============================================================

    def get_account(self):
        return self.client.get_account()

    # ============================================================
    # POSITIONS
    # ============================================================

    def get_positions(self):
        return self.client.get_all_positions()

    def get_position(self, symbol: str):
        """
        Return a single position by symbol.

        Returns None if the position does not exist.
        """

        symbol = symbol.upper().strip()

        if not symbol:
            return None

        positions = self.client.get_all_positions()

        for position in positions:

            if not position.symbol:
                continue

            if position.symbol.upper() == symbol:
                return position

        return None

    # ============================================================
    # ORDERS
    # ============================================================

    def get_orders(self):
        return self.client.get_orders()

    # ============================================================
    # ACTIVE ORDERS
    # ============================================================

    def get_active_orders(self, symbol: str | None = None):
        """
        Return all active/open orders.

        If symbol is supplied, only orders for that symbol
        are returned.
        """

        orders = self.client.get_orders()

        if symbol is None:
            return orders

        symbol = symbol.upper().strip()

        return [
            order
            for order in orders
            if order.symbol
            and order.symbol.upper() == symbol
            and str(order.status).lower()
            not in {
                "filled",
                "canceled",
                "cancelled",
                "rejected",
                "expired",
            }
        ]

    # ============================================================
    # AVAILABLE SELL QUANTITY
    # ============================================================

    def get_available_sell_quantity(
        self,
        symbol: str,
    ) -> float:
        """
        Calculate the quantity of a position that is genuinely
        available for a NEW sell order.

        Example:

            Position = 21
            Existing sell stop = 21
            Available = 0

        This prevents Alpaca errors such as:

            insufficient qty available for order
        """

        symbol = symbol.upper().strip()

        if not symbol:
            return 0.0

        position = self.get_position(symbol)

        if position is None:
            return 0.0

        position_qty = float(
            position.qty or 0
        )

        if position_qty <= 0:
            return 0.0

        active_orders = self.get_active_orders(symbol)

        held_qty = 0.0

        for order in active_orders:

            if not order.symbol:
                continue

            if order.symbol.upper() != symbol:
                continue

            if order.side != OrderSide.SELL:
                continue

            order_qty = float(
                getattr(order, "qty", 0) or 0
            )

            filled_qty = float(
                getattr(order, "filled_qty", 0) or 0
            )

            remaining_qty = max(
                0.0,
                order_qty - filled_qty,
            )

            held_qty += remaining_qty

        available_qty = max(
            0.0,
            position_qty - held_qty,
        )

        return available_qty

    # ============================================================
    # SELL ORDER SUMMARY
    # ============================================================

    def get_sell_quantity_summary(
        self,
        symbol: str,
    ):
        """
        Useful for debugging and autonomous trading.

        Returns:

            position_qty
            held_qty
            available_qty
        """

        symbol = symbol.upper().strip()

        position = self.get_position(symbol)

        if position is None:
            return {
                "symbol": symbol,
                "position_qty": 0.0,
                "held_qty": 0.0,
                "available_qty": 0.0,
            }

        position_qty = float(
            position.qty or 0
        )

        active_orders = self.get_active_orders(symbol)

        held_qty = 0.0

        for order in active_orders:

            if order.side != OrderSide.SELL:
                continue

            order_qty = float(
                getattr(order, "qty", 0) or 0
            )

            filled_qty = float(
                getattr(order, "filled_qty", 0) or 0
            )

            held_qty += max(
                0.0,
                order_qty - filled_qty,
            )

        available_qty = max(
            0.0,
            position_qty - held_qty,
        )

        return {
            "symbol": symbol,
            "position_qty": position_qty,
            "held_qty": held_qty,
            "available_qty": available_qty,
        }

    # ============================================================
    # MARKET DATA
    # ============================================================

    def get_market_bars(
        self,
        symbol: str,
        timeframe: str = "1Min",
        limit: int = 200,
    ):

        symbol = symbol.upper().strip()

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        timeframe_map = {

            "1Min": TimeFrame.Minute,

            "5Min": TimeFrame(
                5,
                TimeFrameUnit.Minute,
            ),

            "15Min": TimeFrame(
                15,
                TimeFrameUnit.Minute,
            ),

            "1Hour": TimeFrame.Hour,

            "1Day": TimeFrame.Day,
        }

        selected_timeframe = timeframe_map.get(
            timeframe
        )

        if selected_timeframe is None:
            raise ValueError(
                "Invalid timeframe. "
                "Use 1Min, 5Min, 15Min, 1Hour, or 1Day."
            )

        limit = max(
            1,
            min(int(limit), 1000),
        )

        end = datetime.now(timezone.utc)

        if timeframe == "1Min":
            start = end - timedelta(days=7)

        elif timeframe == "5Min":
            start = end - timedelta(days=14)

        elif timeframe == "15Min":
            start = end - timedelta(days=30)

        elif timeframe == "1Hour":
            start = end - timedelta(days=90)

        else:
            start = end - timedelta(days=730)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=selected_timeframe,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.IEX,
        )

        try:

            response = self.data_client.get_stock_bars(
                request
            )

        except Exception as error:

            raise RuntimeError(
                f"Alpaca market data request failed: {error}"
            )

        if response is None:
            raise RuntimeError(
                "Alpaca returned an empty response."
            )

        try:

            symbol_bars = response[symbol]

        except Exception:

            raise RuntimeError(
                f"Alpaca returned no bar collection for {symbol}."
            )

        if not symbol_bars:
            return []

        result = []

        for bar in symbol_bars:

            result.append(
                {
                    "time": bar.timestamp.isoformat(),

                    "open": float(bar.open),

                    "high": float(bar.high),

                    "low": float(bar.low),

                    "close": float(bar.close),

                    "volume": int(bar.volume),

                    "vwap": (
                        float(bar.vwap)
                        if bar.vwap is not None
                        else None
                    ),

                    "trade_count": (
                        int(bar.trade_count)
                        if getattr(
                            bar,
                            "trade_count",
                            None,
                        ) is not None
                        else None
                    ),
                }
            )

        return result

    # ============================================================
    # MARKET ORDER
    # ============================================================

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ):

        symbol = symbol.upper().strip()
        side = side.lower().strip()

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        if side not in {"buy", "sell"}:
            raise ValueError(
                "Invalid order side. Use 'buy' or 'sell'."
            )

        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            raise ValueError(
                "Quantity must be a valid number."
            )

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        # ========================================================
        # BUY
        # ========================================================

        if side == "buy":

            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )

            return self.client.submit_order(
                order_data=request
            )

        # ========================================================
        # SELL
        #
        # IMPORTANT:
        # Never submit more shares than are actually available.
        # Existing stop-loss / sell orders may already reserve
        # part or all of the position.
        # ========================================================

        available_qty = (
            self.get_available_sell_quantity(
                symbol
            )
        )

        if available_qty <= 0:

            summary = (
                self.get_sell_quantity_summary(
                    symbol
                )
            )

            raise ValueError(
                f"No shares available to sell for {symbol}. "
                f"Position={summary['position_qty']}, "
                f"Held={summary['held_qty']}, "
                f"Available={summary['available_qty']}."
            )

        if quantity > available_qty:

            raise ValueError(
                f"Insufficient available quantity for {symbol}. "
                f"Requested={quantity}, "
                f"Available={available_qty}."
            )

        request = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

        return self.client.submit_order(
            order_data=request
        )

    # ============================================================
    # WAIT FOR ORDER FILL
    # ============================================================

    def wait_for_order_fill(
        self,
        order_id,
        timeout: int = 15,
        poll_interval: float = 0.5,
    ):

        deadline = time.time() + timeout

        last_order = None

        while time.time() < deadline:

            try:

                order = self.client.get_order_by_id(
                    order_id
                )

            except Exception as error:

                raise RuntimeError(
                    f"Failed to retrieve order status: {error}"
                )

            last_order = order

            status = str(
                order.status
            ).lower()

            if status == "filled":
                return order

            if status in {
                "canceled",
                "cancelled",
                "rejected",
                "expired",
            }:
                return order

            time.sleep(
                poll_interval
            )

        return last_order

    # ============================================================
    # SUBMIT PROTECTIVE STOP
    # ============================================================

    def submit_protective_stop(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
    ):

        symbol = symbol.upper().strip()

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            raise ValueError(
                "Quantity must be a valid number."
            )

        try:
            stop_price = float(stop_price)
        except (TypeError, ValueError):
            raise ValueError(
                "Stop price must be a valid number."
            )

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if stop_price <= 0:
            raise ValueError(
                "Stop price must be greater than zero."
            )

        # ========================================================
        # CHECK WHETHER AN ACTIVE PROTECTIVE STOP ALREADY EXISTS
        # ========================================================

        existing_stop = (
            self.get_active_protective_stop(
                symbol
            )
        )

        if existing_stop is not None:

            existing_qty = float(
                getattr(
                    existing_stop,
                    "qty",
                    0,
                )
                or 0
            )

            raise ValueError(
                f"An active protective stop already exists "
                f"for {symbol}. "
                f"Existing quantity={existing_qty}."
            )

        # ========================================================
        # IMPORTANT:
        #
        # A stop order itself reserves shares.
        #
        # Therefore we check the quantity against the current
        # position before creating the stop.
        # ========================================================

        position = self.get_position(symbol)

        if position is None:
            raise ValueError(
                f"No position exists for {symbol}. "
                "Cannot create protective stop."
            )

        position_qty = float(
            position.qty or 0
        )

        if quantity > position_qty:

            raise ValueError(
                f"Protective stop quantity exceeds position "
                f"for {symbol}. "
                f"Requested={quantity}, "
                f"Position={position_qty}."
            )

        # ========================================================
        # CHECK OTHER ACTIVE SELL ORDERS
        # ========================================================

        available_qty = (
            self.get_available_sell_quantity(
                symbol
            )
        )

        if quantity > available_qty:

            raise ValueError(
                f"Protective stop cannot reserve {quantity} "
                f"shares of {symbol}. "
                f"Only {available_qty} shares are currently "
                f"available."
            )

        request = StopOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            stop_price=round(
                stop_price,
                2,
            ),
        )

        return self.client.submit_order(
            order_data=request
        )

    # ============================================================
    # FIND ACTIVE PROTECTIVE STOP
    # ============================================================

    def get_active_protective_stop(
        self,
        symbol: str,
    ):

        symbol = symbol.upper().strip()

        orders = self.client.get_orders()

        for order in orders:

            if not order.symbol:
                continue

            if order.symbol.upper() != symbol:
                continue

            if order.side != OrderSide.SELL:
                continue

            if order.type not in {
                OrderType.STOP,
                OrderType.STOP_LIMIT,
            }:
                continue

            status = str(
                order.status
            ).lower()

            if status in {
                "filled",
                "canceled",
                "cancelled",
                "rejected",
                "expired",
            }:
                continue

            return order

        return None

    # ============================================================
    # GET ALL ACTIVE SELL ORDERS
    # ============================================================

    def get_active_sell_orders(
        self,
        symbol: str,
    ):

        symbol = symbol.upper().strip()

        orders = self.get_active_orders(
            symbol
        )

        return [
            order
            for order in orders
            if order.side == OrderSide.SELL
        ]

    # ============================================================
    # MOVE STOP TO BREAKEVEN
    # ============================================================

    def move_stop_to_breakeven(
        self,
        symbol: str,
        stop_price: float,
    ):

        symbol = symbol.upper().strip()

        if stop_price <= 0:
            raise ValueError(
                "Stop price must be greater than zero."
            )

        stop_order = (
            self.get_active_protective_stop(
                symbol
            )
        )

        if stop_order is None:
            return None

        replacement = ReplaceOrderRequest(
            stop_price=round(
                stop_price,
                2,
            )
        )

        return self.client.replace_order_by_id(
            stop_order.id,
            replacement,
        )

    # ============================================================
    # CANCEL PROTECTIVE STOP
    # ============================================================

    def cancel_protective_stop(
        self,
        symbol: str,
    ):

        symbol = symbol.upper().strip()

        stop_order = (
            self.get_active_protective_stop(
                symbol
            )
        )

        if stop_order is None:
            return None

        return self.client.cancel_order_by_id(
            stop_order.id
        )

    # ============================================================
    # CANCEL ALL ORDERS
    # ============================================================

    def cancel_all_orders(self):
        return self.client.cancel_orders()

    # ============================================================
    # CLOSE POSITION
    # ============================================================

    def close_position(
        self,
        symbol: str,
        timeout: int = 15,
        poll_interval: float = 0.5,
    ):

        symbol = symbol.upper().strip()

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        # Alpaca's close-position endpoint can cancel orders
        # associated with the position automatically.

        try:

            self.client.close_position(
                symbol,
                cancel_orders=True,
            )

        except Exception as error:

            raise RuntimeError(
                f"Failed to close {symbol}: {error}"
            )

        deadline = time.time() + timeout

        while time.time() < deadline:

            time.sleep(
                poll_interval
            )

            position = self.get_position(
                symbol
            )

            if position is None:

                return {
                    "closed": True,
                    "symbol": symbol,
                }

        position = self.get_position(
            symbol
        )

        return {
            "closed": position is None,
            "symbol": symbol,
            "remaining_qty": (
                float(position.qty)
                if position is not None
                else 0.0
            ),
        }

    # ============================================================
    # CLOSE ALL POSITIONS
    # ============================================================

    def close_all_positions(
        self,
        timeout: int = 15,
        poll_interval: float = 0.5,
    ):

        positions_before = (
            self.client.get_all_positions()
        )

        if not positions_before:

            return {
                "closed": True,
                "count": 0,
            }

        position_count = len(
            positions_before
        )

        try:

            self.client.close_all_positions(
                cancel_orders=True
            )

        except Exception as error:

            raise RuntimeError(
                f"Failed to close all positions: {error}"
            )

        deadline = (
            time.time()
            + timeout
        )

        while time.time() < deadline:

            time.sleep(
                poll_interval
            )

            current_positions = (
                self.client.get_all_positions()
            )

            if not current_positions:

                return {
                    "closed": True,
                    "count": position_count,
                }

        current_positions = (
            self.client.get_all_positions()
        )

        return {
            "closed": not bool(
                current_positions
            ),
            "count": position_count,
            "remaining": len(
                current_positions
            ),
        }


# ================================================================
# SINGLE SERVICE INSTANCE
# ================================================================

alpaca_service = AlpacaService()

