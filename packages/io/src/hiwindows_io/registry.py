"""Windows 注册表抽象与 pywin32 实现。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from core.models.event import EventPublisher

from .exceptions import BackendUnavailableError
from .models.events import IOEventType
from .models.registry import (
    Registry,
    RegistryHive,
    RegistryValue,
    RegistryValueType,
)


def _load_pywin32_registry_modules() -> tuple[Any, Any]:
    """延迟加载 pywin32，保证非 Windows 平台可以导入本包。"""
    try:
        return import_module("win32api"), import_module("win32con")
    except ImportError as error:
        raise BackendUnavailableError(
            "PyWin32Registry 需要在 Windows 环境安装 pywin32。"
        ) from error


def _is_missing_error(error: BaseException) -> bool:
    """判断 pywin32 是否报告了不存在的注册表对象。"""
    return getattr(error, "winerror", None) in {2, 3}


class PyWin32Registry(Registry):
    """使用 ``pywin32.win32api`` 的注册表实现。"""

    def __init__(self, event_publisher: EventPublisher | None = None) -> None:
        super().__init__(event_publisher)
        self._win32api, self._win32con = _load_pywin32_registry_modules()

    def _root(self, hive: RegistryHive) -> int:
        try:
            return getattr(self._win32con, hive.value)
        except AttributeError as error:
            raise ValueError(f"不支持的注册表根键: {hive!r}") from error

    def _open_key(self, hive: RegistryHive, key_path: str, access: int) -> Any:
        return self._win32api.RegOpenKeyEx(
            self._root(hive),
            key_path,
            0,
            access,
        )

    def key_exists(self, hive: RegistryHive, key_path: str) -> bool:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "key_exists",
            f"{hive.value}\\{key_path}",
        ):
            try:
                handle = self._open_key(hive, key_path, self._win32con.KEY_READ)
            except Exception as error:
                if _is_missing_error(error):
                    return False
                raise
            self._win32api.RegCloseKey(handle)
            return True

    def create_key(self, hive: RegistryHive, key_path: str) -> None:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "create_key",
            f"{hive.value}\\{key_path}",
        ):
            handle, _ = self._win32api.RegCreateKeyEx(
                self._root(hive),
                key_path,
                0,
                "",
                0,
                self._win32con.KEY_WRITE,
                None,
            )
            self._win32api.RegCloseKey(handle)

    def delete_key(
        self,
        hive: RegistryHive,
        key_path: str,
        *,
        recursive: bool = False,
    ) -> None:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "delete_key",
            f"{hive.value}\\{key_path}",
        ):
            if recursive:
                for child in self.list_subkeys(hive, key_path):
                    self.delete_key(
                        hive,
                        f"{key_path}\\{child}",
                        recursive=True,
                    )
            self._win32api.RegDeleteKey(self._root(hive), key_path)

    def read_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str = "",
        *,
        default: object | None = None,
    ) -> object | None:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "read_value",
            f"{hive.value}\\{key_path}\\{value_name}",
        ):
            try:
                handle = self._open_key(hive, key_path, self._win32con.KEY_READ)
            except Exception as error:
                if _is_missing_error(error):
                    return default
                raise
            try:
                value, _ = self._win32api.RegQueryValueEx(handle, value_name)
                return value
            except Exception as error:
                if _is_missing_error(error):
                    return default
                raise
            finally:
                self._win32api.RegCloseKey(handle)

    def write_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str,
        value: object,
        *,
        value_type: RegistryValueType | int | None = None,
    ) -> None:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "write_value",
            f"{hive.value}\\{key_path}\\{value_name}",
        ):
            if value_type is None:
                value_type = self._infer_value_type(value)
            handle, _ = self._win32api.RegCreateKeyEx(
                self._root(hive),
                key_path,
                0,
                "",
                0,
                self._win32con.KEY_WRITE,
                None,
            )
            try:
                self._win32api.RegSetValueEx(
                    handle,
                    value_name,
                    0,
                    int(value_type),
                    value,
                )
            finally:
                self._win32api.RegCloseKey(handle)

    def delete_value(
        self,
        hive: RegistryHive,
        key_path: str,
        value_name: str = "",
    ) -> None:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "delete_value",
            f"{hive.value}\\{key_path}\\{value_name}",
        ):
            handle = self._open_key(hive, key_path, self._win32con.KEY_WRITE)
            try:
                self._win32api.RegDeleteValue(handle, value_name)
            finally:
                self._win32api.RegCloseKey(handle)

    def list_subkeys(self, hive: RegistryHive, key_path: str) -> tuple[str, ...]:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "list_subkeys",
            f"{hive.value}\\{key_path}",
        ):
            handle = self._open_key(hive, key_path, self._win32con.KEY_READ)
            try:
                names: list[str] = []
                index = 0
                while True:
                    try:
                        names.append(self._win32api.RegEnumKey(handle, index))
                    except Exception as error:
                        if getattr(error, "winerror", None) == 259:
                            return tuple(names)
                        raise
                    index += 1
            finally:
                self._win32api.RegCloseKey(handle)

    def list_values(
        self,
        hive: RegistryHive,
        key_path: str,
    ) -> tuple[RegistryValue, ...]:
        with self._operation(
            IOEventType.REGISTRY_OPERATION,
            "list_values",
            f"{hive.value}\\{key_path}",
        ):
            handle = self._open_key(hive, key_path, self._win32con.KEY_READ)
            try:
                values: list[RegistryValue] = []
                index = 0
                while True:
                    try:
                        name, data, value_type = self._win32api.RegEnumValue(
                            handle,
                            index,
                        )
                    except Exception as error:
                        if getattr(error, "winerror", None) == 259:
                            return tuple(values)
                        raise
                    values.append(RegistryValue(name, data, value_type))
                    index += 1
            finally:
                self._win32api.RegCloseKey(handle)

    def _infer_value_type(self, value: object) -> RegistryValueType:
        if isinstance(value, bool) or isinstance(value, int):
            return RegistryValueType.DWORD
        if isinstance(value, str):
            return RegistryValueType.STRING
        if isinstance(value, bytes):
            return RegistryValueType.BINARY
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return RegistryValueType.MULTI_STRING
        raise TypeError(
            "无法推断注册表值类型，请通过 value_type 显式指定类型。"
        )


WindowsRegistry = PyWin32Registry

__all__ = [
    "PyWin32Registry",
    "WindowsRegistry",
]
