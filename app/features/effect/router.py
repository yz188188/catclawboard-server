from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.features.effect.models import MoneyEffect
from app.features.effect.schemas import EffectItem, EffectListResponse

router = APIRouter(prefix="/api/effect", tags=["effect"])


@router.get("", response_model=EffectItem | None)
def get_effect_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(MoneyEffect).filter(MoneyEffect.cdate == date).first()


@router.get("/list", response_model=EffectListResponse)
def get_effect_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    total = db.query(MoneyEffect).count()
    rows = (
        db.query(MoneyEffect)
        .order_by(MoneyEffect.cdate.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return EffectListResponse(total=total, page=page, size=size, items=rows)
