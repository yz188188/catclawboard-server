# coding:utf-8
"""自动定时采集调度器

采集时间表（交易日）:
  9:26      - bidding        竞价数据（一次）
  9:30-9:46 - mighty         强势反包实时监控（内含循环，启动一次）
  15:05     - stat           涨停统计（一次）
  15:08     - thsdata        涨停反包 + 大额成交（收盘后全天数据）
  15:15     - mighty_close   更新收盘涨幅（一次）

注意: thsdata 必须在收盘后执行，因为 THS_RQ 获取实时行情，
盘中 high/low/amount 不完整，导致振幅和成交额筛选不准确。

用法:
  python -m app.collectors.scheduler              正常调度模式（常驻进程）
  python -m app.collectors.scheduler --now         立即执行所有任务（测试/补采）
  python -m app.collectors.scheduler --task <name>  执行单个任务（供 Windows 任务计划程序调用）
"""
import os
import sys
import time
from datetime import datetime, timedelta

from app.collectors import func
from app.collectors.stat import collect_stat
from app.collectors.thsdata import collect_ztdb, backfill_large_amount
from app.collectors.bidding import collect_bidding
from app.collectors.mighty import collect_mighty, update_close_price
from app.collectors.lianban import collect_lianban, update_close_price as lianban_update_close
from app.collectors.jjmighty import collect_jjmighty, update_close_price as jjmighty_update_close
from app.collectors.models import ZtReson
from app.features.mighty.models import LargeAmount
from app.database import SessionLocal

# 日志文件路径
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
_log_file = None


def setup_logging(task_name: str = None):
    """初始化日志文件输出（追加模式）

    Args:
        task_name: 任务名称，指定时日志写入 logs/<task_name>_YYYYMMDD.log
                   未指定时写入 logs/scheduler_YYYYMMDD.log
    """
    global _log_file
    os.makedirs(LOG_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    prefix = task_name if task_name else "scheduler"
    log_file_path = os.path.join(LOG_DIR, f"{prefix}_{date_str}.log")
    _log_file = open(log_file_path, "a", encoding="utf-8")


def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()


def run_task(name: str, task_fn):
    """执行单个采集任务，返回是否成功"""
    log(f"执行 {name}...")
    db = SessionLocal()
    try:
        result = task_fn(db)
        log(f"{name} 完成: {result}")
        return True
    except Exception as e:
        log(f"{name} 失败: {e}")
        return False
    finally:
        db.close()


def run_bidding(trading_day: str, db):
    return collect_bidding(trading_day, db)


def run_thsdata(trading_day: str, db):
    return collect_ztdb(trading_day, db)


def run_stat(cdate: str, db):
    return collect_stat(cdate, db)


def run_mighty(trading_day: str, db):
    return collect_mighty(trading_day, db)


def run_mighty_close(trading_day: str, db):
    return update_close_price(trading_day, db)


def run_lianban(trading_day: str, db):
    return collect_lianban(trading_day, db)


def run_lianban_close(trading_day: str, db):
    return lianban_update_close(trading_day, db)


def run_jjmighty(trading_day: str, db):
    return collect_jjmighty(trading_day, db)


def run_jjmighty_close(trading_day: str, db):
    return jjmighty_update_close(trading_day, db)


def seconds_until(hour: int, minute: int) -> float:
    """计算距离今天指定时间的秒数，如果已过则返回负数"""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (target - now).total_seconds()


def sleep_until_tomorrow():
    """睡眠到明天 9:20"""
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=20, second=0, microsecond=0)
    secs = (tomorrow - now).total_seconds()
    log(f"等待下一个交易日... ({round(secs / 3600, 1)} 小时后)")
    time.sleep(max(secs, 60))


def ensure_previous_day_data(trading_day: str):
    """检查并补采前一交易日的 db_zt_reson 和 db_large_amount 数据

    早盘任务（bidding/mighty/lianban/jjmighty）依赖前一交易日下午写入的
    涨停原因和大额成交数据。首次运行或前一天采集失败时需自动补采。

    Args:
        trading_day: 当前交易日 YYYY-MM-DD 格式
    """
    yesterday_str = func.get_previous_trading_day(trading_day)
    yesterday_cdate = yesterday_str.replace("-", "")

    db = SessionLocal()
    try:
        # 检查 db_zt_reson
        zt_count = db.query(ZtReson).filter(ZtReson.cdate == yesterday_cdate).count()
        if zt_count == 0:
            log(f"补采前一交易日 {yesterday_cdate} 涨停原因数据...")
            result = collect_stat(yesterday_cdate, db)
            log(f"补采 stat 完成: {result}")

        # 检查 db_large_amount
        la_count = db.query(LargeAmount).filter(LargeAmount.cdate == yesterday_cdate).count()
        if la_count == 0:
            log(f"补采前一交易日 {yesterday_cdate} 大额成交数据...")
            result = backfill_large_amount(yesterday_cdate, db)
            log(f"补采 large_amount 完成: {result}")

        if zt_count > 0 and la_count > 0:
            log(f"前一交易日 {yesterday_cdate} 数据完整，无需补采")
    except Exception as e:
        log(f"补采前一交易日数据失败: {e}")
    finally:
        db.close()


