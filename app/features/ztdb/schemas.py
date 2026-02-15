from pydantic import BaseModel


class ZtdbItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    zhenfu: float | None = None
    declines: float | None = None

    class Config:
        from_attributes = True


class ZtdbListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[ZtdbItem]
