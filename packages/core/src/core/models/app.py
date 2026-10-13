"""应用根抽象类与可选的模式能力。"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import ClassVar


class AppType(StrEnum):
    """应用类型。"""

    TOOL = "tool"
    UI = "ui"


class AppMode(StrEnum):
    """宿主可以识别的通用模式标识。

    模式的具体行为由实现类决定；core 不规定 standard/simple 的业务语义。
    """

    STANDARD = "standard"
    SIMPLE = "simple"


class App(ABC):
    """所有 HiWindows 组件和插件必须继承的根抽象类。

    ``supports_managed_modes`` 默认是 ``False``。没有明确实现
    :class:`ModeAwareApp` 的组件不会被总控接管模式切换，而是使用自己的
    默认运行流程。
    """

    supports_managed_modes: ClassVar[bool] = False

    @abstractmethod
    def run(self, app_type: AppType) -> None:
        """启动应用。"""
        ...

    @abstractmethod
    def stop(self, app_type: AppType) -> None:
        """停止应用。"""
        ...


class ModeAwareApp(App, ABC):
    """声明由宿主管理运行模式的可选 App 能力。

    继承该类即表示组件愿意向宿主声明模式并接收模式执行请求；模式的
    选择规则、确认流程和实际行为全部由具体 App 自己定义。
    """

    supports_managed_modes: ClassVar[bool] = True

    @abstractmethod
    def modes(self) -> tuple[str, ...]:
        """返回该 App 实际支持的模式名称。"""
        ...

    @abstractmethod
    def run_mode(self, mode: str, request: object | None = None) -> object:
        """按 App 自己定义的模式执行一次请求。"""
        ...
