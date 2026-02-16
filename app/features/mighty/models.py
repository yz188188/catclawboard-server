# coding:utf-8
from sqlalchemy import Column, Integer, String, DECIMAL, UniqueConstraint

from app.database import Base


class LargeAmount(Base):
    __tablename__ = "db_large_amount"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    amount = Column(DECIMAL(20, 2), default=0)

    __table_args__ = (
        UniqueConstraint("cdate", "stockid", name="uk_la_cdate_stockid"),
    )


class Mighty(Base):
    __tablename__ = "db_mighty"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    scores = Column(DECIMAL(10, 2))
    times = Column(String(4))
    bzf = Column(DECIMAL(10, 2))
    cje = Column(DECIMAL(15, 2))
    rates = Column(DECIMAL(10, 2))
    ozf = Column(DECIMAL(10, 2))
    tms = Column(String(5))
    lastzf = Column(DECIMAL(10, 2))

    __table_args__ = (
        UniqueConstraint("cdate", "stockid", name="uk_mighty_cdate_stockid"),
    )
