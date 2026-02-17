from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_subscribed_user
from app.features.jjmighty.models import Jjmighty
from app.features.jjmighty.schemas import JjmightyItem, JjmightyListResponse
from app.features.shared.filters import get_filters_for_display, apply_strategy_filters

router = APIRouter(prefix="/api/jjmighty", tags=["jjmighty"])


@router.get("", response_model=list[JjmightyItem])
def get_jjmighty_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "jjmighty", strategy_id)
    query = db.query(Jjmighty).filter(Jjmighty.cdate == date)
    query = apply_strategy_filters(query, Jjmighty, filters, strategy_name="jjmighty")
    rows = query.order_by(Jjmighty.scores.desc()).all()
    return rows


@router.get("/list", response_model=JjmightyListResponse)
def get_jjmighty_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    strategy_id: int | None = Query(None, description="策略配置ID"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    filters = get_filters_for_display(db, "jjmighty", strategy_id)
    query = db.query(Jjmighty)
    query = apply_strategy_filters(query, Jjmighty, filters, strategy_name="jjmighty")
    total = query.count()
    rows = (
        query
        .order_by(Jjmighty.cdate.desc(), Jjmighty.scores.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return JjmightyListResponse(total=total, page=page, size=size, items=rows)
