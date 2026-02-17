# coding:utf-8
"""评分公式对比CLI

用法:
  python -m app.collectors.score_compare mighty 20250101 20250217
  python -m app.collectors.score_compare mighty 20250101 20250217 --threshold=80
  python -m app.collectors.score_compare lianban 20250101 20250217 --old_threshold=100 --new_threshold=80
  python -m app.collectors.score_compare mighty 20250101 20250217 --w_chg=25 --w_bzf=8 --w_flow=0.08
"""
import sys
from collections import defaultdict

from app.backtest.strategy import STRATEGIES, Trade, apply_filters, params_to_filters, DEFAULT_PARAMS
from app.backtest.engine import compute_stats
from app.database import SessionLocal


def recalculate(rec, coeffs=None):
    """用DB字段重算新旧分数

    Args:
        rec: 数据库记录
        coeffs: 新公式系数字典, 可选键: w_chg, w_bzf, w_flow, w_main, w_20cm

    Returns:
        (old_score, new_score, mins)
    """
    c = coeffs or {}
    w_chg = c.get("w_chg", 20)
    w_bzf = c.get("w_bzf", 10)
    w_flow = c.get("w_flow", 0.05)
    w_main = c.get("w_main", 1.0)
    w_20cm = c.get("w_20cm", 0.6)

    chg = float(rec.chg_1min or 0)
    bzf = float(rec.bzf or 0)
    zst = float(rec.zs_times or 1.0)
    cje = float(rec.cje or 0)
    rates = float(rec.rates or 0)

    # times="0935" -> mins=5
    t = rec.times or "0930"
    h, m = int(t[:2]), int(t[2:])
    mins = (h * 60 + m) - 570

    # 旧公式不变（固定系数，用DB原始 zst）
    old_momentum = (chg * 20 + bzf * 10) * zst
    old_score = round(old_momentum + cje * 0.001)

    # 新公式使用可调系数 + 可调板块系数
    new_zst = w_20cm if zst < 1.0 else w_main
    new_momentum = (chg * w_chg + bzf * w_bzf) * new_zst
    flow_velocity = rates / max(mins, 1)
    new_score = round(new_momentum * (1 + flow_velocity * w_flow))
    return old_score, new_score, mins


def build_trades(records, threshold, use_new_score=False, coeffs=None):
    """按门槛过滤记录，构建Trade列表"""
    trades = []
    for rec in records:
        old_score, new_score, mins = recalculate(rec, coeffs=coeffs)
        score = new_score if use_new_score else old_score
        if score < threshold:
            continue

        bzf = float(rec.bzf) if rec.bzf is not None else 0
        return_pct = float(rec.lastzf) - bzf

        trades.append(Trade(
            stockid=rec.stockid,
            stockname=rec.stockname or "",
            entry_date=rec.cdate,
            return_pct=round(return_pct, 4),
            signal_data={
                "scores": float(rec.scores) if rec.scores is not None else None,
                "old_score": old_score,
                "new_score": new_score,
                "bzf": bzf,
                "lastzf": float(rec.lastzf),
                "rates": float(rec.rates) if rec.rates is not None else None,
                "cje": float(rec.cje) if rec.cje is not None else None,
                "times": rec.times or "",
                "mins": mins,
            },
        ))
    return trades


def print_stats(label, stats):
    """打印统计信息"""
    print(f"\n  [{label}]")
    print(f"  交易数: {stats['total_trades']}")
    print(f"  盈利数: {stats['win_trades']}")
    print(f"  胜  率: {stats['win_rate']*100:.1f}%")
    print(f"  平均收益: {stats['avg_return']:.2f}%")
    print(f"  累计收益: {stats['total_return']:.2f}%")
    print(f"  最大回撤: {stats['max_drawdown']:.2f}%")
    print(f"  夏普比率: {stats['sharpe_ratio']:.2f}")
    print(f"  盈亏比: {stats['profit_factor']:.2f}")


