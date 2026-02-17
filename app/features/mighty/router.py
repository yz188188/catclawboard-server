from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_subscribed_user
from app.features.mighty.models import Mighty
from app.features.mighty.schemas import MightyItem, MightyListResponse
from app.features.shared.filters import get_filters_for_display, apply_strategy_filters

router = APIRouter(prefix="/api/mighty", tags=["mighty"])


@router.get("", response_model=list[MightyItem])
def get_mighty_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "mighty", strategy_id)
    query = db.query(Mighty).filter(Mighty.cdate == date)
    query = apply_strategy_filters(query, Mighty, filters, strategy_name="mighty")
    rows = query.order_by(Mighty.scores.desc()).all()
    return rows


@router.get("/list", response_model=MightyListResponse)
def get_mighty_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "mighty", strategy_id)
    query = db.query(Mighty)
    query = apply_strategy_filters(query, Mighty, filters, strategy_name="mighty")
    total = query.count()
    rows = (
        query
        .order_by(Mighty.cdate.desc(), Mighty.scores.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return MightyListResponse(total=total, page=page, size=size, items=rows)
