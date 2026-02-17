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

# 过滤器注册表：数据驱动的过滤逻辑
FILTER_REGISTRY = {
    "min_score":    {"attr": "scores",   "op": ">="},
    "min_rate":     {"attr": "rates",    "op": ">="},
    "min_bzf":      {"attr": "bzf",      "op": ">="},
    "max_bzf":      {"attr": "bzf",      "op": "<="},
    "min_zhenfu":   {"attr": "zhenfu",   "op": ">="},
    "min_chg_1min": {"attr": "chg_1min", "op": ">="},
    "time_start":   {"attr": "times",    "op": ">="},
    "time_end":     {"attr": "times",    "op": "<="},
    "min_lbs":      {"attr": "lbs",      "op": ">="},
}


@dataclass
class Trade:
    stockid: str
    stockname: str
    entry_date: str
    return_pct: float
    signal_data: dict


def params_to_filters(params: dict) -> dict:
    """旧 flat params 转新 filters 格式（CLI 兼容）

    Args:
        params: {"min_score": 100, "min_rate": 10, ...}

    Returns:
        {"min_score": {"enabled": True, "value": 100}, ...}
    """
    filters = {}
    for key, value in params.items():
        if key in FILTER_REGISTRY:
            filters[key] = {"enabled": True, "value": value}
    return filters


def apply_filters(rec, filters: dict) -> bool:
    """根据 filters 配置过滤单条记录

    Args:
        rec: 数据库记录（Model 实例）
        filters: {"min_score": {"enabled": True, "value": 100}, ...}

    Returns:
        True 通过过滤，False 被过滤掉
    """
    for key, config in filters.items():
        if not config.get("enabled", True):
            continue

        reg = FILTER_REGISTRY.get(key)
        if not reg:
            continue

        attr_name = reg["attr"]
        op = reg["op"]
        threshold = config["value"]

        # 获取记录属性值
        if not hasattr(rec, attr_name):
            continue

        raw_value = getattr(rec, attr_name)

        # NULL 值：times 字段空字符串视为不通过，数值字段跳过过滤
        if attr_name == "times":
            val = raw_value or ""
            threshold_str = str(threshold)
            if op == ">=" and val < threshold_str:
                return False
            if op == "<=" and val > threshold_str:
                return False
        else:
            if raw_value is None:
                continue
            val = float(raw_value)
            threshold_f = float(threshold)
            if op == ">=" and val < threshold_f:
                return False
            if op == "<=" and val > threshold_f:
                return False

    return True


def generate_trades(
    db: Session,
    strategy_name: str,
    start_date: str,
    end_date: str,
    params: dict | None = None,
    filters: dict | None = None,
) -> list[Trade]:
    """从对应表读取信号，按参数过滤，计算每笔收益

    Args:
        db: SQLAlchemy Session
        strategy_name: 策略名称 (mighty/lianban/jjmighty)
        start_date: 起始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        params: 旧格式回测参数（CLI 兼容），None 则使用默认值
        filters: 新格式过滤配置，优先级高于 params

    Returns:
        交易列表
    """
    if strategy_name not in STRATEGIES:
        raise ValueError(f"未知策略: {strategy_name}，可选: {list(STRATEGIES.keys())}")

    Model = STRATEGIES[strategy_name]["model"]

    # 确定过滤条件：filters 优先，否则从 params 转换
    if filters is not None:
        active_filters = filters
    else:
        p = {**DEFAULT_PARAMS, **(params or {})}
        active_filters = params_to_filters(p)

    # 查询日期范围内的所有记录
    query = (
        db.query(Model)
        .filter(Model.cdate >= start_date, Model.cdate <= end_date)
        .filter(Model.lastzf.isnot(None))  # 必须有收盘涨幅
    )
    records = query.all()

    trades = []
    for rec in records:
        if not apply_filters(rec, active_filters):
            continue

        bzf = float(rec.bzf) if rec.bzf is not None else 0
        # 收益 = 收盘涨幅 - 入选时涨幅
        return_pct = float(rec.lastzf) - bzf

        signal_data = {
            "scores": float(rec.scores) if rec.scores is not None else None,
            "bzf": bzf,
            "lastzf": float(rec.lastzf),
            "rates": float(rec.rates) if rec.rates is not None else None,
            "ozf": float(rec.ozf) if rec.ozf is not None else None,
            "cje": float(rec.cje) if rec.cje is not None else None,
            "zhenfu": float(rec.zhenfu) if rec.zhenfu is not None else None,
            "chg_1min": float(rec.chg_1min) if rec.chg_1min is not None else None,
            "zs_times": float(rec.zs_times) if rec.zs_times is not None else None,
            "times": rec.times or "",
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
