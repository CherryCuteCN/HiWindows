"""应用模型与生命周期端口。"""

from enum import Enum
from typing import Protocol


class AppType(Enum):
    """应用类型。"""
    TOOL = "tool"
    UI = "ui"

class App(Protocol):
    """应用生命周期端口。"""

    def run(self, app_type: AppType) -> None:
        """启动应用。"""
        ...

    def stop(self, app_type: AppType) -> None:
        """停止应用。"""
        ...
