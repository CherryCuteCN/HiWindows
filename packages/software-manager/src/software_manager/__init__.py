"""HiWindows 软件管理模块。"""

from .models.events import SoftwareManagerEventType, UninstallProgressEvent
from .models.uninstall import (
    ApplicationType,
    CleanupItem,
    CleanupItemType,
    CleanupRisk,
    IndexedApplication,
    Uninstall,
    UninstallMethod,
    UninstallMode,
    UninstallPhase,
    UninstallPlan,
    UninstallProgress,
)
from .uninstaller import SoftwareUninstaller, WindowsSoftwareUninstaller

__all__ = [
    "ApplicationType",
    "CleanupItem",
    "CleanupItemType",
    "CleanupRisk",
    "IndexedApplication",
    "SoftwareUninstaller",
    "SoftwareManagerEventType",
    "Uninstall",
    "UninstallMethod",
    "UninstallMode",
    "UninstallPhase",
    "UninstallPlan",
    "UninstallProgress",
    "UninstallProgressEvent",
    "WindowsSoftwareUninstaller",
]
