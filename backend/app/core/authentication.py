from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.services.jwt_service import InvalidAccessTokenError, JwtService

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = JwtService(get_settings()).decode_access_token(
            credentials.credentials
        )
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = UserRepository(db).get(claims.user_id)
    if (
        user is None
        or not user.is_active
        or user.username != claims.username
        or user.role.value != claims.role
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]



def require_super_power(user: CurrentUserDependency) -> User:
    if user.role.value != "SUPER_POWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilège SUPER_POWER requis.",
        )
    return user


SuperPowerDependency = Annotated[User, Depends(require_super_power)]

