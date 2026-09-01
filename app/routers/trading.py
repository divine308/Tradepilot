

from fastapi import APIRouter, Depends, HTTPException

from app.agents.supervisor import supervisor_agent
from app.core.security import get_current_user
from app.schemas.trading import (
    AnalyzeRequest,
    TradeRequest,
)
from app.services.alpaca_service import alpaca_service
from app.agents.autonomous_agent import autonomous_agent

router = APIRouter(
    prefix="/api/trading",
    tags=["Trading"],
)


# ==========================================================
# ACCOUNT
# ==========================================================

@router.get("/account")
async def account(
    current_user=Depends(get_current_user),
):

    try:

        account = alpaca_service.get_account()

        return {
            "id": str(account.id),
            "status": str(account.status),
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(
                account.buying_power
            ),
            "currency": str(
                account.currency
            ),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve account: {error}",
        )


# ==========================================================
# POSITIONS
# ==========================================================

@router.get("/positions")
async def positions(
    current_user=Depends(get_current_user),
):

    try:

        positions = (
            alpaca_service.get_positions()
        )

        return [
            {
                "symbol": position.symbol,
                "qty": float(position.qty),
                "market_value": float(
                    position.market_value
                ),
                "cost_basis": float(
                    position.cost_basis
                ),
                "unrealized_pl": float(
                    position.unrealized_pl
                ),
                "unrealized_plpc": float(
                    position.unrealized_plpc
                ),
                "avg_entry_price": float(
                    position.avg_entry_price
                ),
                "current_price": float(
                    position.current_price
                ),
            }
            for position in positions
        ]

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve positions: {error}",
        )


# ============================================================
# AUTONOMOUS AGENT
# ============================================================

@router.get("/agent/status")
async def agent_status(
    current_user=Depends(get_current_user),
):

    try:

        return autonomous_agent.status()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve agent status: {error}",
        )


@router.post("/agent/start")
async def start_agent(
    current_user=Depends(get_current_user),
):

    try:

        return await autonomous_agent.start()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to start autonomous agent: {error}",
        )


@router.post("/agent/stop")
async def stop_agent(
    current_user=Depends(get_current_user),
):

    try:

        return await autonomous_agent.stop()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to stop autonomous agent: {error}",
        )


@router.post("/agent/scan")
async def scan_agent(
    current_user=Depends(get_current_user),
):

    try:

        return await autonomous_agent.scan()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Autonomous scan failed: {error}",
        )


@router.get("/agent/activity")
async def agent_activity(
    limit: int = 50,
    current_user=Depends(get_current_user),
):

    try:

        return {
            "activity": autonomous_agent.get_activity(
                limit
            )
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve agent activity: {error}",
        )

# ==========================================================
# ORDERS
# ==========================================================

@router.get("/orders")
async def orders(
    current_user=Depends(get_current_user),
):

    try:

        orders = alpaca_service.get_orders()

        return [
            {
                "id": str(order.id),
                "symbol": order.symbol,
                "side": str(order.side),
                "type": str(order.type),
                "qty": (
                    float(order.qty)
                    if order.qty is not None
                    else None
                ),
                "filled_qty": (
                    float(order.filled_qty)
                    if order.filled_qty is not None
                    else 0,
                ),
                "status": str(order.status),
                "submitted_at": (
                    order.submitted_at.isoformat()
                    if order.submitted_at
                    else None
                ),
                "filled_at": (
                    order.filled_at.isoformat()
                    if order.filled_at
                    else None
                ),
            }
            for order in orders
        ]

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve orders: {error}",
        )


# ==========================================================
# AI MARKET ANALYSIS
# ==========================================================

@router.post("/analyze")
async def analyze(
    data: AnalyzeRequest,
    current_user=Depends(get_current_user),
):

    symbol = data.symbol.upper().strip()

    if not symbol:

        raise HTTPException(
            status_code=400,
            detail="Symbol is required.",
        )

    try:

        return supervisor_agent.analyze(
            symbol
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {error}",
        )


# ==========================================================
# EXECUTE TRADE
# ==========================================================

@router.post("/execute")
async def execute(
    data: TradeRequest,
    current_user=Depends(get_current_user),
):

    symbol = data.symbol.upper().strip()
    side = data.side.lower().strip()

    if not symbol:

        raise HTTPException(
            status_code=400,
            detail="Symbol is required.",
        )

    if side not in {"buy", "sell"}:

        raise HTTPException(
            status_code=400,
            detail="Side must be buy or sell.",
        )

    if data.quantity <= 0:

        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero.",
        )

    try:

        result = supervisor_agent.execute(
            symbol=symbol,
            side=side,
            quantity=data.quantity,
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Trade execution failed: {error}",
        )


# ==========================================================
# CANCEL ALL ORDERS
# ==========================================================

@router.delete("/orders")
async def cancel_orders(
    current_user=Depends(get_current_user),
):

    try:

        result = (
            alpaca_service.cancel_all_orders()
        )

        return {
            "success": True,
            "message": "All open orders cancelled.",
            "count": len(result),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Unable to cancel orders: {error}",
        )

 # ============================================================
# CLOSE ALL POSITIONS
# ============================================================

@router.post("/positions/close-all")
async def close_all_positions(
    current_user=Depends(get_current_user),
):

    try:

        result = alpaca_service.close_all_positions()

        if result["closed"]:

            return {
                "success": True,
                "message": (
                    "All open positions have been closed."
                ),
                "count": result["count"],
            }

        return {
            "success": False,
            "message": (
                "Close orders were submitted, "
                "but some positions are still open."
            ),
            "count": result["count"],
            "remaining_positions": result["remaining"],
        }

    except Exception as error:

        print(
            "===================================================="
        )
        print("CLOSE ALL POSITIONS ERROR")
        print(
            "===================================================="
        )
        print(repr(error))
        print(
            "===================================================="
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to close all positions: {error}"
            ),
        )