def run_compare(strategy_name, start_date, end_date, old_threshold=100, new_threshold=80, filters=None, coeffs=None):
    """执行公式对比"""
    db = SessionLocal()
    try:
        Model = STRATEGIES[strategy_name]["model"]
        label = STRATEGIES[strategy_name]["label"]

        # 查询所有有收盘涨幅的记录
        query = (
            db.query(Model)
            .filter(Model.cdate >= start_date, Model.cdate <= end_date)
            .filter(Model.lastzf.isnot(None))
        )
        records = query.all()

        # 先应用基础过滤（除score外的过滤器）
        if filters:
            records = [r for r in records if apply_filters(r, filters)]

        print(f"\n{'='*70}")
        print(f"评分公式对比: {label} ({strategy_name})")
        print(f"期间: {start_date} ~ {end_date}")
        print(f"总记录数(过滤后): {len(records)}")
        print(f"旧公式门槛: {old_threshold}  |  新公式门槛: {new_threshold}")
        c = coeffs or {}
        print(f"新公式系数: w_chg={c.get('w_chg', 20)}, w_bzf={c.get('w_bzf', 10)}, w_flow={c.get('w_flow', 0.05)}, w_main={c.get('w_main', 1.0)}, w_20cm={c.get('w_20cm', 0.6)}")
        print(f"{'='*70}")

        # 旧公式（固定系数，不传coeffs）
        old_trades = build_trades(records, old_threshold, use_new_score=False)
        old_stats = compute_stats(old_trades)

        # 新公式（使用可调系数）
        new_trades = build_trades(records, new_threshold, use_new_score=True, coeffs=coeffs)
        new_stats = compute_stats(new_trades)

        print("\n--- 统计对比 ---")
        print_stats(f"旧公式(加法) 门槛={old_threshold}", old_stats)
        print_stats(f"新公式(流速乘数) 门槛={new_threshold}", new_stats)

        # 差异分析
        old_keys = {(t.stockid, t.entry_date) for t in old_trades}
        new_keys = {(t.stockid, t.entry_date) for t in new_trades}
        old_only = old_keys - new_keys
        new_only = new_keys - old_keys
        both = old_keys & new_keys

        print(f"\n--- 差异分析 ---")
        print(f"  旧有新无: {len(old_only)} 笔")
        print(f"  新有旧无: {len(new_only)} 笔")
        print(f"  两者都有: {len(both)} 笔")

        # 旧有新无的典型案例
        if old_only:
            old_only_trades = [t for t in old_trades if (t.stockid, t.entry_date) in old_only]
            old_only_trades.sort(key=lambda t: t.signal_data.get("old_score", 0), reverse=True)
            print(f"\n--- 旧有新无 TOP10 (被新公式淘汰) ---")
            print(f"  {'日期':<10} {'代码':<12} {'名称':<8} {'旧分':>6} {'新分':>6} {'收益%':>7} {'换手率':>7} {'mins':>5}")
            for t in old_only_trades[:10]:
                sd = t.signal_data
                print(f"  {t.entry_date:<10} {t.stockid:<12} {t.stockname:<8} "
                      f"{sd.get('old_score', 0):>6} {sd.get('new_score', 0):>6} "
                      f"{t.return_pct:>7.2f} {sd.get('rates', 0) or 0:>7.1f} {sd.get('mins', 0):>5}")

        # 新有旧无的典型案例
        if new_only:
            new_only_trades = [t for t in new_trades if (t.stockid, t.entry_date) in new_only]
            new_only_trades.sort(key=lambda t: t.signal_data.get("new_score", 0), reverse=True)
            print(f"\n--- 新有旧无 TOP10 (被新公式发掘) ---")
            print(f"  {'日期':<10} {'代码':<12} {'名称':<8} {'旧分':>6} {'新分':>6} {'收益%':>7} {'换手率':>7} {'mins':>5}")
            for t in new_only_trades[:10]:
                sd = t.signal_data
                print(f"  {t.entry_date:<10} {t.stockid:<12} {t.stockname:<8} "
                      f"{sd.get('old_score', 0):>6} {sd.get('new_score', 0):>6} "
                      f"{t.return_pct:>7.2f} {sd.get('rates', 0) or 0:>7.1f} {sd.get('mins', 0):>5}")

        # 多门槛对比
        print(f"\n--- 多门槛对比 ---")
        thresholds = [60, 80, 100, 120, 150, 200]
        print(f"  {'门槛':>6} | {'旧-交易数':>10} {'旧-胜率':>8} {'旧-累计':>8} | {'新-交易数':>10} {'新-胜率':>8} {'新-累计':>8}")
        print(f"  {'-'*80}")
        for th in thresholds:
            ot = build_trades(records, th, use_new_score=False)
            os = compute_stats(ot)
            nt = build_trades(records, th, use_new_score=True, coeffs=coeffs)
            ns = compute_stats(nt)
            print(f"  {th:>6} | {os['total_trades']:>10} {os['win_rate']*100:>7.1f}% {os['total_return']:>7.2f}% | "
                  f"{ns['total_trades']:>10} {ns['win_rate']*100:>7.1f}% {ns['total_return']:>7.2f}%")

    finally:
        db.close()


def parse_args():
    positional = []
    params = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                key, val = arg[2:].split("=", 1)
                params[key] = val
            else:
                params[arg[2:]] = True
        else:
            positional.append(arg)

    strategy = positional[0] if len(positional) > 0 else "mighty"
    start_date = positional[1] if len(positional) > 1 else None
    end_date = positional[2] if len(positional) > 2 else None

    old_threshold = int(params.get("old_threshold", params.get("threshold", 100)))
    new_threshold = int(params.get("new_threshold", params.get("threshold", 80)))

    coeffs = {}
    if "w_chg" in params:
        coeffs["w_chg"] = float(params["w_chg"])
    if "w_bzf" in params:
        coeffs["w_bzf"] = float(params["w_bzf"])
    if "w_flow" in params:
        coeffs["w_flow"] = float(params["w_flow"])
    if "w_main" in params:
        coeffs["w_main"] = float(params["w_main"])
    if "w_20cm" in params:
        coeffs["w_20cm"] = float(params["w_20cm"])

    return strategy, start_date, end_date, old_threshold, new_threshold, coeffs


def main():
    strategy, start_date, end_date, old_threshold, new_threshold, coeffs = parse_args()

    if strategy not in STRATEGIES:
        print(f"未知策略: {strategy}，可选: {list(STRATEGIES.keys())}")
        sys.exit(1)

    if not start_date or not end_date:
        print("用法: python -m app.collectors.score_compare <strategy> <start_date> <end_date> [--threshold=80] [--old_threshold=100] [--new_threshold=80] [--w_chg=20] [--w_bzf=10] [--w_flow=0.05] [--w_main=1.0] [--w_20cm=0.6]")
        sys.exit(1)

    # 构建非score的基础过滤
    base_params = {k: v for k, v in DEFAULT_PARAMS.items() if k != "min_score"}
    filters = params_to_filters(base_params)

    run_compare(strategy, start_date, end_date, old_threshold, new_threshold, filters, coeffs=coeffs or None)


if __name__ == "__main__":
    main()
