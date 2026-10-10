"""应用注册与管理。"""

from .models.app import App, AppRegistry
from enum import Enum

class AppType(Enum):
    """应用类型。"""
    TOOL = "tool"
    UI = "ui"

class AppRegistryImpl(AppRegistry):
    def register(self, app: App) -> None:
        pass

    def unregister(self, app: App) -> None:
        pass
