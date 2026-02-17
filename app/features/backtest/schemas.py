from pydantic import BaseModel


class FilterConfig(BaseModel):
    enabled: bool = True
    value: float | str


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


# --- 策略配置 CRUD ---

class StrategyCreate(BaseModel):
    name: str
    strategy_name: str
    filters: dict[str, FilterConfig]


class StrategyUpdate(BaseModel):
    name: str | None = None
    filters: dict[str, FilterConfig] | None = None


class StrategyItem(BaseModel):
    id: int
    name: str
    strategy_name: str
    filters: dict
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True


# --- 运行回测 ---

class BacktestRunRequest(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    filters: dict[str, FilterConfig]
    save: bool = False


class BacktestRunResponse(BaseModel):
    run_id: int | None = None
    stats: dict
    equity: list[dict]
    trades: list[dict]


# --- 公式对比 ---

class FormulaCoeffs(BaseModel):
    w_chg: float = 20      # chg_1min 权重
    w_bzf: float = 10      # changeRatio 权重
    w_flow: float = 0.05   # flow_velocity 系数
    w_main: float = 1.0    # 主板系数
    w_20cm: float = 0.6    # 创业板/科创板系数


class CompareRequest(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    filters: dict[str, FilterConfig] = {}
    old_threshold: int = 100
    new_threshold: int = 80
    coeffs: FormulaCoeffs = FormulaCoeffs()


class FormulaResult(BaseModel):
    label: str
    threshold: int
    stats: dict
    equity: list[dict]
    trades: list[dict]


class DiffItem(BaseModel):
    stockid: str
    stockname: str
    entry_date: str
    old_score: int
    new_score: int
    return_pct: float
    rates: float | None = None
    times: str = ""
    mins: int = 0
    lastzf: float | None = None


class CompareResponse(BaseModel):
    old_formula: FormulaResult
    new_formula: FormulaResult
    diff: dict
