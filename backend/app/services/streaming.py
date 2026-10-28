from pathlib import Path


class InvalidRange(ValueError):
    pass


def parse_byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    if header is None or header == "":
        return None
    if not header.startswith("bytes="):
        raise InvalidRange("range unit must be bytes")
    spec = header.removeprefix("bytes=").split(",", 1)[0].strip()
    if "-" not in spec:
        raise InvalidRange("range is missing a hyphen")
    start_text, end_text = spec.split("-", 1)
    if start_text == "":
        length = int(end_text)
        if length <= 0:
            raise InvalidRange("suffix length must be positive")
        start = max(0, size - length)
        end = size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    if start < 0 or start >= size or end < start:
        raise InvalidRange("range is outside the file")
    return start, min(end, size - 1)


def iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
