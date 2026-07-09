"""MinIO/S3 storage utilities."""
from __future__ import annotations

async def ensure_bucket_exists() -> None:
    """Create the MinIO bucket if it doesn't exist."""
    from config.settings import get_settings
    import asyncio
    settings = get_settings()
    try:
        from minio import Minio
        client = Minio(
            settings.minio.endpoint,
            access_key=settings.minio.access_key.get_secret_value(),
            secret_key=settings.minio.secret_key.get_secret_value(),
            secure=settings.minio.secure,
        )
        def _sync():
            if not client.bucket_exists(settings.minio.bucket_name):
                client.make_bucket(settings.minio.bucket_name)
        await asyncio.get_event_loop().run_in_executor(None, _sync)
    except Exception:
        pass  # non-fatal on startup
