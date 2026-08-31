from pydantic import BaseModel, Field, model_validator

from app.db.models import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class AuthenticatedUserRead(BaseModel):
    id: int
    username: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUserRead



class OAuthProviderRead(BaseModel):
    provider: str



class OAuthExchangeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=512)



class AccountUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    username: str | None = Field(default=None, min_length=1, max_length=100)
    new_password: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def requires_a_change(self) -> "AccountUpdateRequest":
        if self.username is None and self.new_password is None:
            raise ValueError(
                "username ou new_password doit être renseigné."
            )
        return self

