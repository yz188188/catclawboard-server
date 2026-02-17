# coding:utf-8
from sqlalchemy import Column, Integer, String, DECIMAL, UniqueConstraint

from app.database import Base


class Lianban(Base):
    __tablename__ = "db_lianban"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    lbs = Column(Integer, default=0)
    scores = Column(DECIMAL(10, 2))
    times = Column(String(4))
    bzf = Column(DECIMAL(10, 2))
    cje = Column(DECIMAL(15, 2))
    rates = Column(DECIMAL(10, 2))
    ozf = Column(DECIMAL(10, 2))
    zhenfu = Column(DECIMAL(10, 2))
    chg_1min = Column(DECIMAL(10, 2))
    zs_times = Column(DECIMAL(3, 1))
    tms = Column(String(5))
    lastzf = Column(DECIMAL(10, 2))

    __table_args__ = (
        UniqueConstraint("cdate", "stockid", name="uk_lianban_cdate_stockid"),
    )
