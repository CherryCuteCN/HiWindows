"""HiWindows 输入输出模块。

抽象接口可以在任意平台导入；Windows 后端会在实例化时延迟加载
``pywin32``，因此不会让 macOS/Linux 上的导入阶段直接失败。
"""

from .exceptions import BackendUnavailableError, WindowsIOError
from .filesystem import (
    PathFileSystem,
    PyWin32FileSystem,
    WindowsFileSystem,
)
from .models import (
    FileSystem,
    PathLike,
    Registry,
    RegistryHive,
    RegistryValue,
    RegistryValueType,
)
from .registry import (
    PyWin32Registry,
    WindowsRegistry,
)

__all__ = [
    "BackendUnavailableError",
    "FileSystem",
    "PathFileSystem",
    "PathLike",
    "PyWin32FileSystem",
    "PyWin32Registry",
    "Registry",
    "RegistryHive",
    "RegistryValue",
    "RegistryValueType",
    "WindowsFileSystem",
    "WindowsIOError",
    "WindowsRegistry",
]
