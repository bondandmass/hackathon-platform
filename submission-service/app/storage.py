"""S3 access. Credentials come from the pod's identity (no keys in code or env)."""
import os
from functools import lru_cache

import boto3
from botocore.config import Config

from .core.config import get_settings

URL_EXPIRY_SECONDS = 900


def bucket() -> str:
    name = os.getenv("S3_BUCKET", "").strip()
    if not name:
        raise RuntimeError("Missing required environment variable: S3_BUCKET")
    return name


@lru_cache
def s3():
    region = get_settings().aws_region
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def upload(fileobj, key: str, content_type: str) -> None:
    s3().upload_fileobj(fileobj, bucket(), key, ExtraArgs={"ContentType": content_type})


def delete(key: str) -> None:
    s3().delete_object(Bucket=bucket(), Key=key)


def download_url(key: str, filename: str) -> str:
    return s3().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket(),
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=URL_EXPIRY_SECONDS,
    )
