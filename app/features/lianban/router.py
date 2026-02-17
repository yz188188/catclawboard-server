from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_subscribed_user
from app.features.lianban.models import Lianban
from app.features.lianban.schemas import LianbanItem, LianbanListResponse
from app.features.shared.filters import get_filters_for_display, apply_strategy_filters

router = APIRouter(prefix="/api/lianban", tags=["lianban"])


@router.get("", response_model=list[LianbanItem])
def get_lianban_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "lianban", strategy_id)
    query = db.query(Lianban).filter(Lianban.cdate == date)
    query = apply_strategy_filters(query, Lianban, filters, strategy_name="lianban")
    rows = query.order_by(Lianban.scores.desc()).all()
    return rows


@router.get("/list", response_model=LianbanListResponse)
def get_lianban_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "lianban", strategy_id)
    query = db.query(Lianban)
    query = apply_strategy_filters(query, Lianban, filters, strategy_name="lianban")
    total = query.count()
    rows = (
        query
        .order_by(Lianban.cdate.desc(), Lianban.scores.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return LianbanListResponse(total=total, page=page, size=size, items=rows)
