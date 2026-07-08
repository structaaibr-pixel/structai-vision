"""Camada fina sobre o MinIO (compatível com S3)."""
import io

from minio import Minio

from .config import settings

_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def ensure_bucket() -> None:
    if not _client.bucket_exists(settings.minio_bucket):
        _client.make_bucket(settings.minio_bucket)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    _client.put_object(settings.minio_bucket, key, io.BytesIO(data), len(data),
                       content_type=content_type)
    return key


def put_file(key: str, path: str) -> str:
    _client.fput_object(settings.minio_bucket, key, path)
    return key


def download_to(key: str, path: str) -> None:
    _client.fget_object(settings.minio_bucket, key, path)


def list_keys(prefix: str) -> list[str]:
    return [o.object_name for o in
            _client.list_objects(settings.minio_bucket, prefix=prefix, recursive=True)]
