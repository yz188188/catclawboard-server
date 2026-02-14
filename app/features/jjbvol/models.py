from sqlalchemy import Column, Integer, String, DECIMAL, BigInteger

from app.database import Base


class Jjbvol(Base):
    __tablename__ = "db_zrzt_jjvol"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    zf = Column(DECIMAL(10, 2))
    zs = Column(DECIMAL(10, 2))
    volume = Column(BigInteger, default=0)
    jje = Column(DECIMAL(15, 2), default=0)
    rate = Column(DECIMAL(10, 2), default=0)
    status = Column(String(20))
