"""Persistence utility helpers."""

import json
import os
from pathlib import Path
from uuid import uuid4


def write_json_atomic(
    file_path: Path,
    data: object,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Write JSON atomically using tmp + fsync + replace."""
    target_path = Path(file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = target_path.with_name(f".{target_path.name}.tmp-{uuid4().hex}")

    try:
        with open(temp_path, "w", encoding="utf-8") as temp_file:
            json.dump(data, temp_file, indent=indent, ensure_ascii=ensure_ascii)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        temp_path.replace(target_path)

        try:
            dir_fd = os.open(str(target_path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
