"""Test setup: a real Postgres (DB_* env vars) and locally signed Cognito-style tokens."""
import os
import time

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_NAME", "test_judging")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_SSLMODE", "disable")
os.environ.setdefault("COGNITO_USER_POOL_ID", "ap-south-1_TestPool")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import get_settings
from app.core.db import Base, get_engine

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(sub="user-1", groups=("participants",), token_use="access", client_id=None, exp_in=3600, key=_KEY):
    now = int(time.time())
    claims = {
        "sub": sub,
        "cognito:groups": list(groups),
        "iss": get_settings().cognito_issuer,
        "client_id": client_id or get_settings().cognito_app_client_id,
        "token_use": token_use,
        "iat": now,
        "exp": now + exp_in,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def bearer(**kwargs) -> dict:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}


@pytest.fixture(autouse=True)
def _fake_jwks(monkeypatch):
    monkeypatch.setattr(auth, "_get_signing_key", lambda token: _KEY.public_key())


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        engine = get_engine()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield c
