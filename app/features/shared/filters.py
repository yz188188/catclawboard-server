# coding:utf-8
"""共享过滤工具 — 将策略配置转为 SQLAlchemy 过滤条件"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.backtest.models import BacktestStrategy
from app.backtest.strategy import FILTER_REGISTRY

# 每种策略允许的过滤器 key（白名单）
STRATEGY_ALLOWED_FILTERS: dict[str, set[str]] = {
    "mighty": {
        "min_score", "min_rate", "min_bzf", "max_bzf",
        "min_zhenfu", "min_chg_1min", "time_start", "time_end", "min_ozf",
    },
    "lianban": {
        "min_score", "min_rate", "min_bzf", "max_bzf",
        "min_zhenfu", "min_chg_1min", "time_start", "time_end", "min_ozf", "min_lbs",
    },
    "jjmighty": {
        "min_score", "min_rate", "min_bzf", "max_bzf",
        "min_zhenfu", "min_chg_1min", "time_start", "time_end", "min_ozf", "min_lbs",
    },
}

# 每种策略的默认显示过滤（向后兼容现有硬编码值）
DEFAULT_DISPLAY_FILTERS = {
    "mighty": {
        "min_score": {"enabled": True, "value": 100},
        "min_rate": {"enabled": True, "value": 10},
        "min_zhenfu": {"enabled": True, "value": 5},
        "min_chg_1min": {"enabled": True, "value": 1.5},
    },
    "lianban": {
        "min_score": {"enabled": True, "value": 100},
        "min_rate": {"enabled": True, "value": 10},
        "min_zhenfu": {"enabled": True, "value": 5},
        "min_chg_1min": {"enabled": True, "value": 1.5},
    },
    "jjmighty": {
        "min_score": {"enabled": True, "value": 100},
        "min_rate": {"enabled": True, "value": 10},
        "min_zhenfu": {"enabled": True, "value": 5},
        "min_chg_1min": {"enabled": True, "value": 1.5},
        "min_ozf": {"enabled": True, "value": 3},
    },
}


def get_filters_for_display(
    db: Session, strategy_name: str, strategy_id: int | None
) -> dict:
    """有 strategy_id 则从 DB 加载策略过滤配置，否则返回默认值"""
    if strategy_id is not None:
        strategy = (
            db.query(BacktestStrategy)
            .filter(
                BacktestStrategy.id == strategy_id,
                BacktestStrategy.strategy_name == strategy_name,
            )
            .first()
        )
        if strategy and strategy.filters:
            return strategy.filters
    return DEFAULT_DISPLAY_FILTERS.get(strategy_name, {})


def apply_strategy_filters(
    query, Model, filters: dict, strategy_name: str | None = None
):
    """将策略 filters 转为 SQLAlchemy 过滤条件

    Args:
        query: SQLAlchemy query 对象
        Model: 数据模型类 (Mighty/Lianban/Jjmighty)
        filters: {"min_score": {"enabled": True, "value": 100}, ...}
        strategy_name: 策略名称，有值时只处理白名单内的 key

    Returns:
        添加了过滤条件的 query
    """
    allowed = STRATEGY_ALLOWED_FILTERS.get(strategy_name) if strategy_name else None
    for key, config in filters.items():
        if allowed and key not in allowed:
            continue
        if not config.get("enabled", True):
            continue

        reg = FILTER_REGISTRY.get(key)
        if not reg:
            continue

        attr_name = reg["attr"]
        op = reg["op"]
        threshold = config["value"]

        column = getattr(Model, attr_name, None)
        if column is None:
            continue

        # 时间字段直接比较字符串
        if attr_name == "times":
            threshold_str = str(threshold)
            if op == ">=":
                query = query.filter(column >= threshold_str)
            elif op == "<=":
                query = query.filter(column <= threshold_str)
        else:
            threshold_f = float(threshold)
            null_pass = reg.get("null_pass", False)
            if null_pass:
                # NULL 值兼容：字段为 NULL 时跳过该过滤条件（兼容旧数据）
                if op == ">=":
                    query = query.filter(or_(column.is_(None), column >= threshold_f))
                elif op == "<=":
                    query = query.filter(or_(column.is_(None), column <= threshold_f))
            else:
                # 严格模式：NULL 值不通过过滤
                if op == ">=":
                    query = query.filter(column >= threshold_f)
                elif op == "<=":
                    query = query.filter(column <= threshold_f)

    return query
