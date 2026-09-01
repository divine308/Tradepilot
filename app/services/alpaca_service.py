
# from datetime import datetime, timedelta, timezone

# from alpaca.data.historical import StockHistoricalDataClient
# from alpaca.data.requests import StockBarsRequest
# from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
# from alpaca.data.enums import DataFeed

# from alpaca.trading.client import TradingClient
# from alpaca.trading.enums import OrderSide, TimeInForce
# from alpaca.trading.requests import MarketOrderRequest

# from app.core.config import settings


# class AlpacaService:

#     def __init__(self):

#         # ========================================================
#         # TRADING CLIENT
#         # ========================================================

#         self.client = TradingClient(
#             settings.alpaca_api_key,
#             settings.alpaca_secret_key,
#             paper=settings.alpaca_paper,
#         )

#         # ========================================================
#         # MARKET DATA CLIENT
#         # ========================================================

#         self.data_client = StockHistoricalDataClient(
#             settings.alpaca_api_key,
#             settings.alpaca_secret_key,
#         )

#     # ============================================================
#     # ACCOUNT
#     # ============================================================

#     def get_account(self):
#         return self.client.get_account()

#     # ============================================================
#     # POSITIONS
#     # ============================================================

#     def get_positions(self):
#         return self.client.get_all_positions()

#     # ============================================================
#     # ORDERS
#     # ============================================================

#     def get_orders(self):
#         return self.client.get_orders()

#     # ============================================================
#     # MARKET DATA
#     # ============================================================

#     def get_market_bars(
#         self,
#         symbol: str,
#         timeframe: str = "1Min",
#         limit: int = 200,
#     ):

#         symbol = symbol.upper().strip()

#         if not symbol:
#             raise ValueError("Symbol is required.")

#         # ========================================================
#         # TIMEFRAME
#         # ========================================================

#         timeframe_map = {
#             "1Min": TimeFrame.Minute,

#             "5Min": TimeFrame(
#                 5,
#                 TimeFrameUnit.Minute,
#             ),

#             "15Min": TimeFrame(
#                 15,
#                 TimeFrameUnit.Minute,
#             ),

#             "1Hour": TimeFrame.Hour,

#             "1Day": TimeFrame.Day,
#         }

#         selected_timeframe = timeframe_map.get(timeframe)

#         if selected_timeframe is None:
#             raise ValueError(
#                 "Invalid timeframe. "
#                 "Use 1Min, 5Min, 15Min, 1Hour, or 1Day."
#             )

#         # ========================================================
#         # LIMIT
#         # ========================================================

#         limit = max(
#             1,
#             min(int(limit), 1000),
#         )

#         # ========================================================
#         # DATE RANGE
#         # ========================================================

#         end = datetime.now(timezone.utc)

#         if timeframe == "1Min":
#             start = end - timedelta(days=7)

#         elif timeframe == "5Min":
#             start = end - timedelta(days=14)

#         elif timeframe == "15Min":
#             start = end - timedelta(days=30)

#         elif timeframe == "1Hour":
#             start = end - timedelta(days=90)

#         else:
#             start = end - timedelta(days=730)

#         # ========================================================
#         # DEBUG
#         # ========================================================

#         print()
#         print("====================================================")
#         print("ALPACA MARKET DATA REQUEST")
#         print("====================================================")
#         print(f"Symbol:     {symbol}")
#         print(f"Timeframe:  {timeframe}")
#         print(f"Limit:      {limit}")
#         print(f"Start:      {start}")
#         print(f"End:        {end}")
#         print("Feed:       IEX")
#         print("====================================================")

#         # ========================================================
#         # REQUEST
#         # ========================================================

#         request = StockBarsRequest(
#             symbol_or_symbols=symbol,
#             timeframe=selected_timeframe,
#             start=start,
#             end=end,
#             limit=limit,
#             feed=DataFeed.IEX,
#         )

#         # ========================================================
#         # ALPACA REQUEST
#         # ========================================================

#         try:

#             response = self.data_client.get_stock_bars(
#                 request
#             )

#         except Exception as error:

#             print()
#             print("====================================================")
#             print("ALPACA MARKET DATA ERROR")
#             print("====================================================")
#             print(repr(error))
#             print("====================================================")

#             raise RuntimeError(
#                 f"Alpaca market data request failed: {error}"
#             )

#         # ========================================================
#         # RESPONSE DEBUG
#         # ========================================================

