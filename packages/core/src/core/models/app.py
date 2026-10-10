"""应用模型与注册接口。"""

from abc import ABC, abstractmethod
from enum import Enum


class AppType(Enum):
    """应用类型。"""
    TOOL = "tool"
    UI = "ui"

class App(ABC):
    """应用生命周期接口。"""

    @abstractmethod
    def run(self, app_type: AppType) -> None:
        """启动应用。"""
        ...

    @abstractmethod
    def stop(self, app_type: AppType) -> None:
        """停止应用。"""
        ...
