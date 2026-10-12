"""Windows 进程执行后端。"""

from __future__ import annotations

import subprocess

from .models.process import ProcessResult, ProcessRunner


class WindowsProcessRunner:
    """使用 Windows 命令解释器执行卸载命令。"""

    def run(self, command: str, *, working_dir: str | None = None) -> ProcessResult:
        completed = subprocess.run(
            command,
            cwd=working_dir,
            check=False,
            shell=True,
        )
        return ProcessResult(return_code=completed.returncode)


__all__ = ["ProcessRunner", "ProcessResult", "WindowsProcessRunner"]
