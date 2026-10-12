"""Windows 应用卸载记录模型。"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from hiwindows_io import RegistryHive


class ApplicationType(StrEnum):
    """应用安装类型。"""

    WIN32 = "win32"
    MSI = "msi"
    APPX = "appx"
    PORTABLE = "portable"
    UNKNOWN = "unknown"


class UninstallPhase(StrEnum):
    """卸载过程阶段。"""

    INSPECTING = "inspecting"
    RUNNING_UNINSTALLER = "running_uninstaller"
    REMOVING_FILES = "removing_files"
    REMOVING_REGISTRY = "removing_registry"
    COMPLETED = "completed"
    FAILED = "failed"


class UninstallProgress(BaseModel):
    """卸载过程中的实时进度事件。"""

    phase: UninstallPhase
    progress: float = Field(ge=0, le=100, description="整体完成百分比")
    current_directory: str | None = Field(
        default=None,
        description="当前正在处理的目录",
    )
    current_path: str | None = Field(
        default=None,
        description="当前正在处理的文件或注册表路径",
    )
    completed_items: int = Field(default=0, ge=0, description="已处理项目数")
    total_items: int = Field(default=0, ge=0, description="待处理项目数")
    message: str = Field(default="", description="面向用户的进度说明")
    succeeded: bool = True
    error: str | None = None

    @classmethod
    def for_path(
        cls,
        *,
        phase: UninstallPhase,
        path: Path | str,
        completed_items: int,
        total_items: int,
        message: str,
    ) -> "UninstallProgress":
        """从文件路径构造进度事件。"""
        path_object = Path(path)
        progress = (
            100.0
            if total_items == 0
            else min(100.0, completed_items / total_items * 100)
        )
        return cls(
            phase=phase,
            progress=progress,
            current_directory=str(path_object.parent),
            current_path=str(path_object),
            completed_items=completed_items,
            total_items=total_items,
            message=message,
        )


class RegistryLocation(BaseModel):
    """应用在 Windows 注册表中的清理位置。"""

    hive: RegistryHive = Field(description="注册表根键")
    path: str = Field(min_length=1, description="注册表键路径")
    value_names: list[str] = Field(
        default_factory=list,
        description="需要单独删除的值名称；为空时表示处理整个键",
    )
    recursive: bool = Field(
        default=True,
        description="是否递归删除该键下的子键",
    )


class UninstallRegistryRecord(BaseModel):
    """Windows“应用和功能”使用的卸载注册表记录。"""

    hive: RegistryHive = Field(description="注册表根键")
    path: str = Field(min_length=1, description="卸载项注册表路径")
    display_name: str | None = Field(default=None, description="显示名称")
    display_version: str | None = Field(default=None, description="显示版本")
    publisher: str | None = Field(default=None, description="发布者")
    install_location: str | None = Field(default=None, description="安装目录")
    display_icon: str | None = Field(default=None, description="显示图标路径")
    uninstall_string: str | None = Field(default=None, description="卸载命令")
    quiet_uninstall_string: str | None = Field(
        default=None,
        description="静默卸载命令",
    )
    estimated_size_kb: int | None = Field(
        default=None,
        ge=0,
        description="预估安装大小，单位为 KB",
    )
    windows_installer: bool = Field(
        default=False,
        description="是否由 Windows Installer 管理",
    )
    system_component: bool = Field(
        default=False,
        description="是否为系统组件",
    )
    no_modify: bool = Field(default=False, description="是否禁止修改")
    no_remove: bool = Field(default=False, description="是否禁止卸载")
    install_date: str | None = Field(default=None, description="安装日期")


class UninstallCommand(BaseModel):
    """应用提供的卸载命令。"""

    command: str = Field(min_length=1, description="卸载命令")
    quiet_command: str | None = Field(default=None, description="静默卸载命令")
    working_dir: str | None = Field(default=None, description="执行命令时的工作目录")
    requires_elevation: bool = Field(default=True, description="是否需要管理员权限")


class ServiceRecord(BaseModel):
    """应用注册的 Windows 服务。"""

    name: str = Field(min_length=1, description="服务名")
    display_name: str | None = Field(default=None, description="服务显示名")
    executable_path: str | None = Field(default=None, description="服务程序路径")


class ScheduledTaskRecord(BaseModel):
    """应用注册的计划任务。"""

    path: str = Field(min_length=1, description="计划任务完整路径")
    author: str | None = Field(default=None, description="任务作者")


class StartupEntryRecord(BaseModel):
    """应用的开机启动项。"""

    name: str = Field(min_length=1, description="启动项名称")
    command: str = Field(min_length=1, description="启动命令")
    location: str = Field(
        min_length=1,
        description="启动项来源，例如 Run 注册表或 Startup 目录",
    )


class FileAssociationRecord(BaseModel):
    """应用注册的文件扩展名关联。"""

    extension: str = Field(min_length=1, description="文件扩展名")
    prog_id: str | None = Field(default=None, description="Windows ProgID")
    command: str | None = Field(default=None, description="打开文件时执行的命令")


class UrlProtocolRecord(BaseModel):
    """应用注册的 URL 协议。"""

    scheme: str = Field(min_length=1, description="协议名称，不含冒号")
    prog_id: str | None = Field(default=None, description="Windows ProgID")


class ShellExtensionRecord(BaseModel):
    """应用注册的资源管理器 Shell 扩展。"""

    clsid: str = Field(min_length=1, description="COM CLSID")
    registry_path: str | None = Field(default=None, description="注册表路径")
    description: str | None = Field(default=None, description="扩展说明")


class AppPathRecord(BaseModel):
    """应用注册的 App Paths 项。"""

    name: str = Field(min_length=1, description="可执行文件名")
    executable_path: str = Field(min_length=1, description="可执行文件路径")


class EnvironmentVariableRecord(BaseModel):
    """应用增加或修改的环境变量。"""

    name: str = Field(min_length=1, description="变量名")
    value: str = Field(description="变量值")
    scope: str = Field(min_length=1, description="变量范围，例如 User 或 Machine")


class FirewallRuleRecord(BaseModel):
    """应用创建的 Windows 防火墙规则。"""

    name: str = Field(min_length=1, description="防火墙规则名称")
    direction: str | None = Field(default=None, description="入站或出站")
    protocol: str | None = Field(default=None, description="网络协议")


class CertificateRecord(BaseModel):
    """应用安装的证书。"""

    store: str = Field(min_length=1, description="证书存储区")
    thumbprint: str = Field(min_length=1, description="证书指纹")


class MsiRecord(BaseModel):
    """MSI 安装包的标识。"""

    product_code: str = Field(min_length=1, description="MSI ProductCode")
    upgrade_code: str | None = Field(default=None, description="MSI UpgradeCode")
    package_code: str | None = Field(default=None, description="MSI PackageCode")


class AppxRecord(BaseModel):
    """MSIX/AppX 应用包信息。"""

    package_full_name: str = Field(min_length=1, description="Package Full Name")
    package_family_name: str = Field(
        min_length=1,
        description="Package Family Name",
    )
    install_location: str = Field(min_length=1, description="应用包安装目录")
    user_data_dirs: list[str] = Field(
        default_factory=list,
        description="应用包用户数据目录",
    )


class PackageManagerRecord(BaseModel):
    """第三方包管理器中的应用标识。"""

    manager: str = Field(min_length=1, description="包管理器名称")
    package_id: str = Field(min_length=1, description="包管理器中的应用 ID")
    version: str | None = Field(default=None, description="包管理器记录的版本")


class Uninstall(BaseModel):
    """描述一个 Windows 应用及其完整卸载信息。

    ``id`` 保留快捷方式完整路径作为当前应用发现入口；真正稳定的应用身份
    还应记录在 ``msi``、``appx`` 或 ``package_manager`` 中。
    ``dir`` 是应用实际安装目录，不是快捷方式所在目录。
    """

    id: str = Field(min_length=1, description="应用快捷方式的完整路径")
    name: str = Field(min_length=1, description="应用名称")
    dir: str = Field(min_length=1, description="应用实际安装目录")
    application_type: ApplicationType = Field(
        default=ApplicationType.UNKNOWN,
        description="应用安装类型",
    )
    publisher: str | None = Field(default=None, description="应用发布者")
    version: str | None = Field(default=None, description="应用版本")
    executable_paths: list[str] = Field(
        default_factory=list,
        description="应用可执行文件路径",
    )
    shortcut_paths: list[str] = Field(
        default_factory=list,
        description="桌面、开始菜单等位置的快捷方式",
    )
    program_data_dirs: list[str] = Field(
        default_factory=list,
        description="ProgramData 下需要清理的目录",
    )
    app_data_dirs: list[str] = Field(
        default_factory=list,
        description="AppData 下需要清理的目录",
    )
    cache_dirs: list[str] = Field(
        default_factory=list,
        description="应用缓存和临时目录",
    )
    uninstall_commands: list[UninstallCommand] = Field(
        default_factory=list,
        description="应用提供的卸载命令",
    )
    registry_keys: list[RegistryLocation] = Field(
        default_factory=list,
        description="应用需要清理的注册表键和值",
    )
    uninstall_registry_records: list[UninstallRegistryRecord] = Field(
        default_factory=list,
        description="应用和功能中的卸载注册表记录",
    )
    services: list[ServiceRecord] = Field(
        default_factory=list,
        description="应用注册的服务",
    )
    scheduled_tasks: list[ScheduledTaskRecord] = Field(
        default_factory=list,
        description="应用注册的计划任务",
    )
    startup_entries: list[StartupEntryRecord] = Field(
        default_factory=list,
        description="应用的开机启动项",
    )
    file_associations: list[FileAssociationRecord] = Field(
        default_factory=list,
        description="文件扩展名关联",
    )
    url_protocols: list[UrlProtocolRecord] = Field(
        default_factory=list,
        description="URL 协议注册",
    )
    shell_extensions: list[ShellExtensionRecord] = Field(
        default_factory=list,
        description="Shell 扩展注册",
    )
    app_paths: list[AppPathRecord] = Field(
        default_factory=list,
        description="App Paths 注册",
    )
    environment_variables: list[EnvironmentVariableRecord] = Field(
        default_factory=list,
        description="应用设置的环境变量",
    )
    firewall_rules: list[FirewallRuleRecord] = Field(
        default_factory=list,
        description="应用创建的防火墙规则",
    )
    certificates: list[CertificateRecord] = Field(
        default_factory=list,
        description="应用安装的证书",
    )
    msi: MsiRecord | None = Field(default=None, description="MSI 标识信息")
    appx: AppxRecord | None = Field(default=None, description="MSIX/AppX 信息")
    package_manager: PackageManagerRecord | None = Field(
        default=None,
        description="包管理器信息",
    )
