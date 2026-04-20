"""Minimal R2 (S3-compatible) client for Parquet snapshot storage."""

import boto3

from polybot.config import Settings


class R2Client:
    def __init__(self, settings: Settings):
        self._bucket = settings.R2_BUCKET_NAME
        self._s3 = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

    def upload_bytes(self, key: str, data: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)

    def upload_parquet(self, key: str, data: bytes) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def list_keys(self, prefix: str = "") -> list[str]:
        response = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        if "Contents" not in response:
            return []
        return [obj["Key"] for obj in response["Contents"]]

    def delete_object(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)
