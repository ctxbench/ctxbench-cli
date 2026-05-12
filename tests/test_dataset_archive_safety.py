from __future__ import annotations

from pathlib import Path
import io
import tarfile

import pytest

from ctxbench.dataset.archive import UnsafeArchiveError, safe_extract_tar_gz


def _build_tar_gz(
    entries: list[tuple[str, bytes | None, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as handle:
        for name, member_type, data in entries:
            info = tarfile.TarInfo(name=name)
            if member_type:
                info.type = member_type
            if info.isdir():
                handle.addfile(info)
                continue
            info.size = len(data)
            handle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("name", "member_type"),
    [
        ("../escape.txt", tarfile.REGTYPE),
        ("/absolute.txt", tarfile.REGTYPE),
        ("package/link", tarfile.SYMTYPE),
        ("package/hardlink", tarfile.LNKTYPE),
        ("package/fifo", tarfile.FIFOTYPE),
        ("package/device", tarfile.CHRTYPE),
    ],
)
def test_safe_extract_rejects_unsafe_members(
    tmp_path: Path,
    name: str,
    member_type: bytes,
) -> None:
    payload = _build_tar_gz([(name, member_type, b"unsafe")])

    with pytest.raises(UnsafeArchiveError):
        safe_extract_tar_gz(payload, tmp_path / "extract")


def test_safe_extract_writes_normal_archive(tmp_path: Path) -> None:
    payload = _build_tar_gz(
        [
            ("dataset/", tarfile.DIRTYPE, b""),
            ("dataset/ctxbench.dataset.json", tarfile.REGTYPE, b'{"id":"ctxbench/fake","version":"0.1.0"}'),
            ("dataset/data/example.txt", tarfile.REGTYPE, b"example"),
        ]
    )

    written = safe_extract_tar_gz(payload, tmp_path / "extract")

    assert sorted(path.relative_to(tmp_path / "extract").as_posix() for path in written) == [
        "dataset/ctxbench.dataset.json",
        "dataset/data/example.txt",
    ]
    assert (tmp_path / "extract" / "dataset" / "data" / "example.txt").read_text(encoding="utf-8") == "example"
