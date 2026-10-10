"""应用模型与注册接口。"""

from abc import ABC, abstractmethod


class App(ABC):
    """应用生命周期接口。"""

    @abstractmethod
    def run(self) -> None:
        """启动应用。"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止应用。"""
        ...


class AppRegistry(ABC):
    """应用注册表接口。"""

    @abstractmethod
    def register(self, app: App) -> None:
        """注册应用。"""
        ...

    @abstractmethod
    def unregister(self, app: App) -> None:
        """注销应用。"""
        ...

    @abstractmethod
    def get_app(self, app_id: str) -> App:
        """根据应用 ID 获取应用。"""
        ...
