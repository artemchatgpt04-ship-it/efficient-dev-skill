"""Content fingerprints for cache and change validation."""

from __future__ import annotations

import hashlib
from pathlib import Path


FINGERPRINT_ALGORITHM = "sha256"
DEFAULT_CHUNK_SIZE = 64 * 1024


def fingerprint_file(path: str | Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Hash file bytes deterministically without relying on timestamps."""

    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return f"{FINGERPRINT_ALGORITHM}:{digest.hexdigest()}"
