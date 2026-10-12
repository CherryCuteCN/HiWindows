"""文件系统抽象与 Windows 后端实现。"""

from __future__ import annotations

import shutil
import stat
from importlib import import_module
from pathlib import Path
from typing import Any

from core.models.event import EventPublisher

from .exceptions import BackendUnavailableError
from .models.backend import IOBackend
from .models.events import IOEventType
from .models.filesystem import (
    FileSystem,
    FileSystemProgress,
    FileSystemProgressCallback,
    PathLike,
)


class _FileSystemBackend(IOBackend, FileSystem):
    """文件系统实现共享的非抽象能力。"""

    def read_bytes(self, path: PathLike) -> bytes:
        """读取文件的原始字节，由具体实现提供。"""
        raise NotImplementedError

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        """写入文件的原始字节，由具体实现提供。"""
        raise NotImplementedError

    def read_text(
        self,
        path: PathLike,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> str:
        """按指定编码读取文本文件。"""
        return self.read_bytes(path).decode(encoding, errors)

    def write_text(
        self,
        path: PathLike,
        data: str,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
    ) -> None:
        """按指定编码覆盖写入文本文件。"""
        self.write_bytes(path, data.encode(encoding, errors))

    def remove_tree(
        self,
        path: PathLike,
        *,
        on_progress: FileSystemProgressCallback | None = None,
    ) -> None:
        """递归删除路径，并按删除项目逐项报告进度。"""
        root = Path(path)
        if not self.exists(root):
            return

        total_items = self._count_tree(root)
        completed_items = 0

        def remove(current_path: Path) -> None:
            nonlocal completed_items
            if self.is_dir(current_path):
                for child in self.list_dir(current_path):
                    remove(child)
                self.remove_dir(current_path)
            else:
                self.remove_file(current_path)
            completed_items += 1
            if on_progress is not None:
                on_progress(
                    FileSystemProgress(
                        operation="remove_tree",
                        current_path=current_path,
                        completed_items=completed_items,
                        total_items=total_items,
                    )
                )

        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_tree",
            str(root),
        ):
            remove(root)

    def _count_tree(self, path: Path) -> int:
        if not self.is_dir(path):
            return 1
        return 1 + sum(self._count_tree(child) for child in self.list_dir(path))


class PathFileSystem(_FileSystemBackend):
    """基于 Python 标准库的文件系统实现。

    该实现用于跨平台测试和不需要 Windows 特有语义的场景。
    """

    def exists(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "exists", str(path)):
            return Path(path).exists()

    def is_file(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "is_file", str(path)):
            return Path(path).is_file()

    def is_dir(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "is_dir", str(path)):
            path_object = Path(path)
            return path_object.is_dir() and not path_object.is_symlink()

    def read_bytes(self, path: PathLike) -> bytes:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "read_bytes",
            str(path),
        ):
            return Path(path).read_bytes()

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "write_bytes",
            str(path),
        ):
            Path(path).write_bytes(data)

    def remove_file(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_file",
            str(path),
        ):
            path_object = Path(path)
            path_object.chmod(path_object.stat().st_mode | stat.S_IWRITE)
            path_object.unlink()

    def remove_dir(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_dir",
            str(path),
        ):
            path_object = Path(path)
            path_object.chmod(path_object.stat().st_mode | stat.S_IWRITE)
            path_object.rmdir()

    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "make_dir",
            str(path),
        ):
            Path(path).mkdir(parents=parents, exist_ok=True)

    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "list_dir",
            str(path),
        ):
            return tuple(sorted(Path(path).iterdir()))

    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "copy_file",
            f"{source} -> {destination}",
        ):
            if not overwrite and Path(destination).exists():
                raise FileExistsError(destination)
            shutil.copy2(source, destination)

    def move_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "move_file",
            f"{source} -> {destination}",
        ):
            if not overwrite and Path(destination).exists():
                raise FileExistsError(destination)
            if overwrite:
                Path(destination).unlink(missing_ok=True)
            shutil.move(source, destination)


def _load_pywin32_file_module() -> Any:
    """延迟加载 pywin32，保证非 Windows 平台可以导入本包。"""
    try:
        return import_module("win32file")
    except ImportError as error:
        raise BackendUnavailableError(
            "PyWin32FileSystem 需要在 Windows 环境安装 pywin32。"
        ) from error


