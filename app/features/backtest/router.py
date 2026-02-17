from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_subscribed_user
from app.backtest.models import BacktestRun, BacktestTrade, BacktestEquity, BacktestStrategy
from app.backtest.strategy import generate_trades, STRATEGIES
from app.backtest.engine import compute_stats, build_equity_curve, save_backtest
from app.features.shared.filters import STRATEGY_ALLOWED_FILTERS
from app.features.backtest.schemas import (
    BacktestRunItem,
    BacktestRunListResponse,
    BacktestTradeItem,
    BacktestEquityItem,
    StrategyCreate,
    StrategyUpdate,
    StrategyItem,
    BacktestRunRequest,
    BacktestRunResponse,
    CompareRequest,
    CompareResponse,
    FormulaResult,
)
from app.collectors.score_compare import recalculate

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


# ==================== 回测记录 ====================

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


# ==================== 策略配置 CRUD ====================

@router.get("/strategies", response_model=list[StrategyItem])
def list_strategies(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    rows = db.query(BacktestStrategy).order_by(BacktestStrategy.updated_at.desc()).all()
    return rows


@router.get("/strategies/by-type/{strategy_name}", response_model=list[StrategyItem])
def list_strategies_by_type(
    strategy_name: str,
    db: Session = Depends(get_db),
    _=Depends(get_subscribed_user),
):
    if strategy_name not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知策略: {strategy_name}")
    rows = (
        db.query(BacktestStrategy)
        .filter(BacktestStrategy.strategy_name == strategy_name)
        .order_by(BacktestStrategy.updated_at.desc())
        .all()
    )
    return rows


@router.post("/strategies", response_model=StrategyItem)
def create_strategy(
    body: StrategyCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if body.strategy_name not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知策略: {body.strategy_name}")

    allowed = STRATEGY_ALLOWED_FILTERS.get(body.strategy_name, set())
    invalid_keys = set(body.filters.keys()) - allowed
    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"过滤器 {invalid_keys} 不适用于策略 {body.strategy_name}",
        )

    existing = db.query(BacktestStrategy).filter(BacktestStrategy.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"策略名称已存在: {body.name}")

    filters_dict = {k: v.model_dump() for k, v in body.filters.items()}
    strategy = BacktestStrategy(
        name=body.name,
        strategy_name=body.strategy_name,
        filters=filters_dict,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.put("/strategies/{strategy_id}", response_model=StrategyItem)
def update_strategy(
    strategy_id: int,
    body: StrategyUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    strategy = db.query(BacktestStrategy).filter(BacktestStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    if body.name is not None:
        dup = db.query(BacktestStrategy).filter(
            BacktestStrategy.name == body.name,
            BacktestStrategy.id != strategy_id,
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"策略名称已存在: {body.name}")
        strategy.name = body.name

    if body.filters is not None:
        allowed = STRATEGY_ALLOWED_FILTERS.get(strategy.strategy_name, set())
        invalid_keys = set(body.filters.keys()) - allowed
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"过滤器 {invalid_keys} 不适用于策略 {strategy.strategy_name}",
            )
        strategy.filters = {k: v.model_dump() for k, v in body.filters.items()}

    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete("/strategies/{strategy_id}")
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    strategy = db.query(BacktestStrategy).filter(BacktestStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    db.delete(strategy)
    db.commit()
    return {"detail": "已删除"}


# ==================== 运行回测 ====================

@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(
    body: BacktestRunRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if body.strategy_name not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知策略: {body.strategy_name}")

    if not body.start_date or not body.end_date:
        raise HTTPException(status_code=400, detail="请提供起止日期")

    # 将 FilterConfig 转为 dict
    filters_dict = {k: v.model_dump() for k, v in body.filters.items()}

    # 执行回测
    trades = generate_trades(
        db=db,
        strategy_name=body.strategy_name,
        start_date=body.start_date,
        end_date=body.end_date,
        filters=filters_dict,
    )

    stats = compute_stats(trades)
    equity = build_equity_curve(trades)

    trades_data = [
        {
            "stockid": t.stockid,
            "stockname": t.stockname,
            "entry_date": t.entry_date,
            "return_pct": t.return_pct,
            "signal_data": t.signal_data,
        }
        for t in trades
    ]

    run_id = None
    if body.save and trades:
        run = save_backtest(
            db=db,
            strategy_name=body.strategy_name,
            start_date=body.start_date,
            end_date=body.end_date,
            params=filters_dict,
            trades=trades,
        )
        run_id = run.id

    return BacktestRunResponse(
        run_id=run_id,
        stats=stats,
        equity=equity,
        trades=trades_data,
    )


# ==================== 公式对比 ====================

@router.post("/compare", response_model=CompareResponse)
def compare_formulas(
    body: CompareRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if body.strategy_name not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知策略: {body.strategy_name}")

    Model = STRATEGIES[body.strategy_name]["model"]

    # 查询日期范围内所有有收盘涨幅的记录
    query = (
        db.query(Model)
        .filter(Model.cdate >= body.start_date, Model.cdate <= body.end_date)
        .filter(Model.lastzf.isnot(None))
    )
    records = query.all()

    # 应用非score的过滤器
    filters_dict = {k: v.model_dump() for k, v in body.filters.items()}
    non_score_filters = {k: v for k, v in filters_dict.items() if k != "min_score"}
    from app.backtest.strategy import apply_filters as af, Trade
    records = [r for r in records if af(r, non_score_filters)]

    # 对每条记录重算新旧分数，分别按门槛过滤
    old_trades = []
    new_trades = []
    score_map = {}  # (stockid, cdate) -> (old_score, new_score, rec_data)
    coeffs = body.coeffs.model_dump()

    for rec in records:
        old_score, new_score, mins = recalculate(rec, coeffs=coeffs)
        bzf = float(rec.bzf) if rec.bzf is not None else 0
        return_pct = round(float(rec.lastzf) - bzf, 4)

        key = (rec.stockid, rec.cdate)
        score_map[key] = {
            "old_score": old_score,
            "new_score": new_score,
            "stockid": rec.stockid,
            "stockname": rec.stockname or "",
            "entry_date": rec.cdate,
            "return_pct": return_pct,
            "rates": float(rec.rates) if rec.rates is not None else None,
            "times": rec.times or "",
            "mins": mins,
            "lastzf": float(rec.lastzf),
        }

        signal_data = {
            "scores": float(rec.scores) if rec.scores is not None else None,
            "old_score": old_score,
            "new_score": new_score,
            "bzf": bzf,
            "lastzf": float(rec.lastzf),
            "rates": float(rec.rates) if rec.rates is not None else None,
            "cje": float(rec.cje) if rec.cje is not None else None,
            "times": rec.times or "",
            "mins": mins,
        }

        trade = Trade(
            stockid=rec.stockid,
            stockname=rec.stockname or "",
            entry_date=rec.cdate,
            return_pct=return_pct,
            signal_data=signal_data,
        )

        if old_score >= body.old_threshold:
            old_trades.append(trade)
        if new_score >= body.new_threshold:
            new_trades.append(trade)

    # 计算统计和权益曲线
    old_stats = compute_stats(old_trades)
    new_stats = compute_stats(new_trades)
    old_equity = build_equity_curve(old_trades)
    new_equity = build_equity_curve(new_trades)

    # 构建交易数据
    def trades_to_dicts(trades):
        return [
            {
                "stockid": t.stockid,
                "stockname": t.stockname,
                "entry_date": t.entry_date,
                "return_pct": t.return_pct,
                "signal_data": t.signal_data,
            }
            for t in trades
        ]

    # 差异分析
    old_keys = {(t.stockid, t.entry_date) for t in old_trades}
    new_keys = {(t.stockid, t.entry_date) for t in new_trades}

    old_only = [score_map[k] for k in (old_keys - new_keys) if k in score_map]
    new_only = [score_map[k] for k in (new_keys - old_keys) if k in score_map]
    both_keys = old_keys & new_keys

    old_only.sort(key=lambda x: x["old_score"], reverse=True)
    new_only.sort(key=lambda x: x["new_score"], reverse=True)

    return CompareResponse(
        old_formula=FormulaResult(
            label="旧公式(加法)",
            threshold=body.old_threshold,
            stats=old_stats,
            equity=old_equity,
            trades=trades_to_dicts(old_trades),
        ),
        new_formula=FormulaResult(
            label="新公式(流速乘数)",
            threshold=body.new_threshold,
            stats=new_stats,
            equity=new_equity,
            trades=trades_to_dicts(new_trades),
        ),
        diff={
            "old_only": old_only[:50],
            "new_only": new_only[:50],
            "both_count": len(both_keys),
        },
    )
