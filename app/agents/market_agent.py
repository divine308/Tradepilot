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

        # ============================================================
        # MARKET DATA
        # ============================================================

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

        if data.empty:
            return {
                "symbol": symbol,
                "available": False,
                "reason": "No market data available.",
            }

        # ============================================================
        # CLEAN DATAFRAME
        # ============================================================

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

        # Need enough data for meaningful analysis
        if len(data) < 55:
            return {
                "symbol": symbol,
                "available": False,
                "reason": (
                    "Insufficient historical data "
                    "for reliable analysis."
                ),
            }

        # ============================================================
        # OHLCV
        # ============================================================

        close = data["close"].astype(float)
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        volume = data["volume"].astype(float)

        latest = data.iloc[-1]

        current_price = float(
            close.iloc[-1]
        )

        # ============================================================
        # MOVING AVERAGES
        # ============================================================

        sma_20 = close.rolling(
            window=20
        ).mean()

        sma_50 = close.rolling(
            window=50
        ).mean()

        sma_200 = close.rolling(
            window=200
        ).mean()

        ema_12 = close.ewm(
            span=12,
            adjust=False,
        ).mean()

        ema_26 = close.ewm(
            span=26,
            adjust=False,
        ).mean()

        current_sma_20 = float(
            sma_20.iloc[-1]
        )

        current_sma_50 = float(
            sma_50.iloc[-1]
        )

        current_sma_200 = (
            float(sma_200.iloc[-1])
            if not pd.isna(sma_200.iloc[-1])
            else None
        )

        current_ema_12 = float(
            ema_12.iloc[-1]
        )

        current_ema_26 = float(
            ema_26.iloc[-1]
        )

        # ============================================================
        # MOVING AVERAGE SLOPES
        # ============================================================

        sma_20_slope = 0.0
        sma_50_slope = 0.0

        if len(sma_20) >= 6 and not pd.isna(
            sma_20.iloc[-6]
        ):
            sma_20_slope = (
                current_sma_20 /
                float(sma_20.iloc[-6])
            ) - 1

        if len(sma_50) >= 6 and not pd.isna(
            sma_50.iloc[-6]
        ):
            sma_50_slope = (
                current_sma_50 /
                float(sma_50.iloc[-6])
            ) - 1

        # ============================================================
        # RSI 14
        # ============================================================

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

        current_rsi = (
            float(rsi.iloc[-1])
            if not pd.isna(rsi.iloc[-1])
            else 50.0
        )

        # ============================================================
        # MACD
        # ============================================================

        macd = ema_12 - ema_26

        signal = macd.ewm(
            span=9,
            adjust=False,
        ).mean()

        macd_histogram = (
            macd - signal
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

        previous_histogram = (
            float(macd_histogram.iloc[-2])
            if len(macd_histogram) >= 2
            else current_histogram
        )

        histogram_change = (
            current_histogram -
            previous_histogram
        )

        if current_macd > current_signal:
            macd_signal = "BULLISH"
        elif current_macd < current_signal:
            macd_signal = "BEARISH"
        else:
            macd_signal = "NEUTRAL"

        if histogram_change > 0:
            macd_momentum = "ACCELERATING"
        elif histogram_change < 0:
            macd_momentum = "WEAKENING"
        else:
            macd_momentum = "FLAT"

        # ============================================================
        # RETURNS
        # ============================================================

        daily_return = close.pct_change()

        if len(close) >= 6:
            return_5d = (
                current_price /
                float(close.iloc[-6])
            ) - 1
        else:
            return_5d = 0.0

        if len(close) >= 21:
            return_20d = (
                current_price /
                float(close.iloc[-21])
            ) - 1
        else:
            return_20d = 0.0

        # ============================================================
        # VOLATILITY
        # ============================================================

        volatility_20d = (
            daily_return
            .rolling(window=20)
            .std()
            * np.sqrt(252)
        )

        current_volatility = (
            float(volatility_20d.iloc[-1])
            if not pd.isna(
                volatility_20d.iloc[-1]
            )
            else 0.0
        )

        # ============================================================
        # ATR 14
        # ============================================================

        previous_close = close.shift(1)

        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr_14 = true_range.rolling(
            window=14
        ).mean()

        current_atr = (
            float(atr_14.iloc[-1])
            if not pd.isna(atr_14.iloc[-1])
            else 0.0
        )

        atr_percent = (
            current_atr / current_price
            if current_price > 0
            else 0.0
        )

        # ============================================================
        # VOLUME
        # ============================================================

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
                latest_volume /
                average_volume
            )
        else:
            volume_ratio = 1.0

        if volume_ratio >= 1.5:
            volume_signal = "HIGH"
        elif volume_ratio <= 0.7:
            volume_signal = "LOW"
        else:
            volume_signal = "NORMAL"

        # ============================================================
        # PRICE STRUCTURE
        # ============================================================

        recent_high = float(
            high.tail(20).max()
        )

        recent_low = float(
            low.tail(20).min()
        )

        price_range = (
            recent_high -
            recent_low
        )

        if price_range > 0:
            range_position = (
                (current_price - recent_low)
                / price_range
            )
        else:
            range_position = 0.5

        distance_from_high = (
            (current_price / recent_high) - 1
            if recent_high > 0
            else 0.0
        )

        distance_from_low = (
            (current_price / recent_low) - 1
            if recent_low > 0
            else 0.0
        )

        # ============================================================
        # BREAKOUT DETECTION
        # ============================================================

        previous_20d_high = float(
            high.iloc[-21:-1].max()
        )

        previous_20d_low = float(
            low.iloc[-21:-1].min()
        )

        bullish_breakout = (
            current_price >
            previous_20d_high
            and volume_ratio >= 1.2
        )

        bearish_breakdown = (
            current_price <
            previous_20d_low
            and volume_ratio >= 1.2
        )

        if bullish_breakout:
            structure_signal = "BULLISH_BREAKOUT"
        elif bearish_breakdown:
            structure_signal = "BEARISH_BREAKDOWN"
        elif range_position >= 0.75:
            structure_signal = "NEAR_RANGE_HIGH"
        elif range_position <= 0.25:
            structure_signal = "NEAR_RANGE_LOW"
        else:
            structure_signal = "MID_RANGE"

        # ============================================================
        # PULLBACK DETECTION
        # ============================================================

        bullish_trend_structure = (
            current_price > current_sma_20
            and current_sma_20 > current_sma_50
            and current_ema_12 > current_ema_26
        )

        bearish_trend_structure = (
            current_price < current_sma_20
            and current_sma_20 < current_sma_50
            and current_ema_12 < current_ema_26
        )

        bullish_pullback = (
            bullish_trend_structure
            and current_price <= current_sma_20 * 1.02
            and current_price >= current_sma_20 * 0.97
            and current_rsi < 60
        )

        bearish_pullback = (
            bearish_trend_structure
            and current_price >= current_sma_20 * 0.98
            and current_price <= current_sma_20 * 1.03
            and current_rsi > 40
        )

        if bullish_pullback:
            pullback_signal = "BULLISH_PULLBACK"
        elif bearish_pullback:
            pullback_signal = "BEARISH_PULLBACK"
        else:
            pullback_signal = "NONE"

        # ============================================================
        # RSI SIGNAL
        # ============================================================

        if current_rsi >= 70:
            rsi_signal = "OVERBOUGHT"
        elif current_rsi <= 30:
            rsi_signal = "OVERSOLD"
        elif current_rsi >= 55:
            rsi_signal = "BULLISH"
        elif current_rsi <= 45:
            rsi_signal = "BEARISH"
        else:
            rsi_signal = "NEUTRAL"

        # ============================================================
        # TREND DETECTION
        # ============================================================

        bullish_alignment = (
            current_price > current_sma_20
            and current_sma_20 > current_sma_50
            and current_ema_12 > current_ema_26
            and sma_20_slope > 0
            and sma_50_slope > 0
        )

        bearish_alignment = (
            current_price < current_sma_20
            and current_sma_20 < current_sma_50
            and current_ema_12 < current_ema_26
            and sma_20_slope < 0
            and sma_50_slope < 0
        )

        if bullish_alignment:
            trend = "STRONG_BULLISH"
        elif bearish_alignment:
            trend = "STRONG_BEARISH"
        elif (
            current_price > current_sma_20
            and current_ema_12 > current_ema_26
        ):
            trend = "BULLISH"
        elif (
            current_price < current_sma_20
            and current_ema_12 < current_ema_26
        ):
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # ============================================================
        # QUANTITATIVE SCORE
        # ============================================================

        score = 50

        # ------------------------------------------------------------
        # Trend contribution
        # ------------------------------------------------------------

        if trend == "STRONG_BULLISH":
            score += 20
        elif trend == "BULLISH":
            score += 12
        elif trend == "BEARISH":
            score -= 12
        elif trend == "STRONG_BEARISH":
            score -= 20

        # ------------------------------------------------------------
        # Momentum contribution
        # ------------------------------------------------------------

        if macd_signal == "BULLISH":
            score += 8
        elif macd_signal == "BEARISH":
            score -= 8

        if macd_momentum == "ACCELERATING":
            score += 5
        elif macd_momentum == "WEAKENING":
            score -= 3

        # ------------------------------------------------------------
        # RSI contribution
        # ------------------------------------------------------------

        if 50 <= current_rsi < 70:
            score += 5
        elif 30 < current_rsi < 50:
            score -= 2
        elif current_rsi >= 75:
            score -= 5
        elif current_rsi <= 25:
            score += 3

        # ------------------------------------------------------------
        # Volume contribution
        # ------------------------------------------------------------

        if volume_ratio >= 1.5:
            if (
                current_price >=
                float(close.iloc[-2])
            ):
                score += 8
            else:
                score -= 6

        elif volume_ratio <= 0.7:
            score -= 2

        # ------------------------------------------------------------
        # Performance contribution
        # ------------------------------------------------------------

        if return_5d > 0:
            score += 3
        elif return_5d < 0:
            score -= 3

        if return_20d > 0:
            score += 4
        elif return_20d < 0:
            score -= 4

        # ------------------------------------------------------------
        # Structure contribution
        # ------------------------------------------------------------

        if bullish_breakout:
            score += 10
        elif bearish_breakdown:
            score -= 10

        if bullish_pullback:
            score += 7
        elif bearish_pullback:
            score -= 7

        # ------------------------------------------------------------
        # Long-term trend contribution
        # ------------------------------------------------------------

        if current_sma_200 is not None:

            if current_price > current_sma_200:
                score += 5
            else:
                score -= 5

        # ------------------------------------------------------------
        # Clamp score
        # ------------------------------------------------------------

        score = max(
            0,
            min(100, score),
        )

        # ============================================================
        # SIGNAL STRENGTH
        # ============================================================

        if score >= 80:
            signal_strength = "VERY_STRONG_BULLISH"
        elif score >= 70:
            signal_strength = "BULLISH"
        elif score >= 60:
            signal_strength = "MILDLY_BULLISH"
        elif score >= 40:
            signal_strength = "NEUTRAL"
        elif score >= 30:
            signal_strength = "MILDLY_BEARISH"
        elif score >= 20:
            signal_strength = "BEARISH"
        else:
            signal_strength = "VERY_STRONG_BEARISH"

        # ============================================================
        # RETURN MARKET INTELLIGENCE
        # ============================================================

        return {
            "symbol": symbol,

            "available": True,

            "price": {
                "current": current_price,
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
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
                "sma_200": (
                    round(
                        current_sma_200,
                        4,
                    )
                    if current_sma_200 is not None
                    else None
                ),
                "ema_12": round(
                    current_ema_12,
                    4,
                ),
                "ema_26": round(
                    current_ema_26,
                    4,
                ),
                "sma_20_slope": round(
                    sma_20_slope * 100,
                    4,
                ),
                "sma_50_slope": round(
                    sma_50_slope * 100,
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

                "macd_histogram_change": round(
                    histogram_change,
                    6,
                ),

                "macd_signal_direction": (
                    macd_signal
                ),

                "macd_momentum": (
                    macd_momentum
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

            "volatility": {
                "atr_14": round(
                    current_atr,
                    4,
                ),
                "atr_percent": round(
                    atr_percent * 100,
                    2,
                ),
                "annualized_20d": round(
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
                "distance_from_high": round(
                    distance_from_high * 100,
                    2,
                ),
                "distance_from_low": round(
                    distance_from_low * 100,
                    2,
                ),
            },

            "structure": {
                "signal": structure_signal,
                "bullish_breakout": (
                    bullish_breakout
                ),
                "bearish_breakdown": (
                    bearish_breakdown
                ),
                "pullback": pullback_signal,
                "previous_20d_high": (
                    previous_20d_high
                ),
                "previous_20d_low": (
                    previous_20d_low
                ),
            },

            "trend": trend,

            "quantitative_signal": {
                "score": score,
                "strength": signal_strength,
            },

            "data_points": len(data),

            "data_feed": "IEX",
        }


market_agent = MarketAgent()