from pydantic import BaseModel


class BacktestRunItem(BaseModel):
    id: int
    strategy_name: str
    strategy_label: str | None = None
    start_date: str
    end_date: str
    params: dict | None = None
    total_trades: int = 0
    win_trades: int = 0
    win_rate: float | None = None
    avg_return: float | None = None
    total_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class BacktestRunListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[BacktestRunItem]


class BacktestTradeItem(BaseModel):
    id: int
    run_id: int
    stockid: str
    stockname: str | None = None
    entry_date: str
    return_pct: float | None = None
    signal_data: dict | None = None

    class Config:
        from_attributes = True


class BacktestEquityItem(BaseModel):
    id: int
    run_id: int
    tdate: str
    equity: float
    drawdown: float | None = None

    class Config:
        from_attributes = True
