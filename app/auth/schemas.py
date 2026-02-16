from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    subscription_type: Optional[str] = None
    subscription_end: Optional[datetime] = None
    subscription_active: bool = False

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def compute_subscription_active(cls, data):
        if hasattr(data, "subscription_end"):
            end = data.subscription_end
            data = {c.key: getattr(data, c.key) for c in data.__table__.columns}
            data["subscription_active"] = end is not None and end > datetime.now()
        return data


class UserInfoAdmin(BaseModel):
    id: int
    username: str
    role: str
    password: str
    subscription_type: Optional[str] = None
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    subscription_active: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def compute_subscription_active(cls, data):
        if hasattr(data, "subscription_end"):
            end = data.subscription_end
            data = {c.key: getattr(data, c.key) for c in data.__table__.columns}
            data["subscription_active"] = end is not None and end > datetime.now()
        return data


class SubscriptionUpdate(BaseModel):
    subscription_type: str
