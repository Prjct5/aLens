from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from autolens.common.config import Settings, get_settings

RAW = "raw"
QUARANTINE = "quarantine"
IMAGES = "images"
MLFLOW = "mlflow"
EXPORTS = "exports"
BUCKETS = (RAW, QUARANTINE, IMAGES, MLFLOW, EXPORTS)


class ObjectStore:
    def __init__(self, settings: Settings | None = None, client: Any = None) -> None:
        s = settings or get_settings()
        self._client = client or boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def put(self, bucket: str, key: str, data: bytes, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=bucket, Key=key, Body=data, **extra)

    def get(self, bucket: str, key: str) -> bytes:
        body: bytes = self._client.get_object(Bucket=bucket, Key=key)["Body"].read()
        return body

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def delete(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def list_objects(self, bucket: str, prefix: str = "") -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            out.extend(page.get("Contents", []))
        return out

    def count_older_than(self, bucket: str, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return sum(1 for o in self.list_objects(bucket) if o["LastModified"] < cutoff)

    def lifecycle_rules(self, bucket: str) -> list[dict[str, Any]]:
        try:
            rules: list[dict[str, Any]] = self._client.get_bucket_lifecycle_configuration(
                Bucket=bucket
            ).get("Rules", [])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchLifecycleConfiguration":
                return []
            raise
        return rules
