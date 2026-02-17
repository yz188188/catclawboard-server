# coding:utf-8
"""回测引擎 — 统计计算 + 权益曲线 + 写DB"""
import math
from collections import defaultdict

from sqlalchemy.orm import Session

from app.backtest.models import BacktestRun, BacktestTrade, BacktestEquity
from app.backtest.strategy import Trade, STRATEGIES


def compute_stats(trades: list[Trade]) -> dict:
    """计算回测统计指标

    Args:
        trades: 交易列表

    Returns:
        统计字典: total_trades, win_trades, win_rate, avg_return,
                  total_return, max_drawdown, sharpe_ratio, profit_factor
    """
    if not trades:
        return {
            "total_trades": 0,
            "win_trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "profit_factor": 0,
        }

    returns = [t.return_pct for t in trades]
    total = len(returns)
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / total if total > 0 else 0
    avg_ret = sum(returns) / total

    # 按日期聚合计算权益曲线（同日多笔取均值）
    daily = defaultdict(list)
    for t in trades:
        daily[t.entry_date].append(t.return_pct)
    daily_returns = {}
    for d in sorted(daily.keys()):
        daily_returns[d] = sum(daily[d]) / len(daily[d])

    # 复利累计收益
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    equity_curve = {}
    for d, dr in daily_returns.items():
        equity *= (1 + dr / 100)
        equity_curve[d] = equity
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    total_return = (equity - 1) * 100  # 百分比

    # 夏普比率 = avg / std * sqrt(252)
    if len(returns) > 1:
        std = (sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
        sharpe = (avg_ret / std * math.sqrt(252)) if std > 0 else 0
    else:
        sharpe = 0

    # 盈亏比 = avg_win / avg_loss
    win_returns = [r for r in returns if r > 0]
    loss_returns = [r for r in returns if r < 0]
    avg_win = sum(win_returns) / len(win_returns) if win_returns else 0
    avg_loss = abs(sum(loss_returns) / len(loss_returns)) if loss_returns else 0
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

    return {
        "total_trades": total,
        "win_trades": wins,
        "win_rate": round(win_rate, 4),
        "avg_return": round(avg_ret, 4),
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "sharpe_ratio": round(sharpe, 4),
        "profit_factor": round(profit_factor, 4),
    }


def build_equity_curve(trades: list[Trade]) -> list[dict]:
    """按日期聚合构建权益曲线

    Returns:
        [{"tdate": "20250101", "equity": 1.012, "drawdown": 0.0}, ...]
    """
    if not trades:
        return []

    daily = defaultdict(list)
    for t in trades:
        daily[t.entry_date].append(t.return_pct)

    equity = 1.0
    peak = 1.0
    curve = []
    for d in sorted(daily.keys()):
        avg_r = sum(daily[d]) / len(daily[d])
        equity *= (1 + avg_r / 100)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        curve.append({
            "tdate": d,
            "equity": round(equity, 4),
            "drawdown": round(dd * 100, 4),
        })
    return curve


def save_backtest(
    db: Session,
    strategy_name: str,
    start_date: str,
    end_date: str,
    params: dict,
    trades: list[Trade],
) -> BacktestRun:
    """计算统计并持久化回测结果到 DB

    Args:
        db: SQLAlchemy Session
        strategy_name: 策略名
        start_date: YYYYMMDD
        end_date: YYYYMMDD
        params: 回测参数
        trades: 交易列表

    Returns:
        BacktestRun 记录
    """
    stats = compute_stats(trades)
    label = STRATEGIES.get(strategy_name, {}).get("label", strategy_name)

    run = BacktestRun(
        strategy_name=strategy_name,
        strategy_label=label,
        start_date=start_date,
        end_date=end_date,
        params=params,
        **stats,
    )
    db.add(run)
    db.flush()  # 获取 run.id

    # 写入交易明细
    for t in trades:
        trade_rec = BacktestTrade(
            run_id=run.id,
            stockid=t.stockid,
            stockname=t.stockname,
            entry_date=t.entry_date,
            return_pct=t.return_pct,
            signal_data=t.signal_data,
        )
        db.add(trade_rec)

    # 写入权益曲线
    curve = build_equity_curve(trades)
    for point in curve:
        eq = BacktestEquity(
            run_id=run.id,
            tdate=point["tdate"],
            equity=point["equity"],
            drawdown=point["drawdown"],
        )
        db.add(eq)

    db.commit()
    return run
