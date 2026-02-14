from decimal import Decimal
from pydantic import BaseModel


class JjztdtItem(BaseModel):
    id: int
    cdate: str
    zts: int = 0
    ztfd: Decimal = Decimal("0")
    dts: int = 0
    dtfd: Decimal = Decimal("0")

    class Config:
        from_attributes = True


class JjztdtListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[JjztdtItem]
