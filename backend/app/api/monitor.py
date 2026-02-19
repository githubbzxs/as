from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_container, require_user
from app.schemas import MetricsResponse, OrderView, TradeView

router = APIRouter(prefix="/api", tags=["monitor"])


@router.get("/metrics", response_model=MetricsResponse, dependencies=[Depends(require_user)])
async def metrics(container=Depends(get_container)) -> MetricsResponse:
    return MetricsResponse(summary=container.monitor.summary, series=container.monitor.series())


@router.get("/orders/open", response_model=list[OrderView], dependencies=[Depends(require_user)])
async def open_orders(container=Depends(get_container)) -> list[OrderView]:
    rows = container.monitor.open_orders
    return [
        OrderView(
            order_id=o.order_id,
            side=o.side,
            price=o.price,
            size=o.size,
            status=o.status,
            created_at=o.created_at,
        )
        for o in rows
    ]


@router.get("/trades/recent", response_model=list[TradeView], dependencies=[Depends(require_user)])
async def recent_trades(container=Depends(get_container)) -> list[TradeView]:
    rows = container.monitor.recent_trades
    return [
        TradeView(
            trade_id=t.trade_id,
            side=t.side,
            price=t.price,
            size=t.size,
            fee=t.fee,
            created_at=t.created_at,
        )
        for t in rows
    ]
