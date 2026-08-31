# from datetime import datetime, timezone

# from fastapi import APIRouter, Depends

# from app.core.security import get_current_user
# from app.services.alpaca_service import alpaca_service


# router = APIRouter(
#     prefix="/api/dashboard",
#     tags=["Dashboard"],
# )


# @router.get("/overview")
# async def overview(
#     current_user=Depends(get_current_user),
# ):
#     account = alpaca_service.get_account()
#     positions = alpaca_service.get_positions()

#     positions = positions or []

#     total_market_value = sum(
#         float(getattr(position, "market_value", 0) or 0)
#         for position in positions
#     )

#     total_cost_basis = sum(
#         float(getattr(position, "cost_basis", 0) or 0)
#         for position in positions
#     )

#     total_unrealized_pl = sum(
#         float(getattr(position, "unrealized_pl", 0) or 0)
#         for position in positions
#     )

#     portfolio_return = (
#         (total_unrealized_pl / total_cost_basis) * 100
#         if total_cost_basis > 0
#         else 0
#     )

#     return {
#         "equity": float(account.equity),
#         "cash": float(account.cash),
#         "buying_power": float(account.buying_power),

#         "positions": len(positions),

#         "market_value": total_market_value,
#         "cost_basis": total_cost_basis,
#         "unrealized_pl": total_unrealized_pl,
#         "portfolio_return": portfolio_return,

#         "paper_trading": True,

#         "account_status": getattr(
#             account,
#             "status",
#             None,
#         ),

#         "currency": getattr(
#             account,
#             "currency",
#             "USD",
#         ),

#         "timestamp": datetime.now(
#             timezone.utc
#         ).isoformat(),
#     }


from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.alpaca_service import alpaca_service


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/overview")
async def overview(
    current_user=Depends(get_current_user),
):
    account = alpaca_service.get_account()
    positions = alpaca_service.get_positions() or []

    total_market_value = sum(
        float(getattr(position, "market_value", 0) or 0)
        for position in positions
    )

    total_cost_basis = sum(
        float(getattr(position, "cost_basis", 0) or 0)
        for position in positions
    )

    total_unrealized_pl = sum(
        float(getattr(position, "unrealized_pl", 0) or 0)
        for position in positions
    )

    portfolio_return = (
        (total_unrealized_pl / total_cost_basis) * 100
        if total_cost_basis > 0
        else 0
    )

    serialized_positions = []

    for position in positions:
        serialized_positions.append(
            {
                "symbol": str(
                    getattr(position, "symbol", "")
                ),

                "quantity": float(
                    getattr(position, "qty", 0) or 0
                ),

                "avg_entry_price": float(
                    getattr(
                        position,
                        "avg_entry_price",
                        0,
                    )
                    or 0
                ),

                "current_price": float(
                    getattr(
                        position,
                        "current_price",
                        0,
                    )
                    or 0
                ),

                "market_value": float(
                    getattr(
                        position,
                        "market_value",
                        0,
                    )
                    or 0
                ),

                "cost_basis": float(
                    getattr(
                        position,
                        "cost_basis",
                        0,
                    )
                    or 0
                ),

                "unrealized_pl": float(
                    getattr(
                        position,
                        "unrealized_pl",
                        0,
                    )
                    or 0
                ),

                "unrealized_plpc": float(
                    getattr(
                        position,
                        "unrealized_plpc",
                        0,
                    )
                    or 0
                ),

                "side": str(
                    getattr(
                        position,
                        "side",
                        "",
                    )
                ),
            }
        )

    return {
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),

        "positions": len(serialized_positions),
        "position_data": serialized_positions,

        "market_value": total_market_value,
        "cost_basis": total_cost_basis,
        "unrealized_pl": total_unrealized_pl,
        "portfolio_return": portfolio_return,

        "paper_trading": True,

        "account_status": getattr(
            account,
            "status",
            None,
        ),

        "currency": getattr(
            account,
            "currency",
            "USD",
        ),

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }