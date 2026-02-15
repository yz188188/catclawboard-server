from pydantic import BaseModel


class JjbvolItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    zf: float | None = None
    zs: float | None = None
    volume: int = 0
    jje: float = 0
    rate: float = 0
    status: str | None = None

    class Config:
        from_attributes = True


class JjbvolListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[JjbvolItem]
