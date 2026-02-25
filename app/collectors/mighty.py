# coding:utf-8
"""强势反包数据采集 — 原 python/mighty.py 迁移

实时监控模式 (9:30-9:46): 每3秒扫描一次高成交额股票池，筛选强势分时股
收盘更新模式 (--close):   更新入选股票的收盘涨幅

用法:
  python -m app.collectors.mighty                     实时监控 (9:30-9:46)
  python -m app.collectors.mighty --close             收盘后更新当日收盘涨幅
  python -m app.collectors.mighty 2025-02-14 --close  指定日期更新收盘涨幅
"""
import json
import sys
import time as sys_time
from datetime import datetime, time as dt_time

from sqlalchemy.orm import Session

from app.collectors import func
from app.features.mighty.models import LargeAmount, Mighty

try:
    from iFinDPy import THS_RQ
except ImportError:
    THS_RQ = None


def should_execute() -> bool:
    """判断当前时间是否在执行窗口 9:30-9:46"""
    now = datetime.now().time()
    return dt_time(9, 30) <= now <= dt_time(9, 46)


def collect_mighty(trading_day: str, db: Session) -> dict:
    """强势反包实时监控采集

    从 db_large_amount 读取昨日成交额 > 8亿的股票池，
    在 9:30-9:46 期间每 3 秒扫描一轮，筛选强势分时股写入 db_mighty。

    Args:
        trading_day: 交易日 YYYY-MM-DD 格式
        db: SQLAlchemy Session

    Returns:
        统计信息
    """
    if THS_RQ is None:
        return {"error": "iFinDPy not available"}

    cdate = datetime.strptime(trading_day, "%Y-%m-%d").strftime("%Y%m%d")
    yesterday_str = func.get_previous_trading_day(trading_day)
    lsdate = yesterday_str.replace("-", "")

    # 读取昨日大成交额股票池
    la_records = db.query(LargeAmount).filter(LargeAmount.cdate == lsdate).all()
    if not la_records:
        return {"error": f"db_large_amount 中无 {lsdate} 的数据，请先运行 thsdata 采集"}

    stock_pool = {}
    for rec in la_records:
        stock_pool[rec.stockid] = float(rec.amount)

    # 分批查询
    BATCH_SIZE = 200
    code_keys = list(stock_pool.keys())
    batches = [code_keys[i:i+BATCH_SIZE] for i in range(0, len(code_keys), BATCH_SIZE)]
    print(f"强势反包监控启动，股票池: {len(stock_pool)} 只({len(batches)}批)，日期: {cdate}")

    total_found = 0
    loop_count = 0
    filter_stats = {"none_data": 0, "upper_limit": 0, "cje_rate": 0, "zhenfu": 0, "chg_1min": 0, "score": 0, "passed": 0}

    while should_execute():
        loop_count += 1
        sys_time.sleep(3)

        now = datetime.now()
        hm = now.strftime("%H%M")
        ms = now.strftime("%M:%S")

        for batch in batches:
            batch_codes = ", ".join(batch)
            data_result = THS_RQ(
                batch_codes,
                "preClose;open;latest;changeRatio;upperLimit;amount;tradeStatus;chg_1min",
                "", "format:json",
            )

            if data_result.errorcode != 0:
                print(f"THS_RQ 错误: {data_result.errmsg}")
                continue

            jdata = json.loads(data_result.data.decode('gb18030'))

            for item in jdata["tables"]:
                thscode = item["thscode"]

                # 检查是否已入选（UNIQUE约束也会防止重复，但提前跳过更高效）
                exists = db.query(Mighty).filter(
                    Mighty.cdate == cdate, Mighty.stockid == thscode
                ).first()
                if exists:
                    continue

                latest = item["table"]["latest"]
                upper_limit = item["table"]["upperLimit"]
                open_price = item["table"]["open"]
                pre_close = item["table"]["preClose"]
                chg_1min = item["table"]["chg_1min"]
                change_ratio = item["table"]["changeRatio"]
                amount = item["table"]["amount"]

                if latest[0] is None or open_price[0] is None or pre_close[0] is None:
                    filter_stats["none_data"] += 1
                    continue

                # 过滤已涨停
                if upper_limit[0] is not None and float(latest[0]) == float(upper_limit[0]):
                    filter_stats["upper_limit"] += 1
                    continue

                # 成交额占比（换手率）: 当前成交额 / 昨日总成交额 * 100
                ls_amount = stock_pool[thscode]
                cje_rate = round(amount[0] / ls_amount * 100, 2)
                if cje_rate < 7:
                    filter_stats["cje_rate"] += 1
                    continue

                # 振幅: (最新价 - 开盘价) / 开盘价 * 100
                zhenfu = round(float(latest[0]) / float(open_price[0]) * 100 - 100, 2)
                if zhenfu < 3:
                    filter_stats["zhenfu"] += 1
                    continue

                # 1分钟涨速
                if not chg_1min[0] or chg_1min[0] < 1:
                    filter_stats["chg_1min"] += 1
                    continue

                # 板块系数: 创业板(30)/科创板(68) = 0.6，主板 = 1.0
                thscoder = thscode.split(".")
                code_prefix = thscoder[0][:2]
                zs_times = 0.6 if code_prefix in ("68", "30") else 1.0

                # 成交额（万）
                cje = round(amount[0] / 10000)

                # 评分: (涨速 * 20 + 最新涨幅 * 10) * 板块系数 + 成交额(万) * 0.001
                score = round((chg_1min[0] * 20 + change_ratio[0] * 10) * zs_times + cje * 0.001)
                if score < 100:
                    filter_stats["score"] += 1
                    continue

                filter_stats["passed"] += 1

                # 开盘涨幅
                ozf = round(float(open_price[0]) / float(pre_close[0]) * 100 - 100, 2)

                record = Mighty(
                    cdate=cdate,
                    stockid=thscode,
                    stockname=thscoder[0],
                    scores=score,
                    times=hm,
                    bzf=round(change_ratio[0], 2),
                    cje=cje,
                    rates=cje_rate,
                    ozf=ozf,
                    zhenfu=zhenfu,
                    chg_1min=round(chg_1min[0], 2),
                    zs_times=zs_times,
                    tms=ms,
                )
                db.add(record)
                db.commit()
                total_found += 1
                print(f"入选: {thscode} 评分={score} 涨幅={round(change_ratio[0], 2)}% "
                      f"涨速={chg_1min[0]}% 换手率={cje_rate}% 时间={hm}")

        if loop_count % 30 == 0:
            print(f"第{loop_count}轮 过滤统计: {filter_stats}")

    print(f"监控结束，共 {loop_count} 轮，入选 {total_found} 只")
    print(f"最终过滤统计: {filter_stats}")
    return {"date": cdate, "loops": loop_count, "found": total_found}


