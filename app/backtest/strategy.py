# coding:utf-8
"""通用回测策略 — 从数据表读取信号，按参数过滤，计算每笔收益

支持三个策略，共享相同的过滤逻辑，只读取不同的数据表:
  mighty:   db_mighty   (强势反包，股票池=昨日大成交额>8亿非涨停)
  lianban:  db_lianban  (连板反包，股票池=昨日连板>=2)
  jjmighty: db_jjmighty (竞价强势，股票池=昨日全部涨停股)
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.features.mighty.models import Mighty
from app.features.lianban.models import Lianban
from app.features.jjmighty.models import Jjmighty

STRATEGIES = {
    "mighty": {"model": Mighty, "label": "强势反包"},
    "lianban": {"model": Lianban, "label": "连板反包"},
    "jjmighty": {"model": Jjmighty, "label": "竞价强势"},
}

DEFAULT_PARAMS = {
    "min_score": 100,
    "min_rate": 10,
    "min_bzf": 0,
    "max_bzf": 100,
    "min_zhenfu": 5,
    "min_chg_1min": 1.5,
    "time_start": "0930",
    "time_end": "0946",
}

GRID_RANGES = {
    "min_score": [80, 100, 120, 150, 200],
    "min_rate": [5, 10, 15, 20],
    "min_bzf": [0, 2, 3, 5],
    "max_bzf": [6, 8, 10, 100],
    "min_zhenfu": [3, 5, 7],
    "min_chg_1min": [1.0, 1.5, 2.0],
    "time_start": ["0930"],
    "time_end": ["0935", "0940", "0946"],
}


@dataclass
class Trade:
    stockid: str
    stockname: str
    entry_date: str
    return_pct: float
    signal_data: dict


def generate_trades(
    db: Session,
    strategy_name: str,
    start_date: str,
    end_date: str,
    params: dict | None = None,
) -> list[Trade]:
    """从对应表读取信号，按参数过滤，计算每笔收益

    Args:
        db: SQLAlchemy Session
        strategy_name: 策略名称 (mighty/lianban/jjmighty)
        start_date: 起始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        params: 回测参数，None 则使用默认值

    Returns:
        交易列表
    """
    if strategy_name not in STRATEGIES:
        raise ValueError(f"未知策略: {strategy_name}，可选: {list(STRATEGIES.keys())}")

    Model = STRATEGIES[strategy_name]["model"]
    p = {**DEFAULT_PARAMS, **(params or {})}

    min_score = float(p["min_score"])
    min_rate = float(p["min_rate"])
    min_bzf = float(p["min_bzf"])
    max_bzf = float(p["max_bzf"])
    min_zhenfu = float(p["min_zhenfu"])
    min_chg_1min = float(p["min_chg_1min"])
    time_start = str(p["time_start"])
    time_end = str(p["time_end"])

    # 查询日期范围内的所有记录
    query = (
        db.query(Model)
        .filter(Model.cdate >= start_date, Model.cdate <= end_date)
        .filter(Model.lastzf.isnot(None))  # 必须有收盘涨幅
    )
    records = query.all()

    trades = []
    for rec in records:
        # 参数过滤
        score = float(rec.scores) if rec.scores is not None else 0
        if score < min_score:
            continue

        rate = float(rec.rates) if rec.rates is not None else 0
        if rate < min_rate:
            continue

        bzf = float(rec.bzf) if rec.bzf is not None else 0
        if bzf < min_bzf or bzf > max_bzf:
            continue

        # 振幅过滤（NULL 旧数据跳过过滤）
        if rec.zhenfu is not None and float(rec.zhenfu) < min_zhenfu:
            continue

        # 1分钟涨速过滤（NULL 旧数据跳过过滤）
        if rec.chg_1min is not None and float(rec.chg_1min) < min_chg_1min:
            continue

        times = rec.times or ""
        if times < time_start or times > time_end:
            continue

        # 收益 = 收盘涨幅 - 入选时涨幅
        return_pct = float(rec.lastzf) - bzf

        signal_data = {
            "scores": score,
            "bzf": bzf,
            "lastzf": float(rec.lastzf),
            "rates": rate,
            "ozf": float(rec.ozf) if rec.ozf is not None else None,
            "cje": float(rec.cje) if rec.cje is not None else None,
            "zhenfu": float(rec.zhenfu) if rec.zhenfu is not None else None,
            "chg_1min": float(rec.chg_1min) if rec.chg_1min is not None else None,
            "zs_times": float(rec.zs_times) if rec.zs_times is not None else None,
            "times": times,
        }
        # lbs field for lianban/jjmighty
        if hasattr(rec, "lbs") and rec.lbs is not None:
            signal_data["lbs"] = rec.lbs

        trades.append(Trade(
            stockid=rec.stockid,
            stockname=rec.stockname or "",
            entry_date=rec.cdate,
            return_pct=round(return_pct, 4),
            signal_data=signal_data,
        ))

    return trades
