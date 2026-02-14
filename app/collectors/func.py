# coding:utf-8
from datetime import datetime, timedelta

import pandas as pd
from pandas.tseries.offsets import BDay

try:
    from iFinDPy import THS_iFinDLogin, THS_iFinDLogout
except ImportError:
    THS_iFinDLogin = None
    THS_iFinDLogout = None

from app.config import get_settings


def get_previous_trading_day(date: str) -> str:
    """获取上一个交易日 (格式 YYYY-MM-DD)"""
    d = pd.to_datetime(date)
    previous = d - BDay(1)
    tdate = previous.strftime("%Y-%m-%d")
    if is_trading_day(tdate):
        return tdate
    return get_previous_trading_day(tdate)


def get_next_trading_day(date: str) -> str:
    """获取下一个交易日"""
    d = datetime.strptime(date, "%Y-%m-%d").date()
    next_day = d + timedelta(days=1)
    tdate = next_day.strftime("%Y-%m-%d")
    if is_trading_day(tdate):
        return tdate
    return get_next_trading_day(tdate)


def get_trading_day(cdate: str) -> str:
    """获取当前最近的一个交易日 (往前推算)"""
    if is_trading_day(cdate):
        return cdate
    return get_previous_trading_day(cdate)


def is_trading_day(cdate: str) -> bool:
    """判断是否为交易日"""
    wdate = datetime.strptime(cdate, "%Y-%m-%d").date()
    if wdate.weekday() >= 5:
        return False
    if is_holiday(cdate):
        return False
    return True


def is_holiday(cdate: str) -> bool:
    date_parts = cdate.split("-")
    cyear = date_parts[0]
    holidays = get_holiday(cyear)
    return cdate in holidays


def get_holiday(year) -> list[str]:
    year = int(year)
    holiday = {
        2025: [
            "2025-01-01",
            "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
            "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04",
            "2025-04-04", "2025-04-05", "2025-04-06",
            "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
            "2025-05-31", "2025-06-01", "2025-06-02",
            "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04",
            "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",
        ],
        2026: [
            "2026-01-01", "2026-01-02",
            "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19",
            "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",
            "2026-04-04", "2026-04-05", "2026-04-06",
            "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
            "2026-06-19", "2026-06-20", "2026-06-21",
            "2026-09-25", "2026-09-26", "2026-09-27",
            "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
            "2026-10-05", "2026-10-06", "2026-10-07",
        ],
    }
    return holiday.get(year, [])


def thslogin():
    """登录同花顺"""
    if THS_iFinDLogin is None:
        print("iFinDPy not available, skipping THS login")
        return
    settings = get_settings()
    result = THS_iFinDLogin(settings.THS_USERNAME, settings.THS_PASSWORD)
    if result in {0, -201}:
        print("THS 登录成功")
    else:
        print(f"THS 登录失败: {result}")


def thslogout():
    """退出登录同花顺"""
    if THS_iFinDLogout is None:
        return
    THS_iFinDLogout()