#         print()
#         print("====================================================")
#         print("ALPACA RESPONSE")
#         print("====================================================")
#         print(response)
#         print("====================================================")

#         # ========================================================
#         # RESPONSE CHECK
#         # ========================================================

#         if response is None:
#             raise RuntimeError(
#                 "Alpaca returned an empty response."
#             )

#         # ========================================================
#         # GET SYMBOL BARS
#         # ========================================================

#         try:

#             symbol_bars = response[symbol]

#         except Exception as error:

#             print()
#             print("====================================================")
#             print("SYMBOL NOT FOUND IN ALPACA RESPONSE")
#             print("====================================================")
#             print(f"Requested symbol: {symbol}")
#             print(f"Response type: {type(response)}")
#             print(f"Response: {response}")
#             print(f"Error: {repr(error)}")
#             print("====================================================")

#             raise RuntimeError(
#                 f"Alpaca returned no bar collection for {symbol}."
#             )

#         # ========================================================
#         # EMPTY BARS
#         # ========================================================

#         if not symbol_bars:

#             print()
#             print("====================================================")
#             print("ZERO BARS RETURNED")
#             print("====================================================")
#             print(f"Symbol: {symbol}")
#             print(f"Timeframe: {timeframe}")
#             print(f"Start: {start}")
#             print(f"End: {end}")
#             print("====================================================")

#             return []

#         # ========================================================
#         # FORMAT BARS
#         # ========================================================

#         result = []

#         for bar in symbol_bars:

#             result.append(
#                 {
#                     "time": bar.timestamp.isoformat(),

#                     "open": float(bar.open),

#                     "high": float(bar.high),

#                     "low": float(bar.low),

#                     "close": float(bar.close),

#                     "volume": int(bar.volume),

#                     "vwap": (
#                         float(bar.vwap)
#                         if bar.vwap is not None
#                         else None
#                     ),

#                     "trade_count": (
#                         int(bar.trade_count)
#                         if getattr(
#                             bar,
#                             "trade_count",
#                             None,
#                         ) is not None
#                         else None
#                     ),
#                 }
#             )

#         print()
#         print("====================================================")
#         print("MARKET DATA SUCCESS")
#         print("====================================================")
#         print(f"Symbol: {symbol}")
#         print(f"Bars returned: {len(result)}")
#         print("====================================================")

#         return result

#     # ============================================================
#     # MARKET ORDER
#     # ============================================================

#     def submit_market_order(
#         self,
#         symbol: str,
#         side: str,
#         quantity: float,
#     ):

#         symbol = symbol.upper().strip()
#         side = side.lower().strip()

#         if side == "buy":
#             order_side = OrderSide.BUY

#         elif side == "sell":
#             order_side = OrderSide.SELL

#         else:
#             raise ValueError(
#                 "Invalid order side."
#             )

#         if quantity <= 0:
#             raise ValueError(
#                 "Quantity must be greater than zero."
#             )

#         request = MarketOrderRequest(
#             symbol=symbol,
#             qty=quantity,
#             side=order_side,
#             time_in_force=TimeInForce.DAY,
#         )

#         return self.client.submit_order(
#             order_data=request
#         )

#     # ============================================================
#     # CANCEL ALL ORDERS
#     # ============================================================

#     def cancel_all_orders(self):
#         return self.client.cancel_orders()


# alpaca_service = AlpacaService()



from datetime import datetime, timedelta, timezone

from alpaca.data.historical import (
    StockHistoricalDataClient,
)
from alpaca.data.requests import (
    StockBarsRequest,
)
from alpaca.data.timeframe import (
    TimeFrame,
    TimeFrameUnit,
)
from alpaca.data.enums import DataFeed

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    OrderClass,
    OrderType,
)
from alpaca.trading.requests import (
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
    ReplaceOrderRequest,
)

from app.core.config import settings

