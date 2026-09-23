"""
Document storage abstraction.

Two backends implement the same operations:

* ``minio`` - S3-compatible object storage, used by the docker-compose stack.
* ``local`` - plain files under ``settings.local_storage_path``, so the
  Knowledge tab works on a machine with no Docker and no object store.

Selected with ``STORAGE_BACKEND``. The ``minio`` package is imported lazily so
the local backend runs without it installed.
"""

from pathlib import Path

from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

_minio_client = None


def get_minio_client():
    """
    Get or create the MinIO client singleton.

    @returns Minio client instance
    """
    global _minio_client
    if _minio_client is None:
        from minio import Minio

        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _minio_client


def _local_root() -> Path:
    """
    Resolve and create the local storage root.

    @returns Absolute path to the local storage root
    """
    root = Path(settings.local_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _local_path(object_key: str) -> Path:
    """
    Map an object key onto a path inside the local storage root, refusing
    keys that would escape it.

    @param object_key: Storage object key, e.g. "<facility>/<uuid>.pdf"
    @returns Absolute path for the object
    """
    root = _local_root().resolve()
    candidate = (root / object_key.replace("\\", "/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Unsafe storage key: {object_key}")
    return candidate


def ensure_bucket() -> None:
    """
    Prepare the backing store: the MinIO bucket, or the local directory.
    """
    if settings.storage_backend == "minio":
        client = get_minio_client()
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
            logger.info("minio_bucket_created", bucket=settings.minio_bucket)
        return

    root = _local_root()
    logger.info("local_storage_ready", path=str(root))


def put_file(file_path: str, object_key: str, content_type: str) -> None:
    """
    Store a file.

    @param file_path: Local path of the file to store
    @param object_key: Destination object key
    @param content_type: MIME type (recorded by MinIO, ignored locally)
    """
    if settings.storage_backend == "minio":
        client = get_minio_client()
        client.fput_object(
            settings.minio_bucket,
            object_key,
            file_path,
            content_type=content_type,
        )
    else:
        destination = _local_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(file_path).read_bytes())

    logger.info("file_stored", backend=settings.storage_backend, key=object_key)


def get_file(object_key: str, dest_path: str) -> None:
    """
    Copy a stored file back to a local path.

    @param object_key: Source object key
    @param dest_path: Local destination path
    """
    if settings.storage_backend == "minio":
        client = get_minio_client()
        client.fget_object(settings.minio_bucket, object_key, dest_path)
    else:
        source = _local_path(object_key)
        Path(dest_path).write_bytes(source.read_bytes())


def delete_file(object_key: str) -> None:
    """
    Remove a stored object.

    @param object_key: Object key to remove
    """
    if settings.storage_backend == "minio":
        client = get_minio_client()
        client.remove_object(settings.minio_bucket, object_key)
    else:
        target = _local_path(object_key)
        if target.exists():
            target.unlink()

    logger.info("file_deleted", backend=settings.storage_backend, key=object_key)


def health() -> str:
    """
    Check storage connectivity.

    @returns Status string: 'connected' or 'disconnected'
    """
    try:
        if settings.storage_backend == "minio":
            get_minio_client().list_buckets()
        else:
            _local_root()
        return "connected"
    except Exception:
        return "disconnected"