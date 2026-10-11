"""导出 I/O 抽象模型。"""

from .filesystem import FileSystem, PathLike
from .registry import (
    Registry,
    RegistryHive,
    RegistryValue,
    RegistryValueType,
)

__all__ = [
    "FileSystem",
    "PathLike",
    "Registry",
    "RegistryHive",
    "RegistryValue",
    "RegistryValueType",
]
