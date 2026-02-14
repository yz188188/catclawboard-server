from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.features.ztdb.models import Ztdb
from app.features.ztdb.schemas import ZtdbItem, ZtdbListResponse

router = APIRouter(prefix="/api/ztdb", tags=["ztdb"])


@router.get("", response_model=list[ZtdbItem])
def get_ztdb_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = db.query(Ztdb).filter(Ztdb.cdate == date).all()
    return rows


@router.get("/list", response_model=ZtdbListResponse)
def get_ztdb_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    total = db.query(Ztdb).count()
    rows = (
        db.query(Ztdb)
        .order_by(Ztdb.cdate.desc(), Ztdb.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return ZtdbListResponse(total=total, page=page, size=size, items=rows)
