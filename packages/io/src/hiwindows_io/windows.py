"""Windows I/O 能力门面。"""

from __future__ import annotations

from core.models.event import EventPublisher

from .models.filesystem import FileSystem
from .models.process import ProcessRunner
from .models.registry import Registry
from .models.shell import ShortcutResolver


class WindowsIO:
    """业务模块使用 Windows 能力的唯一组合入口。

    业务层只依赖本对象暴露的端口，不需要导入 ``pywin32`` 或具体后端。
    所有默认后端的创建都集中在 ``hiwindows_io`` 包内。
    """

    def __init__(
        self,
        *,
        filesystem: FileSystem | None = None,
        registry: Registry | None = None,
        shortcut_resolver: ShortcutResolver | None = None,
        process_runner: ProcessRunner | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if (
            filesystem is None
            or registry is None
            or shortcut_resolver is None
            or process_runner is None
        ):
            from .filesystem import WindowsFileSystem
            from .process import WindowsProcessRunner
            from .registry import WindowsRegistry
            from .shell import WindowsShortcutResolver

            filesystem = filesystem or WindowsFileSystem(
                event_publisher=event_publisher,
            )
            registry = registry or WindowsRegistry(event_publisher=event_publisher)
            shortcut_resolver = shortcut_resolver or WindowsShortcutResolver()
            process_runner = process_runner or WindowsProcessRunner()

        self.filesystem = filesystem
        self.registry = registry
        self.shortcut_resolver = shortcut_resolver
        self.process_runner = process_runner
        self.event_publisher = event_publisher


__all__ = ["WindowsIO"]
