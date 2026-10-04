"""Runtime settings, read once from environment variables."""
import os
from dataclasses import dataclass, field
from functools import lru_cache


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    db_host: str = field(default_factory=lambda: _required("DB_HOST"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "postgres"))
    db_user: str = field(default_factory=lambda: _required("DB_USER"))
    db_password: str = field(default_factory=lambda: _required("DB_PASSWORD"))
    db_sslmode: str = field(default_factory=lambda: os.getenv("DB_SSLMODE", "require"))
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-south-1"))
    cognito_region: str = field(
        default_factory=lambda: os.getenv("COGNITO_REGION", os.getenv("AWS_REGION", "ap-south-1"))
    )
    cognito_user_pool_id: str = field(default_factory=lambda: _required("COGNITO_USER_POOL_ID"))
    cognito_app_client_id: str = field(default_factory=lambda: _required("COGNITO_APP_CLIENT_ID"))

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
