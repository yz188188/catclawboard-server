from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.features.jjztdt.models import Jjztdt
from app.features.jjztdt.schemas import JjztdtItem, JjztdtListResponse

router = APIRouter(prefix="/api/jjztdt", tags=["jjztdt"])


@router.get("", response_model=JjztdtItem | None)
def get_jjztdt_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(Jjztdt).filter(Jjztdt.cdate == date).first()


@router.get("/list", response_model=JjztdtListResponse)
def get_jjztdt_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    total = db.query(Jjztdt).count()
    rows = (
        db.query(Jjztdt)
        .order_by(Jjztdt.cdate.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return JjztdtListResponse(total=total, page=page, size=size, items=rows)