class PyWin32FileSystem(_FileSystemBackend):
    """使用 ``pywin32.win32file`` 的 Windows 文件系统实现。"""

    def __init__(
        self,
        *,
        chunk_size: int = 1024 * 1024,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        super().__init__(event_publisher)
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0。")
        self._win32file = _load_pywin32_file_module()
        self._chunk_size = chunk_size

    def exists(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "exists", str(path)):
            try:
                self._win32file.GetFileAttributes(str(path))
            except Exception:
                return False
            return True

    def is_file(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "is_file", str(path)):
            return Path(path).is_file()

    def is_dir(self, path: PathLike) -> bool:
        with self._operation(IOEventType.FILESYSTEM_OPERATION, "is_dir", str(path)):
            path_object = Path(path)
            return path_object.is_dir() and not path_object.is_symlink()

    def read_bytes(self, path: PathLike) -> bytes:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "read_bytes",
            str(path),
        ):
            handle = self._win32file.CreateFile(
                str(path),
                self._win32file.GENERIC_READ,
                self._win32file.FILE_SHARE_READ
                | self._win32file.FILE_SHARE_WRITE
                | self._win32file.FILE_SHARE_DELETE,
                None,
                self._win32file.OPEN_EXISTING,
                self._win32file.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            try:
                content = bytearray()
                while True:
                    _, chunk = self._win32file.ReadFile(handle, self._chunk_size)
                    if not chunk:
                        return bytes(content)
                    content.extend(chunk)
            finally:
                self._win32file.CloseHandle(handle)

    def write_bytes(self, path: PathLike, data: bytes) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "write_bytes",
            str(path),
        ):
            handle = self._win32file.CreateFile(
                str(path),
                self._win32file.GENERIC_WRITE,
                self._win32file.FILE_SHARE_READ
                | self._win32file.FILE_SHARE_WRITE
                | self._win32file.FILE_SHARE_DELETE,
                None,
                self._win32file.CREATE_ALWAYS,
                self._win32file.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            try:
                offset = 0
                while offset < len(data):
                    _, written = self._win32file.WriteFile(
                        handle,
                        data[offset : offset + self._chunk_size],
                    )
                    if written <= 0:
                        raise OSError("Windows 文件写入未取得进展。")
                    offset += written
            finally:
                self._win32file.CloseHandle(handle)

    def remove_file(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_file",
            str(path),
        ):
            Path(path).chmod(Path(path).stat().st_mode | stat.S_IWRITE)
            self._win32file.DeleteFile(str(path))

    def remove_dir(self, path: PathLike) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "remove_dir",
            str(path),
        ):
            Path(path).chmod(Path(path).stat().st_mode | stat.S_IWRITE)
            self._win32file.RemoveDirectory(str(path))

    def make_dir(self, path: PathLike, *, parents: bool = False) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "make_dir",
            str(path),
        ):
            path_object = Path(path)
            if parents:
                path_object.mkdir(parents=True, exist_ok=True)
                return
            try:
                self._win32file.CreateDirectory(str(path_object), None)
            except Exception:
                if not path_object.is_dir():
                    raise

    def list_dir(self, path: PathLike) -> tuple[Path, ...]:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "list_dir",
            str(path),
        ):
            return tuple(sorted(Path(path).iterdir()))

    def copy_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "copy_file",
            f"{source} -> {destination}",
        ):
            self._win32file.CopyFile(
                str(source),
                str(destination),
                int(not overwrite),
            )

    def move_file(
        self,
        source: PathLike,
        destination: PathLike,
        *,
        overwrite: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.FILESYSTEM_OPERATION,
            "move_file",
            f"{source} -> {destination}",
        ):
            flags = 0
            if overwrite:
                flags |= self._win32file.MOVEFILE_REPLACE_EXISTING
            self._win32file.MoveFileEx(
                str(source),
                str(destination),
                flags,
            )


WindowsFileSystem = PyWin32FileSystem

__all__ = [
    "PathFileSystem",
    "PyWin32FileSystem",
    "WindowsFileSystem",
]
