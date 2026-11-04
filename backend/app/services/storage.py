"""Stream uploads to disk with a size cap and content hash. Stored under random names, outside any web root."""

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

CHUNK = 1024 * 1024


class UploadTooLarge(Exception):
    pass


def storage_root() -> Path:
    root = Path(get_settings().storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_upload(file: UploadFile) -> tuple[Path, int, str]:
    """Return (path, size, sha256). Raises UploadTooLarge and removes the partial file."""
    limit = get_settings().max_file_mb * 1024 * 1024
    path = storage_root() / f"{uuid.uuid4().hex}.bin"
    sha, size = hashlib.sha256(), 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise UploadTooLarge(f"File exceeds {get_settings().max_file_mb} MB")
                sha.update(chunk)
                out.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, size, sha.hexdigest()


def safe_display_name(name: str | None) -> str:
    """Original filename for display only: no path parts, no control characters."""
    base = os.path.basename((name or "upload").replace("\\", "/"))
    clean = "".join(c for c in base if c.isprintable()).strip()
    return (clean or "upload")[:255]
