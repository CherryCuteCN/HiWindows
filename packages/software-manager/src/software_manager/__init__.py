"""HiWindows 软件管理模块。"""

from .models.events import SoftwareManagerEventType, UninstallProgressEvent
from .models.uninstall import (
    ApplicationType,
    Uninstall,
    UninstallPhase,
    UninstallProgress,
)
from .uninstaller import SoftwareUninstaller, WindowsSoftwareUninstaller

__all__ = [
    "ApplicationType",
    "SoftwareUninstaller",
    "SoftwareManagerEventType",
    "Uninstall",
    "UninstallPhase",
    "UninstallProgress",
    "UninstallProgressEvent",
    "WindowsSoftwareUninstaller",
]
