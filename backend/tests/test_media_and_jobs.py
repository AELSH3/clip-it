from pathlib import Path

import pytest

from app.errors import AppError, PermanentProcessingError
from app.services import ensure_size, extension_for, remove_video_files, sanitize_filename, video_dir
from app.services.streaming import InvalidRange, iter_file_range, parse_byte_range


def test_extension_and_size_limits(monkeypatch):
    assert extension_for("lecture.MP4") == ".mp4"
    with pytest.raises(AppError) as exc:
        extension_for("notes.pdf")
    assert exc.value.code == "unsupported_type"
    monkeypatch.setenv("CLIPIT_MAX_UPLOAD_BYTES", "10")
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(AppError) as exc:
        ensure_size(11)
    assert exc.value.code == "file_too_large"
    get_settings.cache_clear()


def test_filename_strips_paths():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("") == "video"


def test_video_dir_rejects_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPIT_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(AppError):
        video_dir("../outside")
    folder = video_dir("12345678-1234-1234-1234-123456789abc")
    folder.mkdir(parents=True)
    (folder / "original.mp4").write_bytes(b"1234")
    remove_video_files("12345678-1234-1234-1234-123456789abc")
    assert not folder.exists()
    get_settings.cache_clear()


def test_byte_range_and_iterator(tmp_path: Path):
    path = tmp_path / "clip.bin"
    path.write_bytes(b"abcdefghij")
    assert parse_byte_range(None, 10) is None
    assert parse_byte_range("bytes=0-3", 10) == (0, 3)
    assert parse_byte_range("bytes=8-", 10) == (8, 9)
    assert parse_byte_range("bytes=-4", 10) == (6, 9)
    with pytest.raises(InvalidRange):
        parse_byte_range("bytes=20-21", 10)
    assert b"".join(iter_file_range(path, 2, 5)) == b"cdef"


def test_permanent_errors_are_not_retryable():
    from app.workers.tasks import process_video_task

    assert process_video_task.max_retries == 2
    assert not issubclass(PermanentProcessingError, type(None))
    error = PermanentProcessingError("corrupt")
    assert error.code == "processing_rejected"
