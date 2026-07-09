from typing import Literal

import boto3
from botocore.config import Config
from redis import Redis
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import create_database_engine

CheckValue = Literal["ok", "failed", "skipped"]


def check_readiness(settings: Settings) -> dict[str, object]:
    if not settings.check_dependencies:
        return {
            "status": "ok",
            "checks": {
                "database": "skipped",
                "redis": "skipped",
                "minio": "skipped",
            },
        }

    checks = {
        "database": _check_database(settings),
        "redis": _check_redis(settings),
        "minio": _check_minio(settings),
    }
    status = "ok" if all(value == "ok" for value in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


def _check_database(settings: Settings) -> CheckValue:
    try:
        engine = create_database_engine(settings)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        engine.dispose()
        return "ok"
    except Exception:
        return "failed"


def _check_redis(settings: Settings) -> CheckValue:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        client.close()
        return "ok"
    except Exception:
        return "failed"


def _check_minio(settings: Settings) -> CheckValue:
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key.get_secret_value(),
            region_name=settings.minio_region,
            config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
        )
        client.head_bucket(Bucket=settings.minio_bucket)
        return "ok"
    except Exception:
        return "failed"

