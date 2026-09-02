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

    # ============================================================
    # ORDERS
    # ============================================================

    def get_orders(self):
        return self.client.get_orders()

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
            raise ValueError("Symbol is required.")

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

        selected_timeframe = timeframe_map.get(timeframe)

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
    # SIMPLE MARKET ORDER
    #
    # IMPORTANT:
    # Fractional quantities are submitted as SIMPLE orders.
    # No bracket / OCO / OTO is used here.
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

        if side == "buy":
            order_side = OrderSide.BUY

        elif side == "sell":
            order_side = OrderSide.SELL

        else:
            raise ValueError(
                "Invalid order side."
            )

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        request = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=order_side,
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

            order = self.client.get_order_by_id(
                order_id
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
    #
    # This is a SIMPLE stop order, which supports fractional
    # quantities with DAY time-in-force.
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

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if stop_price <= 0:
            raise ValueError(
                "Stop price must be greater than zero."
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
    # MOVE STOP TO BREAKEVEN
    # ============================================================

    def move_stop_to_breakeven(
        self,
        symbol: str,
        stop_price: float,
    ):

        symbol = symbol.upper().strip()

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

        self.client.close_all_positions(
            cancel_orders=True
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


# ============================================================
# SINGLE SERVICE INSTANCE
# ============================================================

alpaca_service = AlpacaService()

