# coding:utf-8
"""赚钱效应统计采集 — 原 python/stat.py 迁移
将 Redis 中间层替换为直接写入 Cloud SQL (SQLAlchemy)
"""
import json

from sqlalchemy.orm import Session

from app.collectors import func
from app.collectors.models import ZtReson
from app.features.effect.models import MoneyEffect

try:
    from iFinDPy import THS_WCQuery
except ImportError:
    THS_WCQuery = None


def collect_stat(cdate: str, db: Session) -> dict:
    """采集赚钱效应数据

    Args:
        cdate: 交易日 YYYYMMDD 格式
        db: SQLAlchemy Session

    Returns:
        统计信息
    """
    if THS_WCQuery is None:
        return {"error": "iFinDPy not available"}

    # 一字板数据
    yzdata_result = THS_WCQuery(
        cdate + " 去除ST以及北交所股票一字涨停板股票以及涨停封单金额",
        "stock", "format:json",
    )

    yzb_fd = 0.0
    yzb_num = 0
    if yzdata_result.errorcode == 0:
        jdata = json.loads(yzdata_result.data)
        for item in jdata["tables"]:
            ztfd_list = item["table"]["涨停封单额[" + cdate + "]"]
            ztfd_list = [float(x) for x in ztfd_list]
            yzb_fd = round(sum(ztfd_list) / 100000000, 2)
            yzb_num = len(ztfd_list)
    else:
        print(f"一字板查询失败: {yzdata_result.errmsg}")

    # 涨停板数据
    ztdata_result = THS_WCQuery(
        cdate + " 去除ST以及北交所股票 涨停板股票、成交金额、涨停原因、连续涨停天数",
        "stock", "format:json",
    )

    zt_cje = 0.0
    zt_num = 0
    lbs = 0
    maxlb = 1
    zt_details = []
    if ztdata_result.errorcode == 0:
        jdata = json.loads(ztdata_result.data)
        for item in jdata["tables"]:
            code_list = item["table"]["股票代码"]
            name_list = item["table"]["股票简称"]
            ztje_list = item["table"]["成交额[" + cdate + "]"]
            ztlb_list = item["table"]["连续涨停天数[" + cdate + "]"]
            # THS 返回字段名可能是 "涨停原因类别" 或 "涨停原因"
            reson_key = "涨停原因类别[" + cdate + "]"
            if reson_key not in item["table"]:
                reson_key = "涨停原因[" + cdate + "]"
            ztreson_list = item["table"].get(reson_key, [""] * len(code_list))
            ztje_list = [float(x) for x in ztje_list]
            zt_cje = round(sum(ztje_list) / 100000000, 2)
            zt_num = len(code_list)
            lbs = sum(1 for num in ztlb_list if num > 1)
            maxlb = max(ztlb_list) if ztlb_list else 1
            for k, code in enumerate(code_list):
                zt_details.append({
                    "stockid": code,
                    "stockname": name_list[k],
                    "cje": round(ztje_list[k] / 100000000, 2),
                    "lbs": int(ztlb_list[k]),
                    "reson": str(ztreson_list[k]) if ztreson_list[k] else "",
                })
    else:
        print(f"涨停板查询失败: {ztdata_result.errmsg}")

    # 写入涨停原因明细到 db_zt_reson (替代 Redis zhangting_reson_{date})
    db.query(ZtReson).filter(ZtReson.cdate == cdate).delete()
    for detail in zt_details:
        db.add(ZtReson(cdate=cdate, **detail))

    # 写入赚钱效应汇总 (upsert)
    existing = db.query(MoneyEffect).filter(MoneyEffect.cdate == cdate).first()
    if existing:
        existing.ztje = zt_cje
        existing.maxlb = maxlb
        existing.zts = zt_num
        existing.lbs = lbs
        existing.yzb = yzb_num
        existing.yzbfd = yzb_fd
        existing.dzfs = 0
    else:
        db.add(MoneyEffect(
            cdate=cdate,
            ztje=zt_cje,
            maxlb=maxlb,
            zts=zt_num,
            lbs=lbs,
            yzb=yzb_num,
            yzbfd=yzb_fd,
            dzfs=0,
        ))

    db.commit()
    return {
        "date": cdate,
        "ztje": zt_cje,
        "maxlb": maxlb,
        "zts": zt_num,
        "lbs": lbs,
        "yzb": yzb_num,
        "yzbfd": yzb_fd,
    }


if __name__ == "__main__":
    import sys
    from datetime import datetime
    from app.database import SessionLocal

    date_arg = sys.argv[1] if len(sys.argv) > 1 else datetime.today().strftime("%Y-%m-%d")
    cdate = func.get_trading_day(date_arg).replace("-", "")

    func.thslogin()
    db = SessionLocal()
    try:
        result = collect_stat(cdate, db)
        print(f"stat 采集完成: {result}")
    finally:
        db.close()
        func.thslogout()
