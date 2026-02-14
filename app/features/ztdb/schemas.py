from decimal import Decimal
from pydantic import BaseModel


class ZtdbItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    zhenfu: Decimal | None = None
    declines: Decimal | None = None

    class Config:
        from_attributes = True


class ZtdbListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[ZtdbItem]
