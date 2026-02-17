from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_subscribed_user
from app.features.lianban.models import Lianban
from app.features.lianban.schemas import LianbanItem, LianbanListResponse

router = APIRouter(prefix="/api/lianban", tags=["lianban"])


def _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg):
    """对查询应用过滤条件，兼容历史数据（新字段为 NULL 时跳过过滤）"""
    query = query.filter(Lianban.scores >= min_score)
    query = query.filter(Lianban.rates >= min_rate)
    query = query.filter(or_(Lianban.zhenfu.is_(None), Lianban.zhenfu >= min_zhenfu))
    query = query.filter(or_(Lianban.chg_1min.is_(None), Lianban.chg_1min >= min_chg))
    return query


@router.get("", response_model=list[LianbanItem])
def get_lianban_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    min_score: float = Query(100, description="最低评分"),
    min_rate: float = Query(10, description="最低换手率%"),
    min_zhenfu: float = Query(5, description="最低振幅%"),
    min_chg: float = Query(1.5, description="最低1分钟涨速%"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    query = db.query(Lianban).filter(Lianban.cdate == date)
    query = _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg)
    rows = query.order_by(Lianban.scores.desc()).all()
    return rows


@router.get("/list", response_model=LianbanListResponse)
def get_lianban_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    min_score: float = Query(100, description="最低评分"),
    min_rate: float = Query(10, description="最低换手率%"),
    min_zhenfu: float = Query(5, description="最低振幅%"),
    min_chg: float = Query(1.5, description="最低1分钟涨速%"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    query = db.query(Lianban)
    query = _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg)
    total = query.count()
    rows = (
        query
        .order_by(Lianban.cdate.desc(), Lianban.scores.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return LianbanListResponse(total=total, page=page, size=size, items=rows)
