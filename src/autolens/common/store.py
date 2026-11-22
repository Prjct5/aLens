from __future__ import annotations

import gzip
import json
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


class RawPayloadConflict(RuntimeError):
    """Raised when an immutable raw key would be overwritten with different content."""


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

    def ensure_buckets(self, buckets: tuple[str, ...] = BUCKETS) -> list[str]:
        """Create any missing bucket (dev and CI only; compose creates them with minio-init)."""
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        created = [b for b in buckets if b not in existing]
        for bucket in created:
            self._client.create_bucket(Bucket=bucket)
        return created

    def raw_key(self, source: str, run_date: str, source_listing_id: str) -> str:
        return f"{RAW}/{source}/{run_date}/{source_listing_id}.json.gz"

    @staticmethod
    def _split(key: str) -> tuple[str, str]:
        bucket, _, rest = key.partition("/")
        return bucket, rest

    def put_raw(
        self, source: str, run_date: str, source_listing_id: str, payload: dict[str, Any]
    ) -> str:
        """Store an immutable raw payload (gzip, byte-reproducible); returns its logical key."""
        key = self.raw_key(source, run_date, source_listing_id)
        bucket, rest = self._split(key)
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        if self.exists(bucket, rest):
            if gzip.decompress(self.get(bucket, rest)) != data:
                raise RawPayloadConflict(
                    f"raw payload {key} already exists with different content; "
                    "immutable raw objects must never be overwritten"
                )
            return key
        self.put(bucket, rest, gzip.compress(data, mtime=0), "application/gzip")
        return key

    def get_raw(self, key: str) -> dict[str, Any]:
        bucket, rest = self._split(key)
        payload: dict[str, Any] = json.loads(gzip.decompress(self.get(bucket, rest)))
        return payload

    def raw_keys(self, source: str | None = None, run_date: str | None = None) -> list[str]:
        prefix = f"{source}/" if source else ""
        if source and run_date:
            prefix = f"{source}/{run_date}/"
        keys = [f"{RAW}/{o['Key']}" for o in self.list_objects(RAW, prefix)]
        if run_date and not source:
            keys = [k for k in keys if f"/{run_date}/" in k]
        return keys
