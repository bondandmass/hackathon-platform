"""Cognito access-token validation and group checks."""
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import get_settings

_jwks_client: jwt.PyJWKClient | None = None


@dataclass(frozen=True)
class User:
    sub: str
    groups: frozenset[str]
    token: str

    @property
    def is_judge(self) -> bool:
        return "judges" in self.groups

    @property
    def is_participant(self) -> bool:
        return "participants" in self.groups


def _get_signing_key(token: str):
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{get_settings().cognito_issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
            timeout=5,
        )
    return _jwks_client.get_signing_key_from_jwt(token).key


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    settings = get_settings()
    try:
        key = _get_signing_key(token)
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Cannot reach Cognito") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc
    try:
        # Access tokens carry client_id instead of aud, so aud is checked by hand below.
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={"require": ["exp", "iat", "iss", "sub", "token_use"], "verify_aud": False},
            leeway=30,
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc
    if claims.get("token_use") != "access":
        raise _unauthorized("Access token required")
    if claims.get("client_id") != settings.cognito_app_client_id:
        raise _unauthorized("Token issued for another client")
    return User(sub=claims["sub"], groups=frozenset(claims.get("cognito:groups", [])), token=token)


def require_group(*groups: str):
    allowed = set(groups)

    def checker(user: User = Depends(get_current_user)) -> User:
        if not allowed & user.groups:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires group: {' or '.join(sorted(allowed))}")
        return user

    return checker
