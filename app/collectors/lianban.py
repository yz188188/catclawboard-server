# coding:utf-8
"""连板反包数据采集

股票池来源: db_zt_reson 中 lbs >= 2 的连板股
过滤/评分逻辑: 复用 mighty（强势反包）完全相同的筛选条件
昨日成交额: db_zt_reson.cje（单位: 亿）× 1e8 → 元

实时监控模式 (9:30-9:46): 每3秒扫描一次连板股票池
收盘更新模式 (--close):   更新入选股票的收盘涨幅

用法:
  python -m app.collectors.lianban                     实时监控 (9:30-9:46)
  python -m app.collectors.lianban --close             收盘后更新收盘涨幅
  python -m app.collectors.lianban 2025-02-14 --close  指定日期更新收盘涨幅
"""
import json
import sys
import time as sys_time
from datetime import datetime, time as dt_time

from sqlalchemy.orm import Session

from app.collectors import func
from app.collectors.models import ZtReson
from app.features.lianban.models import Lianban

try:
    from iFinDPy import THS_RQ
except ImportError:
    THS_RQ = None


def should_execute() -> bool:
    """判断当前时间是否在执行窗口 9:30-9:46"""
    now = datetime.now().time()
    return dt_time(9, 30) <= now <= dt_time(9, 46)


def collect_lianban(trading_day: str, db: Session) -> dict:
    """连板反包实时监控采集

    从 db_zt_reson 读取昨日连板数 >= 2 的股票池，
    在 9:30-9:46 期间每 3 秒扫描一轮，筛选强势分时股写入 db_lianban。

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

    # 读取昨日连板股票池 (lbs >= 2)
    zt_records = (
        db.query(ZtReson)
        .filter(ZtReson.cdate == lsdate, ZtReson.lbs >= 2)
        .all()
    )
    if not zt_records:
        return {"error": f"db_zt_reson 中无 {lsdate} 的连板(lbs>=2)数据"}

    # stock_pool: stockid -> {amount_yuan, lbs}
    # cje 单位是亿，转换为元
    stock_pool = {}
    for rec in zt_records:
        stock_pool[rec.stockid] = {
            "amount": float(rec.cje) * 1e8,
            "lbs": rec.lbs,
        }

    codes_list = ", ".join(stock_pool.keys())
    print(f"连板反包监控启动，股票池: {len(stock_pool)} 只，日期: {cdate}")

    total_found = 0
    loop_count = 0

    while should_execute():
        loop_count += 1
        sys_time.sleep(3)

        now = datetime.now()
        hm = now.strftime("%H%M")
        ms = now.strftime("%M:%S")

        data_result = THS_RQ(
            codes_list,
            "preClose;open;latest;changeRatio;upperLimit;amount;tradeStatus;chg_1min",
            "", "format:json",
        )

        if data_result.errorcode != 0:
            print(f"THS_RQ 错误: {data_result.errmsg}")
            continue

        jdata = json.loads(data_result.data)

        for item in jdata["tables"]:
            thscode = item["thscode"]

            exists = db.query(Lianban).filter(
                Lianban.cdate == cdate, Lianban.stockid == thscode
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
                continue

            # 过滤已涨停
            if upper_limit[0] is not None and float(latest[0]) == float(upper_limit[0]):
                continue

            # 成交额占比: 当前成交额 / 昨日总成交额 * 100
            ls_amount = stock_pool[thscode]["amount"]
            if ls_amount <= 0:
                continue
            cje_rate = round(amount[0] / ls_amount * 100, 2)
            if cje_rate < 7:
                continue

            # 振幅: (最新价 - 开盘价) / 开盘价 * 100
            zhenfu = round(float(latest[0]) / float(open_price[0]) * 100 - 100, 2)
            if zhenfu < 3:
                continue

            # 1分钟涨速
            if not chg_1min[0] or chg_1min[0] < 1:
                continue

            # 板块系数
            thscoder = thscode.split(".")
            code_prefix = thscoder[0][:2]
            zs_times = 0.6 if code_prefix in ("68", "30") else 1.0

            # 成交额（万）
            cje = round(amount[0] / 10000)

            # 评分
            score = round((chg_1min[0] * 20 + change_ratio[0] * 10) * zs_times + cje * 0.001)
            if score < 100:
                continue

            # 开盘涨幅
            ozf = round(float(open_price[0]) / float(pre_close[0]) * 100 - 100, 2)

            record = Lianban(
                cdate=cdate,
                stockid=thscode,
                stockname=thscoder[0],
                lbs=stock_pool[thscode]["lbs"],
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
            print(f"入选: {thscode} {stock_pool[thscode]['lbs']}连板 评分={score} "
                  f"涨幅={round(change_ratio[0], 2)}% 换手率={cje_rate}% 时间={hm}")

    print(f"连板反包监控结束，共 {loop_count} 轮，入选 {total_found} 只")
    return {"date": cdate, "loops": loop_count, "found": total_found}


def update_close_price(trading_day: str, db: Session) -> dict:
    """收盘后更新入选股票的收盘涨幅"""
    if THS_RQ is None:
        return {"error": "iFinDPy not available"}

    cdate = datetime.strptime(trading_day, "%Y-%m-%d").strftime("%Y%m%d")

    records = db.query(Lianban).filter(Lianban.cdate == cdate).all()
    if not records:
        return {"date": cdate, "updated": 0, "msg": "无入选记录"}

    code_map = {rec.stockid: rec for rec in records}
    codes_list = ", ".join(code_map.keys())

    data_result = THS_RQ(codes_list, "changeRatio", "", "format:json")
    if data_result.errorcode != 0:
        return {"error": data_result.errmsg}

    jdata = json.loads(data_result.data)
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

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    close_mode = "--close" in sys.argv

    date_arg = args[0] if args else datetime.today().strftime("%Y-%m-%d")
    trading_day = func.get_trading_day(date_arg)

    func.thslogin()
    db = SessionLocal()
    try:
        if close_mode:
            result = update_close_price(trading_day, db)
            print(f"连板反包收盘涨幅更新完成: {result}")
        else:
            result = collect_lianban(trading_day, db)
            print(f"连板反包采集完成: {result}")
    finally:
        db.close()
        func.thslogout()
