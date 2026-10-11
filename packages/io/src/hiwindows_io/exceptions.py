"""HiWindows I/O 后端相关异常。"""


class WindowsIOError(OSError):
    """Windows I/O 操作失败。"""


class BackendUnavailableError(RuntimeError):
    """当前平台或环境未安装所需的 Windows 后端。"""
