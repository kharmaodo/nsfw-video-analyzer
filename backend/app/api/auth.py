from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUserRead, LoginRequest, LoginResponse
from app.services.authentication_service import AuthenticationError, AuthenticationService
from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_authentication_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticationService:
    settings = get_settings()
    return AuthenticationService(
        UserRepository(db),
        PasswordService(rounds=settings.bcrypt_rounds),
        JwtService(settings),
    )


AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    service: AuthenticationServiceDependency,
) -> LoginResponse:
    try:
        result = service.authenticate(payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    settings = get_settings()
    return LoginResponse(
        access_token=result.access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=AuthenticatedUserRead(
            id=result.user.id,
            username=result.user.username,
            role=result.user.role,
        ),
    )

