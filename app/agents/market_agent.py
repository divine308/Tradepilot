from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from app.core.config import settings


class MarketAgent:

    def __init__(self):
        self.client = StockHistoricalDataClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
        )

    def analyze(self, symbol: str):

        symbol = symbol.upper().strip()

        # --------------------------------------------------
        # Request 90 days of daily market data
        # IEX is used because the current Alpaca subscription
        # does not permit recent SIP data.
        # --------------------------------------------------

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=90)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )

        bars = self.client.get_stock_bars(request)

        data = bars.df

        # --------------------------------------------------
        # No data
        # --------------------------------------------------

        if data.empty:
            return {
                "symbol": symbol,
                "available": False,
                "reason": "No market data available.",
            }

        # --------------------------------------------------
        # Clean dataframe
        # --------------------------------------------------

        if isinstance(data.index, pd.MultiIndex):
            data = data.reset_index()

            if "symbol" in data.columns:
                data = data[
                    data["symbol"] == symbol
                ]

            data = data.sort_values(
                by="timestamp"
            )

        else:
            data = data.sort_index()

        if data.empty:
            return {
                "symbol": symbol,
                "available": False,
                "reason": "No market data available for symbol.",
            }

        # --------------------------------------------------
        # Basic OHLCV data
        # --------------------------------------------------

        close = data["close"].astype(float)
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        volume = data["volume"].astype(float)

        latest = data.iloc[-1]

        current_price = float(
            close.iloc[-1]
        )

        # --------------------------------------------------
        # Moving averages
        # --------------------------------------------------

        sma_20 = close.rolling(
            window=20
        ).mean()

        sma_50 = close.rolling(
            window=50
        ).mean()

        ema_12 = close.ewm(
            span=12,
            adjust=False,
        ).mean()

        ema_26 = close.ewm(
            span=26,
            adjust=False,
        ).mean()

        # --------------------------------------------------
        # RSI 14
        # --------------------------------------------------

        delta = close.diff()

        gains = delta.clip(
            lower=0
        )

        losses = -delta.clip(
            upper=0
        )

        avg_gain = gains.rolling(
            window=14
        ).mean()

        avg_loss = losses.rolling(
            window=14
        ).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            np.nan,
        )

        rsi = 100 - (
            100 / (1 + rs)
        )

        # --------------------------------------------------
        # MACD
        # --------------------------------------------------

        macd = ema_12 - ema_26

        signal = macd.ewm(
            span=9,
            adjust=False,
        ).mean()

        macd_histogram = (
            macd - signal
        )

        # --------------------------------------------------
        # Returns
        # --------------------------------------------------

        daily_return = close.pct_change()

        if len(close) >= 6:
            return_5d = (
                current_price
                / float(close.iloc[-6])
            ) - 1
        else:
            return_5d = 0.0

        if len(close) >= 21:
            return_20d = (
                current_price
                / float(close.iloc[-21])
            ) - 1
        else:
            return_20d = 0.0

        # --------------------------------------------------
        # Volatility
        # --------------------------------------------------

        volatility_20d = (
            daily_return
            .rolling(window=20)
            .std()
            * np.sqrt(252)
        )

        # --------------------------------------------------
        # Volume analysis
        # --------------------------------------------------

        volume_sma_20 = (
            volume
            .rolling(window=20)
            .mean()
        )

        latest_volume = float(
            volume.iloc[-1]
        )

        if pd.isna(
            volume_sma_20.iloc[-1]
        ):
            average_volume = latest_volume
        else:
            average_volume = float(
                volume_sma_20.iloc[-1]
            )

        if average_volume > 0:
            volume_ratio = (
                latest_volume
                / average_volume
            )
        else:
            volume_ratio = 1.0

        # --------------------------------------------------
        # Support / resistance
        # --------------------------------------------------

        recent_high = float(
            high.tail(20).max()
        )

        recent_low = float(
            low.tail(20).min()
        )

        # --------------------------------------------------
        # Current indicator values
        # --------------------------------------------------

        current_sma_20 = (
            float(sma_20.iloc[-1])
            if not pd.isna(
                sma_20.iloc[-1]
            )
            else current_price
        )

        current_sma_50 = (
            float(sma_50.iloc[-1])
            if not pd.isna(
                sma_50.iloc[-1]
            )
            else current_price
        )

        current_ema_12 = float(
            ema_12.iloc[-1]
        )

        current_ema_26 = float(
            ema_26.iloc[-1]
        )

        current_rsi = (
            float(rsi.iloc[-1])
            if not pd.isna(
                rsi.iloc[-1]
            )
            else 50.0
        )

        current_macd = float(
            macd.iloc[-1]
        )

        current_signal = float(
            signal.iloc[-1]
        )

        current_histogram = float(
            macd_histogram.iloc[-1]
        )

        current_volatility = (
            float(
                volatility_20d.iloc[-1]
            )
            if not pd.isna(
                volatility_20d.iloc[-1]
            )
            else 0.0
        )

        # --------------------------------------------------
        # Trend detection
        # --------------------------------------------------

        if (
            current_price > current_sma_20
            and current_sma_20 > current_sma_50
            and current_ema_12 > current_ema_26
        ):

            trend = "BULLISH"

        elif (
            current_price < current_sma_20
            and current_sma_20 < current_sma_50
            and current_ema_12 < current_ema_26
        ):

            trend = "BEARISH"

        else:

            trend = "NEUTRAL"

        # --------------------------------------------------
        # RSI signal
        # --------------------------------------------------

        if current_rsi >= 70:

            rsi_signal = "OVERBOUGHT"

        elif current_rsi <= 30:

            rsi_signal = "OVERSOLD"

        else:

            rsi_signal = "NEUTRAL"

        # --------------------------------------------------
        # MACD signal
        # --------------------------------------------------

        if current_macd > current_signal:

            macd_signal = "BULLISH"

        elif current_macd < current_signal:

            macd_signal = "BEARISH"

        else:

            macd_signal = "NEUTRAL"

        # --------------------------------------------------
        # Volume signal
        # --------------------------------------------------

        if volume_ratio >= 1.5:

            volume_signal = "HIGH"

        elif volume_ratio <= 0.7:

            volume_signal = "LOW"

        else:

            volume_signal = "NORMAL"

        # --------------------------------------------------
        # Price position inside 20-day range
        # --------------------------------------------------

        price_range = (
            recent_high - recent_low
        )

        if price_range > 0:

            range_position = (
                (current_price - recent_low)
                / price_range
            )

        else:

            range_position = 0.5

        # --------------------------------------------------
        # Return market intelligence
        # --------------------------------------------------

        return {
            "symbol": symbol,

            "available": True,

            "price": {
                "current": current_price,
                "open": float(
                    latest["open"]
                ),
                "high": float(
                    latest["high"]
                ),
                "low": float(
                    latest["low"]
                ),
                "close": current_price,
            },

            "volume": {
                "current": latest_volume,
                "average_20d": round(
                    average_volume,
                    2,
                ),
                "ratio": round(
                    volume_ratio,
                    4,
                ),
                "signal": volume_signal,
            },

            "moving_averages": {
                "sma_20": round(
                    current_sma_20,
                    4,
                ),
                "sma_50": round(
                    current_sma_50,
                    4,
                ),
                "ema_12": round(
                    current_ema_12,
                    4,
                ),
                "ema_26": round(
                    current_ema_26,
                    4,
                ),
            },

            "momentum": {
                "rsi_14": round(
                    current_rsi,
                    2,
                ),
                "rsi_signal": rsi_signal,

                "macd": round(
                    current_macd,
                    6,
                ),

                "macd_signal": round(
                    current_signal,
                    6,
                ),

                "macd_histogram": round(
                    current_histogram,
                    6,
                ),

                "macd_signal_direction": (
                    macd_signal
                ),
            },

            "performance": {
                "return_5d": round(
                    return_5d * 100,
                    2,
                ),

                "return_20d": round(
                    return_20d * 100,
                    2,
                ),

                "volatility_20d": round(
                    current_volatility * 100,
                    2,
                ),
            },

            "levels": {
                "20d_high": recent_high,
                "20d_low": recent_low,
                "range_position": round(
                    range_position,
                    4,
                ),
            },

            "trend": trend,

            "data_points": len(data),

            "data_feed": "IEX",
        }


market_agent = MarketAgent()