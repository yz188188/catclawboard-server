# coding:utf-8
from sqlalchemy import Column, Integer, String, DECIMAL, JSON, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class BacktestRun(Base):
    __tablename__ = "db_backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False, index=True)
    strategy_label = Column(String(100))
    start_date = Column(String(8), nullable=False)
    end_date = Column(String(8), nullable=False)
    params = Column(JSON)
    total_trades = Column(Integer, default=0)
    win_trades = Column(Integer, default=0)
    win_rate = Column(DECIMAL(10, 4))
    avg_return = Column(DECIMAL(10, 4))
    total_return = Column(DECIMAL(10, 4))
    max_drawdown = Column(DECIMAL(10, 4))
    sharpe_ratio = Column(DECIMAL(10, 4))
    profit_factor = Column(DECIMAL(10, 4))
    created_at = Column(TIMESTAMP, server_default=func.now())


class BacktestTrade(Base):
    __tablename__ = "db_backtest_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("db_backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    entry_date = Column(String(8), nullable=False)
    return_pct = Column(DECIMAL(10, 4))
    signal_data = Column(JSON)


class BacktestEquity(Base):
    __tablename__ = "db_backtest_equity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("db_backtest_runs.id", ondelete="CASCADE"), nullable=False)
    tdate = Column(String(8), nullable=False)
    equity = Column(DECIMAL(15, 4), nullable=False)
    drawdown = Column(DECIMAL(10, 4))

    __table_args__ = (
        UniqueConstraint("run_id", "tdate", name="uk_equity_run_date"),
    )
