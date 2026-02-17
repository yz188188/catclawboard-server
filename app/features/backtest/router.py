from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.backtest.models import BacktestRun, BacktestTrade, BacktestEquity
from app.features.backtest.schemas import (
    BacktestRunItem,
    BacktestRunListResponse,
    BacktestTradeItem,
    BacktestEquityItem,
)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/runs", response_model=BacktestRunListResponse)
def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    strategy: str | None = Query(None, description="筛选策略名"),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    query = db.query(BacktestRun)
    if strategy:
        query = query.filter(BacktestRun.strategy_name == strategy)
    total = query.count()
    rows = (
        query.order_by(BacktestRun.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return BacktestRunListResponse(total=total, page=page, size=size, items=rows)


@router.get("/runs/{run_id}", response_model=BacktestRunItem)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    return run


@router.get("/runs/{run_id}/trades", response_model=list[BacktestTradeItem])
def get_trades(
    run_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    rows = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.entry_date.desc())
        .all()
    )
    return rows


@router.get("/runs/{run_id}/equity", response_model=list[BacktestEquityItem])
def get_equity(
    run_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    rows = (
        db.query(BacktestEquity)
        .filter(BacktestEquity.run_id == run_id)
        .order_by(BacktestEquity.tdate.asc())
        .all()
    )
    return rows


@router.delete("/runs/{run_id}")
def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    db.delete(run)
    db.commit()
    return {"detail": "已删除"}
