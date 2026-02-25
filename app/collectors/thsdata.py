# coding:utf-8
"""涨停反包数据采集 — 原 python/thsdata.py 迁移
将 Redis 中间层替换为直接写入 Cloud SQL (SQLAlchemy)
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.collectors import func
from app.collectors.models import ZtReson
from app.features.ztdb.models import Ztdb
from app.features.mighty.models import LargeAmount

try:
    from iFinDPy import THS_DR, THS_RQ, THS_HQ, THS_WCQuery
except ImportError:
    THS_DR = None
    THS_RQ = None
    THS_HQ = None
    THS_WCQuery = None


def collect_ztdb(trading_day: str, db: Session) -> dict:
    """采集涨停反包数据并写入数据库

    Args:
        trading_day: 交易日 YYYY-MM-DD 格式
        db: SQLAlchemy Session

    Returns:
        统计信息
    """
    if THS_DR is None:
        return {"error": "iFinDPy not available"}

    tradingday_obj = datetime.strptime(trading_day, "%Y-%m-%d")
    cdate = tradingday_obj.strftime("%Y%m%d")
    yesterday_str = func.get_previous_trading_day(trading_day)
    lsdate = yesterday_str.replace("-", "")

    # 从 db_zt_reson 获取昨日涨停股票列表 (由 stat.py 采集写入)
    lszt_records = db.query(ZtReson).filter(ZtReson.cdate == lsdate).all()
    if not lszt_records:
        print(f"警告: db_zt_reson 中无 {lsdate} 的数据，请先运行 stat.py 采集昨日涨停数据")
    lszt_stocks = {}
    for rec in lszt_records:
        lszt_stocks[rec.stockid] = {
            "name": rec.stockname,
            "lbs": rec.lbs,
        }

    # 获取全部A股实时行情
    date_params = f"date={cdate}"
    data_codes = THS_DR(
        "p03291",
        date_params + ";blockname=001005010;iv_type=allcontract",
        "p03291_f001:Y,p03291_f002:Y,p03291_f003:Y,p03291_f004:Y",
    )

    if data_codes.errorcode != 0:
        return {"error": data_codes.errmsg}

    codes_list = data_codes.data["p03291_f002"].tolist()
    names_list = data_codes.data["p03291_f003"].tolist()

    data_result = THS_RQ(
        codes_list,
        "changeRatio;latest;high;low;open;upperLimit;lowerLimit;preClose;amount;tradeStatus",
        "", "format:json",
    )

    if data_result.errorcode != 0:
        return {"error": data_result.errmsg}

    jdata = json.loads(data_result.data.decode('gb18030'))

    # 获取ST股列表
    st_stocks = THS_WCQuery(cdate + " ST股票", "stock", "format:json")
    st_sids = set()
    if st_stocks.errorcode == 0:
        st_data = json.loads(st_stocks.data.decode('gb18030'))
        st_sids = set(st_data["tables"][0]["table"]["股票代码"])

    # 清除当日旧数据
    db.query(Ztdb).filter(Ztdb.cdate == cdate).delete()
    db.query(LargeAmount).filter(LargeAmount.cdate == cdate).delete()

    ztdb_count = 0
    large_amount_count = 0
    for item in jdata["tables"]:
        latest = item["table"]["latest"]
        pre_close = item["table"]["preClose"]
        upper_limit = item["table"]["upperLimit"]
        high = item["table"]["high"]
        low = item["table"]["low"]
        amount = item["table"]["amount"]
        lower_limit = item["table"].get("lowerLimit", [None])
        trade_status = item["table"]["tradeStatus"]
        thscode = item["thscode"]
        thscoder = thscode.split(".")

        # 过滤北交所、非交易、ST
        if thscoder[1] == "BJ" or trade_status[0] != "交易" or thscode in st_sids:
            continue

        # 跳过当日涨停
        if latest[0] == upper_limit[0]:
            continue

        # 入池条件（OR）：成交额>8亿 / 当日跌停 / 冲高回落>=5%
        is_large = amount[0] and amount[0] >= 800000000
        is_limit_down = lower_limit[0] is not None and latest[0] == lower_limit[0]
        # 冲高回落：盘中最高价须高于昨收3%以上，且从高点回落>=5%
        rise_from_pre = round((high[0] - pre_close[0]) / pre_close[0] * 100, 2) if pre_close[0] else 0
        drop_from_high = round((high[0] - latest[0]) / high[0] * 100, 2) if high[0] else 0
        is_pullback = rise_from_pre >= 3 and drop_from_high >= 5
        if is_large or is_limit_down or is_pullback:
            db.add(LargeAmount(cdate=cdate, stockid=thscode, amount=amount[0] or 0))
            large_amount_count += 1

        # 昨日涨停股中振幅>=10且回撤<10的
        if thscode in lszt_stocks:
            zhenfu = round((high[0] - low[0]) / pre_close[0] * 100, 2)
            declines = round((high[0] - latest[0]) / high[0] * 100, 2)
            if zhenfu >= 10 and declines < 10:
                stock_name = names_list[codes_list.index(thscode)] if thscode in codes_list else ""
                record = Ztdb(
                    cdate=cdate,
                    stockid=thscode,
                    stockname=stock_name,
                    zhenfu=zhenfu,
                    declines=declines,
                )
                db.add(record)
                ztdb_count += 1

    db.commit()
    return {"date": cdate, "ztdb_count": ztdb_count, "large_amount_count": large_amount_count}


def backfill_large_amount(cdate: str, db: Session) -> dict:
    """补采指定日期的大额成交数据（历史数据）

    用 THS_DR 获取 A 股代码列表，THS_HQ 获取指定日期历史成交额，
    过滤成交额 > 8 亿写入 db_large_amount。

    Args:
        cdate: 交易日 YYYYMMDD 格式
        db: SQLAlchemy Session

    Returns:
        统计信息
    """
    if THS_DR is None or THS_HQ is None:
        return {"error": "iFinDPy not available"}

    trading_day = f"{cdate[:4]}-{cdate[4:6]}-{cdate[6:]}"

    # 获取全部 A 股代码
    data_codes = THS_DR(
        "p03291",
        f"date={cdate};blockname=001005010;iv_type=allcontract",
        "p03291_f001:Y,p03291_f002:Y,p03291_f003:Y,p03291_f004:Y",
    )
    if data_codes.errorcode != 0:
        return {"error": f"THS_DR 失败: {data_codes.errmsg}"}

    codes_list = data_codes.data["p03291_f002"].tolist()

    # 用 THS_HQ 批量获取历史成交额
    codes_str = ";".join(codes_list)
    data_hq = THS_HQ(codes_str, "amount", "", trading_day, trading_day, "format:json")
    if data_hq.errorcode != 0:
        return {"error": f"THS_HQ 失败: {data_hq.errmsg}"}

    jdata = json.loads(data_hq.data.decode("gb18030"))

    # 清除当日旧数据
    db.query(LargeAmount).filter(LargeAmount.cdate == cdate).delete()

    count = 0
    for item in jdata["tables"]:
        thscode = item["thscode"]
        amount_list = item["table"].get("amount", [])
        if not amount_list:
            continue
        amount = amount_list[0]
        if amount and amount >= 800000000:
            db.add(LargeAmount(cdate=cdate, stockid=thscode, amount=amount))
            count += 1

    db.commit()
    return {"date": cdate, "large_amount_count": count}


if __name__ == "__main__":
    import sys
    from app.database import SessionLocal

    date_arg = sys.argv[1] if len(sys.argv) > 1 else datetime.today().strftime("%Y-%m-%d")
    trading_day = func.get_trading_day(date_arg)

    func.thslogin()
    db = SessionLocal()
    try:
        result = collect_ztdb(trading_day, db)
        print(f"thsdata 采集完成: {result}")
    finally:
        db.close()
        func.thslogout()
