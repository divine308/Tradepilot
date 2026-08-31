
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services.alpaca_service import alpaca_service


router = APIRouter(
    prefix="/api/market",
    tags=["Market Data"],
)


# ============================================================
# NORMALIZE SYMBOL
# ============================================================

def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()

    if not symbol:
        raise HTTPException(
            status_code=400,
            detail="Symbol is required.",
        )

    if not symbol.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol.",
        )

    return symbol


# ============================================================
# HISTORICAL MARKET BARS
#
# GET:
# /api/market/bars?symbol=AAPL&timeframe=1Min&limit=200
# ============================================================

@router.get("/bars")
async def get_market_bars(
    symbol: str = Query(...),
    timeframe: str = Query("1Min"),
    limit: int = Query(
        200,
        ge=10,
        le=1000,
    ),
):
    symbol = normalize_symbol(symbol)

    allowed_timeframes = {
        "1Min",
        "5Min",
        "15Min",
        "1Hour",
        "1Day",
    }

    if timeframe not in allowed_timeframes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid timeframe. "
                "Use 1Min, 5Min, 15Min, 1Hour, or 1Day."
            ),
        )

    try:
        bars = alpaca_service.get_market_bars(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

    except Exception as error:
        print(
            f"Market bars error for {symbol}:",
            repr(error),
        )

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to retrieve market data "
                f"for {symbol}: {str(error)}"
            ),
        )

    if not bars:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No market bars were returned "
                f"for {symbol}."
            ),
        )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": bars,
        "count": len(bars),
        "source": "alpaca",
    }


# ============================================================
# LATEST BAR
# ============================================================

@router.get("/{symbol}/latest")
async def get_latest_market_bar(
    symbol: str,
):
    symbol = normalize_symbol(symbol)

    try:
        bars = alpaca_service.get_market_bars(
            symbol=symbol,
            timeframe="1Min",
            limit=1,
        )

    except Exception as error:
        print(
            f"Latest bar error for {symbol}:",
            repr(error),
        )

        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to retrieve latest "
                f"market data for {symbol}: {str(error)}"
            ),
        )

    if not bars:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No latest market data "
                f"available for {symbol}."
            ),
        )

    return {
        "symbol": symbol,
        **bars[-1],
        "source": "alpaca",
    }

