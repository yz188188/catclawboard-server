from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_subscribed_user
from app.features.jjmighty.models import Jjmighty
from app.features.jjmighty.schemas import JjmightyItem, JjmightyListResponse

router = APIRouter(prefix="/api/jjmighty", tags=["jjmighty"])


def _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg, min_ozf):
    """对查询应用过滤条件，兼容历史数据（新字段为 NULL 时跳过过滤）"""
    query = query.filter(Jjmighty.scores >= min_score)
    query = query.filter(Jjmighty.rates >= min_rate)
    query = query.filter(or_(Jjmighty.zhenfu.is_(None), Jjmighty.zhenfu >= min_zhenfu))
    query = query.filter(or_(Jjmighty.chg_1min.is_(None), Jjmighty.chg_1min >= min_chg))
    query = query.filter(or_(Jjmighty.ozf.is_(None), Jjmighty.ozf >= min_ozf))
    return query


@router.get("", response_model=list[JjmightyItem])
def get_jjmighty_by_date(
    date: str = Query(..., description="日期 YYYYMMDD"),
    min_score: float = Query(100, description="最低评分"),
    min_rate: float = Query(10, description="最低换手率%"),
    min_zhenfu: float = Query(5, description="最低振幅%"),
    min_chg: float = Query(1.5, description="最低1分钟涨速%"),
    min_ozf: float = Query(3, description="最低开盘涨幅%"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    query = db.query(Jjmighty).filter(Jjmighty.cdate == date)
    query = _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg, min_ozf)
    rows = query.order_by(Jjmighty.scores.desc()).all()
    return rows


@router.get("/list", response_model=JjmightyListResponse)
def get_jjmighty_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    min_score: float = Query(100, description="最低评分"),
    min_rate: float = Query(10, description="最低换手率%"),
    min_zhenfu: float = Query(5, description="最低振幅%"),
    min_chg: float = Query(1.5, description="最低1分钟涨速%"),
    min_ozf: float = Query(3, description="最低开盘涨幅%"),
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    query = db.query(Jjmighty)
    query = _apply_filters(query, min_score, min_rate, min_zhenfu, min_chg, min_ozf)
    total = query.count()
    rows = (
        query
        .order_by(Jjmighty.cdate.desc(), Jjmighty.scores.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return JjmightyListResponse(total=total, page=page, size=size, items=rows)
