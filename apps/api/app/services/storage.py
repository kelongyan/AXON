from urllib.parse import urlparse

import boto3

from app.core.config import Settings


class MinioObjectStore:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
    ) -> None:
        self.bucket = bucket
        use_ssl = urlparse(endpoint_url).scheme == "https"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=use_ssl,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "MinioObjectStore":
        return cls(
            endpoint_url=settings.minio_endpoint_url,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key.get_secret_value(),
            bucket=settings.minio_bucket,
            region=settings.minio_region,
        )

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