def update_close_price(trading_day: str, db: Session) -> dict:
    """收盘后更新入选股票的收盘涨幅

    Args:
        trading_day: 交易日 YYYY-MM-DD 格式
        db: SQLAlchemy Session

    Returns:
        统计信息
    """
    if THS_RQ is None:
        return {"error": "iFinDPy not available"}

    cdate = datetime.strptime(trading_day, "%Y-%m-%d").strftime("%Y%m%d")

    records = db.query(Mighty).filter(Mighty.cdate == cdate).all()
    if not records:
        return {"date": cdate, "updated": 0, "msg": "无入选记录"}

    code_map = {rec.stockid: rec for rec in records}
    codes_list = ", ".join(code_map.keys())

    data_result = THS_RQ(codes_list, "changeRatio", "", "format:json")
    if data_result.errorcode != 0:
        return {"error": data_result.errmsg}

    jdata = json.loads(data_result.data.decode('gb18030'))
    updated = 0
    for item in jdata["tables"]:
        thscode = item["thscode"]
        change_ratio = item["table"]["changeRatio"]
        if thscode in code_map and change_ratio[0] is not None:
            code_map[thscode].lastzf = round(change_ratio[0], 2)
            updated += 1
            print(f"更新 {thscode} 收盘涨幅: {round(change_ratio[0], 2)}%")

    db.commit()
    return {"date": cdate, "updated": updated}


if __name__ == "__main__":
    from app.database import SessionLocal

    # 解析参数
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    close_mode = "--close" in sys.argv

    date_arg = args[0] if args else datetime.today().strftime("%Y-%m-%d")
    trading_day = func.get_trading_day(date_arg)

    func.thslogin()
    db = SessionLocal()
    try:
        if close_mode:
            result = update_close_price(trading_day, db)
            print(f"收盘涨幅更新完成: {result}")
        else:
            result = collect_mighty(trading_day, db)
            print(f"强势反包采集完成: {result}")
    finally:
        db.close()
        func.thslogout()
