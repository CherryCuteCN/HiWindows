"""软件管理领域事件。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .uninstall import UninstallProgress


class SoftwareManagerEventType(StrEnum):
    """软件管理事件类型。"""

    UNINSTALL_PROGRESS = "software_manager.uninstall.progress"


@dataclass(frozen=True, slots=True)
class UninstallProgressEvent:
    """一次卸载进度更新。"""

    progress: UninstallProgress
    event_type: SoftwareManagerEventType = SoftwareManagerEventType.UNINSTALL_PROGRESS


__all__ = ["SoftwareManagerEventType", "UninstallProgressEvent"]
