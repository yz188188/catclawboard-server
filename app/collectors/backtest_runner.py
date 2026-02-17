# coding:utf-8
"""回测CLI入口

用法:
  python -m app.collectors.backtest_runner mighty 20250101 20250214
  python -m app.collectors.backtest_runner lianban 20250101 20250214
  python -m app.collectors.backtest_runner jjmighty 20250101 20250214
  python -m app.collectors.backtest_runner mighty 20250101 20250214 --min_score=150
  python -m app.collectors.backtest_runner mighty 20250101 20250214 --time_end=0935
  python -m app.collectors.backtest_runner mighty 20250101 20250214 --min_bzf=3 --max_bzf=8
  python -m app.collectors.backtest_runner mighty 20250101 20250214 --grid
"""
import sys
from itertools import product

from app.backtest.strategy import generate_trades, STRATEGIES, DEFAULT_PARAMS, GRID_RANGES
from app.backtest.engine import compute_stats, save_backtest
from app.database import SessionLocal


def parse_args():
    """解析CLI参数"""
    positional = []
    flags = set()
    params = {}

    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                key, val = arg[2:].split("=", 1)
                params[key] = val
            else:
                flags.add(arg[2:])
        else:
            positional.append(arg)

    strategy = positional[0] if len(positional) > 0 else "mighty"
    start_date = positional[1] if len(positional) > 1 else None
    end_date = positional[2] if len(positional) > 2 else None

    return strategy, start_date, end_date, params, flags


def run_single(strategy: str, start_date: str, end_date: str, params: dict, save: bool = True):
    """执行单次回测"""
    db = SessionLocal()
    try:
        merged_params = {**DEFAULT_PARAMS, **params}
        trades = generate_trades(db, strategy, start_date, end_date, merged_params)
        stats = compute_stats(trades)

        label = STRATEGIES[strategy]["label"]
        print(f"\n{'='*60}")
        print(f"策略: {label} ({strategy})")
        print(f"期间: {start_date} ~ {end_date}")
        print(f"参数: {merged_params}")
        print(f"{'='*60}")
        print(f"交易数: {stats['total_trades']}")
        print(f"盈利数: {stats['win_trades']}")
        print(f"胜  率: {stats['win_rate']*100:.1f}%")
        print(f"平均收益: {stats['avg_return']:.2f}%")
        print(f"累计收益: {stats['total_return']:.2f}%")
        print(f"最大回撤: {stats['max_drawdown']:.2f}%")
        print(f"夏普比率: {stats['sharpe_ratio']:.2f}")
        print(f"盈亏比: {stats['profit_factor']:.2f}")

        if save and trades:
            run = save_backtest(db, strategy, start_date, end_date, merged_params, trades)
            print(f"\n回测已保存，ID: {run.id}")

        return stats
    finally:
        db.close()


def run_grid(strategy: str, start_date: str, end_date: str):
    """参数网格搜索"""
    db = SessionLocal()
    try:
        keys = list(GRID_RANGES.keys())
        values = [GRID_RANGES[k] for k in keys]

        results = []
        for combo in product(*values):
            params = dict(zip(keys, combo))
            merged = {**DEFAULT_PARAMS, **params}
            trades = generate_trades(db, strategy, start_date, end_date, merged)
            stats = compute_stats(trades)
            results.append((params, stats))

        # 按胜率降序，再按平均收益降序排序
        results.sort(key=lambda x: (x[1]["win_rate"], x[1]["avg_return"]), reverse=True)

        # 输出表格
        label = STRATEGIES[strategy]["label"]
        print(f"\n{'='*100}")
        print(f"网格搜索结果: {label} ({strategy})  期间: {start_date} ~ {end_date}")
        print(f"{'='*100}")
        header = f"{'min_score':>10} {'min_rate':>9} {'min_bzf':>8} {'max_bzf':>8} {'time_end':>9} "
        header += f"{'交易数':>6} {'胜率':>7} {'平均收益':>8} {'累计收益':>8} {'回撤':>7} {'夏普':>6} {'盈亏比':>7}"
        print(header)
        print("-" * 100)

        best = results[0] if results else None
        for i, (params, stats) in enumerate(results):
            if stats["total_trades"] == 0:
                continue
            marker = " <-- 最优" if i == 0 else ""
            row = (
                f"{params['min_score']:>10} "
                f"{params['min_rate']:>9} "
                f"{params['min_bzf']:>8} "
                f"{params['max_bzf']:>8} "
                f"{params['time_end']:>9} "
                f"{stats['total_trades']:>6} "
                f"{stats['win_rate']*100:>6.1f}% "
                f"{stats['avg_return']:>7.2f}% "
                f"{stats['total_return']:>7.2f}% "
                f"{stats['max_drawdown']:>6.2f}% "
                f"{stats['sharpe_ratio']:>6.2f} "
                f"{stats['profit_factor']:>6.2f}"
                f"{marker}"
            )
            print(row)

        # 保存最优结果
        if best and best[1]["total_trades"] > 0:
            best_params = {**DEFAULT_PARAMS, **best[0]}
            best_trades = generate_trades(db, strategy, start_date, end_date, best_params)
            run = save_backtest(db, strategy, start_date, end_date, best_params, best_trades)
            print(f"\n最优参数回测已保存，ID: {run.id}")

    finally:
        db.close()


def main():
    strategy, start_date, end_date, params, flags = parse_args()

    if strategy not in STRATEGIES:
        print(f"未知策略: {strategy}，可选: {list(STRATEGIES.keys())}")
        sys.exit(1)

    if not start_date or not end_date:
        print("用法: python -m app.collectors.backtest_runner <strategy> <start_date> <end_date> [--params] [--grid]")
        print(f"策略: {list(STRATEGIES.keys())}")
        sys.exit(1)

    if "grid" in flags:
        run_grid(strategy, start_date, end_date)
    else:
        run_single(strategy, start_date, end_date, params)


if __name__ == "__main__":
    main()
