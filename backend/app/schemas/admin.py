from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import UserRole


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    role: UserRole = UserRole.GUEST


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def requires_a_change(self) -> "AdminUserUpdate":
        if self.role is None and self.is_active is None:
            raise ValueError("role ou is_active doit être renseigné.")
        return self


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRead]
    page: int
    size: int
    total: int
    pages: int