def run_single_task(name: str):
    """执行单个采集任务（供 Windows 任务计划程序调用）

    成功退出码 0，失败退出码 1，便于 Task Scheduler 判断结果。
    """
    setup_logging(task_name=name)
    today = datetime.now().strftime("%Y-%m-%d")
    if not func.is_trading_day(today):
        log(f"{today} 非交易日，跳过")
        sys.exit(0)

    trading_day = today
    cdate = trading_day.replace("-", "")

    tasks = {
        "bidding": lambda db: run_bidding(trading_day, db),
        "thsdata": lambda db: run_thsdata(trading_day, db),
        "stat": lambda db: run_stat(cdate, db),
        "mighty": lambda db: run_mighty(trading_day, db),
        "mighty_close": lambda db: run_mighty_close(trading_day, db),
        "lianban": lambda db: run_lianban(trading_day, db),
        "lianban_close": lambda db: run_lianban_close(trading_day, db),
        "jjmighty": lambda db: run_jjmighty(trading_day, db),
        "jjmighty_close": lambda db: run_jjmighty_close(trading_day, db),
    }

    if name not in tasks:
        log(f"未知任务: {name}，可选: {', '.join(tasks)}")
        sys.exit(1)

    log(f"定时任务模式，执行 {name}，交易日: {trading_day}")
    func.thslogin()
    try:
        # 早盘任务需要前一交易日数据
        if name in ("bidding", "mighty", "lianban", "jjmighty"):
            ensure_previous_day_data(trading_day)
        success = run_task(name, tasks[name])
    finally:
        func.thslogout()
        log(f"任务 {name} 结束")

    sys.exit(0 if success else 1)


def main():
    setup_logging()
    log("调度器启动，登录 THS...")
    func.thslogin()

    try:
        while True:
            today = datetime.now().strftime("%Y-%m-%d")

            # 非交易日直接跳过
            if not func.is_trading_day(today):
                log(f"{today} 非交易日，跳过")
                sleep_until_tomorrow()
                continue

            trading_day = today
            cdate = trading_day.replace("-", "")
            done = set()  # 记录今天已完成的一次性任务

            log(f"交易日 {today}，等待采集时间...")

            while datetime.now().strftime("%Y-%m-%d") == today:
                now = datetime.now()
                hm = now.hour * 100 + now.minute  # 如 925, 930, 1505

                # 9:20+ 补采前一交易日数据（早盘首个任务前）
                if hm >= 920 and "backfill" not in done:
                    ensure_previous_day_data(trading_day)
                    done.add("backfill")

                # 9:26 执行 bidding（一次）
                if hm >= 926 and "bidding" not in done:
                    run_task("bidding", lambda db: run_bidding(trading_day, db))
                    done.add("bidding")

                # 9:30 启动实时监控（mighty/lianban/jjmighty 各含循环到 9:46 自动退出）
                elif hm >= 930 and "mighty" not in done:
                    run_task("lianban", lambda db: run_lianban(trading_day, db))
                    done.add("lianban")
                    run_task("jjmighty", lambda db: run_jjmighty(trading_day, db))
                    done.add("jjmighty")
                    run_task("mighty", lambda db: run_mighty(trading_day, db))
                    done.add("mighty")

                # 15:05 执行 stat（一次）
                elif hm >= 1505 and "stat" not in done:
                    run_task("stat", lambda db: run_stat(cdate, db))
                    done.add("stat")

                # 15:08 执行 thsdata 涨停反包（收盘后全天数据）
                elif hm >= 1508 and "thsdata" not in done:
                    run_task("thsdata", lambda db: run_thsdata(trading_day, db))
                    done.add("thsdata")

                # 15:15 执行收盘更新（mighty/lianban/jjmighty）
                elif hm >= 1515 and "mighty_close" not in done:
                    run_task("mighty_close", lambda db: run_mighty_close(trading_day, db))
                    done.add("mighty_close")
                    run_task("lianban_close", lambda db: run_lianban_close(trading_day, db))
                    done.add("lianban_close")
                    run_task("jjmighty_close", lambda db: run_jjmighty_close(trading_day, db))
                    done.add("jjmighty_close")
                    log("今日采集全部完成")
                    sleep_until_tomorrow()
                    break

                time.sleep(30)

    except KeyboardInterrupt:
        log("收到中断信号，退出...")
    finally:
        func.thslogout()
        log("已登出 THS，调度器结束")


def run_all_now():
    """立即执行所有采集任务（测试/手动补采用）"""
    setup_logging()
    today = datetime.now().strftime("%Y-%m-%d")
    trading_day = func.get_trading_day(today)
    cdate = trading_day.replace("-", "")

    log(f"立即执行模式，交易日: {trading_day}")
    func.thslogin()
    try:
        ensure_previous_day_data(trading_day)
        run_task("bidding", lambda db: run_bidding(trading_day, db))
        run_task("stat", lambda db: run_stat(cdate, db))
        run_task("thsdata", lambda db: run_thsdata(trading_day, db))
        run_task("mighty_close", lambda db: run_mighty_close(trading_day, db))
        run_task("lianban_close", lambda db: run_lianban_close(trading_day, db))
        run_task("jjmighty_close", lambda db: run_jjmighty_close(trading_day, db))
        log("全部任务执行完成")
    finally:
        func.thslogout()


if __name__ == "__main__":
    if "--now" in sys.argv:
        run_all_now()
    elif "--task" in sys.argv:
        idx = sys.argv.index("--task")
        task_name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        if task_name:
            run_single_task(task_name)
        else:
            print("用法: python -m app.collectors.scheduler --task <bidding|thsdata|stat|mighty|mighty_close>")
    else:
        main()