import time

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

        selected_timeframe = (
            timeframe_map.get(timeframe)
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

        end = datetime.now(
            timezone.utc
        )

        if timeframe == "1Min":

            start = end - timedelta(
                days=7
            )

        elif timeframe == "5Min":

            start = end - timedelta(
                days=14
            )

        elif timeframe == "15Min":

            start = end - timedelta(
                days=30
            )

        elif timeframe == "1Hour":

            start = end - timedelta(
                days=90
            )

        else:

            start = end - timedelta(
                days=730
            )

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=selected_timeframe,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.IEX,
        )

        try:

            response = (
                self.data_client.get_stock_bars(
                    request
                )
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
                    "time": (
                        bar.timestamp.isoformat()
                    ),

                    "open": float(
                        bar.open
                    ),

                    "high": float(
                        bar.high
                    ),

                    "low": float(
                        bar.low
                    ),

                    "close": float(
                        bar.close
                    ),

                    "volume": int(
                        bar.volume
                    ),

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
    # WITH OPTIONAL BRACKET PROTECTION
    # ============================================================

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
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

        # ========================================================
        # BRACKET ORDER
        # ========================================================

        if (
            stop_loss_price is not None
            and take_profit_price is not None
        ):

            if stop_loss_price <= 0:

                raise ValueError(
                    "Invalid stop-loss price."
                )

            if take_profit_price <= 0:

                raise ValueError(
                    "Invalid take-profit price."
                )

            # ----------------------------------------------------
            # BUY
            # ----------------------------------------------------

            if order_side == OrderSide.BUY:

                if not (
                    stop_loss_price
                    < take_profit_price
                ):

                    raise ValueError(
                        "For BUY orders, "
                        "stop loss must be below "
                        "take profit."
                    )

            # ----------------------------------------------------
            # SELL
            # ----------------------------------------------------

            else:

                if not (
                    take_profit_price
                    < stop_loss_price
                ):

                    raise ValueError(
                        "For SELL orders, "
                        "take profit must be below "
                        "stop loss."
                    )

            request = MarketOrderRequest(

                symbol=symbol,

                qty=quantity,

                side=order_side,

                time_in_force=TimeInForce.DAY,

                order_class=OrderClass.BRACKET,

                take_profit=TakeProfitRequest(
                    limit_price=round(
                        take_profit_price,
                        2,
                    )
                ),

                stop_loss=StopLossRequest(
                    stop_price=round(
                        stop_loss_price,
                        2,
                    )
                ),
            )

        # ========================================================
        # NORMAL MARKET ORDER
        # ========================================================

        else:

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
    # MOVE STOP TO BREAKEVEN
    # ============================================================

    def move_stop_to_breakeven(
        self,
        symbol: str,
        stop_price: float,
    ):

        symbol = symbol.upper().strip()

        orders = self.client.get_orders()

        candidates = []

        for order in orders:

            if not order.symbol:
                continue

            if (
                order.symbol.upper()
                != symbol
            ):
                continue

            # ----------------------------------------------------
            # We only want SELL protective orders
            # ----------------------------------------------------

            if order.side != OrderSide.SELL:
                continue

            # ----------------------------------------------------
            # We only want stop orders
            # ----------------------------------------------------

            if order.type not in {
                OrderType.STOP,
                OrderType.STOP_LIMIT,
            }:
                continue

            # ----------------------------------------------------
            # Only active orders
            # ----------------------------------------------------

            status = str(
                order.status
            ).lower()

            if any(
                value in status
                for value in [
                    "filled",
                    "canceled",
                    "rejected",
                    "expired",
                ]
            ):
                continue

            candidates.append(order)

        if not candidates:

            return None

        # --------------------------------------------------------
        # Use the first active protective stop
        # --------------------------------------------------------

        stop_order = candidates[0]

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
        """
        Close every open position in the Alpaca account.

        Existing open orders, including bracket protection,
        are cancelled before the positions are closed.

        The method waits until Alpaca confirms that the
        positions are actually gone.
        """

        # --------------------------------------------------------
        # Check current positions
        # --------------------------------------------------------

        positions_before = self.client.get_all_positions()

        if not positions_before:
            return {
                "closed": True,
                "count": 0,
            }

        position_count = len(positions_before)

        # --------------------------------------------------------
        # Submit close request
        # --------------------------------------------------------

        self.client.close_all_positions(
            cancel_orders=True
        )

        # --------------------------------------------------------
        # Wait for Alpaca to update positions
        # --------------------------------------------------------

        deadline = time.time() + timeout

        while time.time() < deadline:

            time.sleep(poll_interval)

            current_positions = (
                self.client.get_all_positions()
            )

            if not current_positions:

                return {
                    "closed": True,
                    "count": position_count,
                }

        # --------------------------------------------------------
        # Final check after timeout
        # --------------------------------------------------------

        current_positions = (
            self.client.get_all_positions()
        )

        return {
            "closed": not bool(current_positions),
            "count": position_count,
            "remaining": len(current_positions),
        }


# ============================================================
# ALPACA SERVICE INSTANCE
# ============================================================

alpaca_service = AlpacaService()

