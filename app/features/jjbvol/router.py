from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.features.jjbvol.models import Jjbvol
from app.features.jjbvol.schemas import JjbvolItem, JjbvolListResponse

router = APIRouter(prefix="/api/jjbvol", tags=["jjbvol"])


@router.get("", response_model=list[JjbvolItem])
def get_jjbvol_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(Jjbvol).filter(Jjbvol.cdate == date).all()


@router.get("/list", response_model=JjbvolListResponse)
def get_jjbvol_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    total = db.query(Jjbvol).count()
    rows = (
        db.query(Jjbvol)
        .order_by(Jjbvol.cdate.desc(), Jjbvol.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return JjbvolListResponse(total=total, page=page, size=size, items=rows)
