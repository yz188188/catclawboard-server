# coding:utf-8
"""竞价一字+爆量采集 — 原 python/bidding.py 迁移
将 Redis 中间层替换为直接写入 Cloud SQL (SQLAlchemy)
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.collectors import func
from app.collectors.models import ZtReson
from app.features.jjztdt.models import Jjztdt
from app.features.jjbvol.models import Jjbvol

try:
    from iFinDPy import THS_DR, THS_RQ, THS_HQ
except ImportError:
    THS_DR = None
    THS_RQ = None
    THS_HQ = None


def collect_bidding(trading_day: str, db: Session) -> dict:
    """采集竞价一字板和爆量数据

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

    # 获取全部A股代码
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
    stock_name_map = dict(zip(codes_list, names_list))

    # 过滤ST
    sid_list = [sid for sid in codes_list if "ST" not in stock_name_map.get(sid, "")]
    codes_str = ", ".join(sid_list)

    # 从 db_zt_reson 获取昨日涨停数据 (由 stat.py 采集写入)
    lszt_records = db.query(ZtReson).filter(ZtReson.cdate == lsdate).all()
    if not lszt_records:
        print(f"警告: db_zt_reson 中无 {lsdate} 的数据，请先运行 stat.py 采集昨日涨停数据")
    lszt_stocks = {}
    for rec in lszt_records:
        lszt_stocks[rec.stockid] = {"lbs": rec.lbs}

    # 获取竞价实时行情
    data_result = THS_RQ(
        codes_str,
        "bid1;ask1;changeRatio;upperLimit;downLimit;amount;volume;bidSize1;askSize1;tradeStatus;chg_5min",
        "", "format:json",
    )

    if data_result.errorcode != 0:
        return {"error": data_result.errmsg}

    jdata = json.loads(data_result.data.decode('gb18030'))

    zts = 0
    dts = 0
    ztfd = 0.0
    dtfd = 0.0
    jjbvol_list = []

    for item in jdata["tables"]:
        thscode = item["thscode"]
        thscoder = thscode.split(".")
        if thscoder[1] == "BJ":
            continue

        upper_limit = item["table"]["upperLimit"]
        down_limit = item["table"]["downLimit"]
        bid1 = item["table"]["bid1"]
        ask1 = item["table"]["ask1"]
        bid_size1 = item["table"]["bidSize1"]
        ask_size1 = item["table"]["askSize1"]
        amount = item["table"]["amount"]
        volume = item["table"]["volume"]
        chg_5min = item["table"]["chg_5min"]
        change_ratio = item["table"]["changeRatio"]
        trade_status = item["table"]["tradeStatus"]

        if trade_status[0] != "交易":
            continue

        # 统计涨停
        if bid1[0] == upper_limit[0]:
            zts += 1
            if bid1[0] is not None and bid_size1[0] is not None:
                ztfd += round(float(bid1[0]) * float(bid_size1[0]) * 100, 2)

        # 统计跌停
        if ask1[0] == down_limit[0]:
            dts += 1
            if ask1[0] is not None and ask_size1[0] is not None:
                dtfd += round(float(ask1[0]) * float(ask_size1[0]) * 100, 2)

        # 昨日涨停竞价爆量检测
        if thscode not in lszt_stocks:
            continue
        if change_ratio[0] < 5 or amount[0] < 10000000:
            continue

        # 获取昨日成交量
        data_lshq = THS_HQ(thscode, "volume,close,amount", "", yesterday_str, yesterday_str, "format:json")
        if data_lshq.errorcode != 0:
            continue

        hqdata = json.loads(data_lshq.data.decode('gb18030'))
        ls_volume = 0
        for hqs in hqdata["tables"]:
            ls_volume = hqs["table"]["volume"][0]

        if ls_volume == 0:
            continue
        vol_rate = round(volume[0] * 100 / ls_volume * 100, 2)
        if vol_rate < 8:
            continue

        lbs = lszt_stocks[thscode]["lbs"]
        status = f"{lbs}连板" if lbs > 1 else "首板"

        jjbvol_list.append({
            "stockid": thscode,
            "stockname": stock_name_map.get(thscode, ""),
            "zf": round(change_ratio[0], 2),
            "zs": round(chg_5min[0], 2),
            "volume": volume[0],
            "jje": round(amount[0] / 10000),
            "rate": vol_rate,
            "status": status,
        })

    # 写入竞价一字数据 (upsert)
    existing = db.query(Jjztdt).filter(Jjztdt.cdate == cdate).first()
    if existing:
        existing.zts = zts
        existing.ztfd = round(ztfd, 2)
        existing.dts = dts
        existing.dtfd = round(dtfd, 2)
    else:
        db.add(Jjztdt(cdate=cdate, zts=zts, ztfd=round(ztfd, 2), dts=dts, dtfd=round(dtfd, 2)))

    # 写入竞价爆量数据
    db.query(Jjbvol).filter(Jjbvol.cdate == cdate).delete()
    for bvol in jjbvol_list:
        db.add(Jjbvol(cdate=cdate, **bvol))

    db.commit()
    return {
        "date": cdate,
        "jjztdt": {"zts": zts, "ztfd": round(ztfd, 2), "dts": dts, "dtfd": round(dtfd, 2)},
        "jjbvol_count": len(jjbvol_list),
    }


if __name__ == "__main__":
    import sys
    from app.database import SessionLocal

    date_arg = sys.argv[1] if len(sys.argv) > 1 else datetime.today().strftime("%Y-%m-%d")
    trading_day = func.get_trading_day(date_arg)

    func.thslogin()
    db = SessionLocal()
    try:
        result = collect_bidding(trading_day, db)
        print(f"bidding 采集完成: {result}")
    finally:
        db.close()
        func.thslogout()
