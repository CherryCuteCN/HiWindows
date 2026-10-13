"""通过桌面快捷方式发现并卸载 Windows 应用。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from core import AppType, ModeAwareApp
from core.models.event import EventPublisher
from hiwindows_io import (
    FileSystem,
    PathLike,
    ProcessRunner,
    Registry,
    RegistryHive,
    ShortcutInfo,
    ShortcutResolver,
    WindowsIO,
)

from .models.events import UninstallProgressEvent
from .models.uninstall import (
    ApplicationType,
    CleanupItem,
    CleanupItemType,
    CleanupRisk,
    IndexedApplication,
    RegistryLocation,
    Uninstall,
    UninstallCommand,
    UninstallMethod,
    UninstallMode,
    UninstallPhase,
    UninstallPlan,
    UninstallProgress,
    UninstallRegistryRecord,
)

_UNINSTALL_REGISTRY_PATHS = (
    (
        RegistryHive.CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
    ),
    (
        RegistryHive.LOCAL_MACHINE,
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
    ),
    (
        RegistryHive.LOCAL_MACHINE,
        r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ),
)


class SoftwareUninstaller(ModeAwareApp):
    """可替换 Windows I/O 后端的应用卸载编排器。

    ``uninstall`` 是同步生成器：调用方可以在每个文件、目录或注册表项
    处理完成后立即拿到一个 ``UninstallProgress``，适合直接接 UI 或 RPC
    的流式响应。
    """

    supports_managed_modes = True

    def __init__(
        self,
        filesystem: FileSystem,
        shortcut_resolver: ShortcutResolver,
        *,
        registry: Registry | None = None,
        process_runner: ProcessRunner | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._filesystem = filesystem
        self._shortcut_resolver = shortcut_resolver
        self._registry = registry
        self._process_runner = process_runner
        self._event_publisher = event_publisher
        self._indexed_applications: tuple[IndexedApplication, ...] = ()

    def run(self, app_type: AppType) -> None:
        """启动软件管理组件。

        卸载器本身不需要常驻进程；该方法保留给 core App 生命周期管理。
        """

    def stop(self, app_type: AppType) -> None:
        """停止软件管理组件。"""

    def modes(self) -> tuple[str, ...]:
        """返回软件管理器自己定义的两种卸载模式。"""
        return (UninstallMode.STANDARD, UninstallMode.SIMPLE)

    def run_mode(self, mode: str, request: object | None = None) -> object:
        """按软件管理器定义的模式执行卸载请求。"""
        selected_item_ids: set[str] | None = None
        reference = request
        method: object = UninstallMethod.APPLICATION
        if isinstance(request, dict):
            reference = request.get("reference")
            method = request.get("method", UninstallMethod.APPLICATION)
            selected = request.get("selected_item_ids")
            if selected is not None:
                if not isinstance(selected, (list, set, tuple)) or not all(
                    isinstance(item, str) for item in selected
                ):
                    raise TypeError("selected_item_ids 必须是字符串序列")
                selected_item_ids = set(selected)
        if not isinstance(reference, (str, os.PathLike)):
            raise TypeError("软件卸载模式需要快捷方式路径或索引 ID")
        try:
            uninstall_mode = UninstallMode(mode)
        except ValueError as error:
            raise ValueError(f"不支持的软件卸载模式: {mode}") from error
        try:
            uninstall_method = UninstallMethod(method)
        except (TypeError, ValueError) as error:
            raise ValueError(f"不支持的软件卸载方式: {method}") from error
        return self.uninstall(
            reference,
            mode=uninstall_mode,
            method=uninstall_method,
            selected_item_ids=selected_item_ids,
        )

    def refresh_index(self) -> tuple[IndexedApplication, ...]:
        """刷新应用快速索引；同名候选会保留为独立记录。"""
        indexed: list[IndexedApplication] = []
        for record in self._all_registry_records():
            if not record.display_name:
                continue
            indexed.append(
                IndexedApplication(
                    application_id=f"registry:{record.hive.value}:{record.path}",
                    name=record.display_name,
                    application_type=(
                        ApplicationType.MSI
                        if record.windows_installer
                        else ApplicationType.WIN32
                    ),
                    publisher=record.publisher,
                    version=record.display_version,
                    install_location=record.install_location,
                    source="uninstall_registry",
                    evidence=[f"{record.hive.value}\\{record.path}"],
                )
            )

        for root in self._shortcut_roots():
            for shortcut_path in self._iter_files(root):
                if shortcut_path.suffix.lower() != ".lnk":
                    continue
                try:
                    shortcut = self._shortcut_resolver.resolve(shortcut_path)
                except (OSError, ValueError):
                    continue
                indexed.append(
                    IndexedApplication(
                        application_id=f"shortcut:{self._path_key(shortcut.path)}",
                        name=shortcut.path.stem,
                        application_type=ApplicationType.PORTABLE,
                        install_location=str(shortcut.target_path.parent),
                        executable_paths=[str(shortcut.target_path)],
                        entry_path=str(shortcut.path),
                        source="shortcut",
                        evidence=[f"shortcut:{shortcut.path}"],
                    )
                )

        self._indexed_applications = tuple(indexed)
        return self._indexed_applications

    def search(self, query: str) -> tuple[IndexedApplication, ...]:
        """在快速索引中按名称、发布者或路径搜索应用。"""
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return ()
        if not self._indexed_applications:
            self.refresh_index()
        return tuple(
            application
            for application in self._indexed_applications
            if normalized_query in " ".join(
                value.casefold()
                for value in (
                    application.name,
                    application.publisher or "",
                    application.install_location or "",
                    *application.executable_paths,
                )
            )
        )

    def inspect(self, shortcut_path: PathLike) -> Uninstall:
        """从快捷方式解析应用，并收集可清理的快捷方式、命令和注册表项。"""
        shortcut = self._shortcut_resolver.resolve(shortcut_path)
        target_path = shortcut.target_path.expanduser()
        install_dir = self._resolve_install_dir(shortcut, target_path)
        registry_records = self._find_registry_records(
            shortcut_name=shortcut.path.stem,
            target_path=target_path,
            install_dir=install_dir,
        )
        install_dir = self._prefer_registry_install_dir(
            install_dir,
            registry_records,
            target_path,
        )

        shortcut_paths = self._find_related_shortcuts(shortcut, target_path)
        if shortcut.path not in shortcut_paths:
            shortcut_paths.insert(0, shortcut.path)

        uninstall_commands = self._commands_from_records(registry_records)
        registry_keys = [
            RegistryLocation(
                hive=record.hive,
                path=record.path,
                recursive=True,
            )
            for record in registry_records
            if not record.no_remove
        ]
        application_type = (
            ApplicationType.MSI
            if any(record.windows_installer for record in registry_records)
            else ApplicationType.WIN32
        )
        publisher = next(
            (record.publisher for record in registry_records if record.publisher),
            None,
        )
        version = next(
            (
                record.display_version
                for record in registry_records
                if record.display_version
            ),
            None,
        )
        return Uninstall(
            id=str(shortcut.path),
            name=next(
                (
                    record.display_name
                    for record in registry_records
                    if record.display_name
                ),
                shortcut.path.stem,
            ),
            dir=str(install_dir),
            application_type=application_type,
            publisher=publisher,
            version=version,
            executable_paths=[str(target_path)],
            shortcut_paths=[str(path) for path in shortcut_paths],
            uninstall_commands=uninstall_commands,
            registry_keys=registry_keys,
            uninstall_registry_records=registry_records,
        )

    def create_plan(
        self,
        shortcut_path: PathLike,
        *,
        mode: UninstallMode = UninstallMode.STANDARD,
    ) -> UninstallPlan:
        """生成可预览的卸载计划，不执行任何破坏性操作。"""
        uninstall = self._inspect_reference(shortcut_path)
        system_component = any(
            record.system_component for record in uninstall.uninstall_registry_records
        )
        items: list[CleanupItem] = []

        for index, path in enumerate(self._cleanup_paths(uninstall)):
            path_object = Path(path)
            is_install_dir = self._path_key(path_object) == self._path_key(
                Path(uninstall.dir)
            )
            items.append(
                CleanupItem(
                    id=f"path:{index}",
                    item_type=(
                        CleanupItemType.DIRECTORY
                        if self._filesystem.is_dir(path_object)
                        else CleanupItemType.FILE
                    ),
                    target=str(path_object),
                    description=(
                        "清理应用安装目录"
                        if is_install_dir
                        else "清理应用关联文件或快捷方式"
                    ),
                    risk=CleanupRisk.HIGH if is_install_dir else CleanupRisk.LOW,
                    evidence=["shortcut-target", "install-location"]
                    if is_install_dir
                    else ["related-shortcut"],
                    allowed_in_simple=not system_component,
                )
            )

        for index, location in enumerate(uninstall.registry_keys):
            items.append(
                CleanupItem(
                    id=f"registry:{index}",
                    item_type=CleanupItemType.REGISTRY,
                    target=f"{location.hive.value}\\{location.path}",
                    description="清理应用注册表项",
                    risk=CleanupRisk.HIGH
                    if system_component
                    else CleanupRisk.MEDIUM,
                    evidence=[location.path],
                    allowed_in_simple=not system_component,
                )
            )

        return UninstallPlan(
            application=uninstall,
            mode=mode,
            available_methods=[
                UninstallMethod.APPLICATION,
                *(
                    [UninstallMethod.OFFICIAL]
                    if uninstall.uninstall_commands
                    else []
                ),
            ],
            official_commands=uninstall.uninstall_commands,
            items=items,
            snapshot={
                "application_id": uninstall.id,
                "name": uninstall.name,
                "directory": uninstall.dir,
            },
        )

    def _inspect_reference(self, reference: PathLike) -> Uninstall:
        """根据快捷方式路径或索引 ID 生成最新卸载信息。"""
        reference_text = str(reference)
        if not reference_text.startswith(("registry:", "shortcut:")):
            return self.inspect(reference)

        if not self._indexed_applications:
            self.refresh_index()
        indexed = next(
            (
                application
                for application in self._indexed_applications
                if application.application_id == reference_text
            ),
            None,
        )
        if indexed is None:
            raise ValueError(f"索引中不存在应用: {reference_text}")
        if indexed.entry_path is not None:
            return self.inspect(indexed.entry_path)

        record = next(
            (
                record
                for record in self._all_registry_records()
                if (
                    f"registry:{record.hive.value}:{record.path}"
                    == reference_text
                )
            ),
            None,
        )
        if record is None:
            raise ValueError(f"应用索引已失效: {reference_text}")
        return self._uninstall_from_registry_record(reference_text, record)

    def _uninstall_from_registry_record(
        self,
        application_id: str,
        record: UninstallRegistryRecord,
    ) -> Uninstall:
        """把没有快捷方式入口的注册表应用转换为卸载信息。"""
        install_dir = record.install_location
        if not install_dir and record.display_icon:
            install_dir = str(Path(record.display_icon.split(",", 1)[0]).parent)
        install_dir = install_dir or "<unknown-install-location>"
        return Uninstall(
            id=application_id,
            name=record.display_name or application_id,
            dir=install_dir,
            application_type=(
                ApplicationType.MSI
                if record.windows_installer
                else ApplicationType.WIN32
            ),
            publisher=record.publisher,
            version=record.display_version,
            executable_paths=[record.display_icon]
            if record.display_icon
            else [],
            uninstall_commands=self._commands_from_records([record]),
            registry_keys=[
                RegistryLocation(
                    hive=record.hive,
                    path=record.path,
                    recursive=True,
                )
            ]
            if not record.no_remove
            else [],
            uninstall_registry_records=[record],
        )

    def uninstall(
        self,
        shortcut_path: PathLike,
        *,
        mode: UninstallMode = UninstallMode.SIMPLE,
        method: UninstallMethod = UninstallMethod.APPLICATION,
        selected_item_ids: set[str] | None = None,
    ) -> Iterator[UninstallProgress]:
        """卸载应用并同时向 core 事件总线发布进度。"""
        try:
            method = UninstallMethod(method)
        except (TypeError, ValueError) as error:
            raise ValueError(f"不支持的软件卸载方式: {method}") from error
        for progress in self._uninstall(
            shortcut_path,
            mode=mode,
            method=method,
            selected_item_ids=selected_item_ids,
        ):
            if self._event_publisher is not None:
                self._event_publisher.publish(
                    UninstallProgressEvent(progress=progress)
                )
            yield progress

    def _uninstall_official(
        self,
        uninstall: Uninstall,
    ) -> Iterator[UninstallProgress]:
        """执行用户明确选择的官方卸载器，不再执行本应用清理。"""
        commands = uninstall.uninstall_commands
        total_items = len(commands)
        completed_items = 0
        errors: list[str] = []

        yield UninstallProgress(
            phase=UninstallPhase.INSPECTING,
            progress=0,
            current_directory=uninstall.dir,
            current_path=uninstall.id,
            application_id=uninstall.id,
            message="已检测到官方卸载器，准备按用户选择执行",
        )

        if not commands:
            errors.append("未检测到官方卸载器")
        elif self._process_runner is None:
            errors.append("未配置进程执行后端，无法运行官方卸载器")

        for command in commands:
            if errors:
                break
            yield self._progress(
                phase=UninstallPhase.RUNNING_UNINSTALLER,
                path=command.working_dir or uninstall.dir,
                completed_items=completed_items,
                total_items=total_items,
                message=f"正在运行官方卸载器: {command.command}",
            )
            try:
                assert self._process_runner is not None
                result = self._process_runner.run(
                    command.command,
                    working_dir=command.working_dir,
                )
            except Exception as error:
                errors.append(str(error))
                yield self._failed_progress(
                    phase=UninstallPhase.RUNNING_UNINSTALLER,
                    path=command.working_dir or uninstall.dir,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=str(error),
                )
                continue

            completed_items += 1
            if result.return_code != 0:
                error = f"官方卸载器返回错误码 {result.return_code}"
                errors.append(error)
                yield self._failed_progress(
                    phase=UninstallPhase.RUNNING_UNINSTALLER,
                    path=command.working_dir or uninstall.dir,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=error,
                )
            else:
                yield self._progress(
                    phase=UninstallPhase.RUNNING_UNINSTALLER,
                    path=command.working_dir or uninstall.dir,
                    completed_items=completed_items,
                    total_items=total_items,
                    message="官方卸载器执行完成",
                )

        if errors:
            yield UninstallProgress(
                phase=UninstallPhase.FAILED,
                progress=100,
                current_directory=uninstall.dir,
                application_id=uninstall.id,
                completed_items=completed_items,
                total_items=total_items,
                message="官方卸载器执行失败",
                succeeded=False,
                error="; ".join(errors),
            )
        else:
            yield UninstallProgress(
                phase=UninstallPhase.COMPLETED,
                progress=100,
                current_directory=uninstall.dir,
                application_id=uninstall.id,
                completed_items=completed_items,
                total_items=total_items,
                message="官方卸载器执行完成，未执行本应用的额外清理",
            )

    def _uninstall(
        self,
        shortcut_path: PathLike,
        *,
        mode: UninstallMode,
        method: UninstallMethod,
        selected_item_ids: set[str] | None,
    ) -> Iterator[UninstallProgress]:
        """卸载快捷方式对应的应用，并实时返回清理进度。"""
        plan = self.create_plan(shortcut_path, mode=mode)
        uninstall = plan.application
        if method is UninstallMethod.OFFICIAL:
            yield from self._uninstall_official(uninstall)
            return
        selected_ids = (
            selected_item_ids
            if mode is UninstallMode.STANDARD and selected_item_ids is not None
            else {
                item.id
                for item in plan.items
                if (
                    item.allowed_in_simple
                    if mode is UninstallMode.SIMPLE
                    else item.selected_by_default
                )
            }
        )
        yield UninstallProgress(
            phase=UninstallPhase.INSPECTING,
            progress=0,
            current_directory=str(Path(uninstall.id).parent),
            current_path=uninstall.id,
            application_id=uninstall.id,
            message="已识别应用，准备清理",
        )

        paths = [
            path
            for index, path in enumerate(self._cleanup_paths(uninstall))
            if f"path:{index}" in selected_ids
        ]
        registry_locations = [
            (f"registry:{index}", location)
            for index, location in enumerate(uninstall.registry_keys)
            if f"registry:{index}" in selected_ids
        ]
        total_items = sum(self._count_items(path) for path in paths)
        total_items += sum(
            len(location.value_names) if location.value_names else 1
            for _, location in registry_locations
        )
        completed_items = 0
        errors: list[str] = []

        for path in paths:
            yield self._progress(
                phase=UninstallPhase.REMOVING_FILES,
                path=path,
                completed_items=completed_items,
                total_items=total_items,
                message=f"正在清理目录: {path}",
            )
            try:
                completed_ref = [completed_items]
                for progress in self._remove_path(
                    Path(path),
                    phase=UninstallPhase.REMOVING_FILES,
                    completed_ref=completed_ref,
                    total_items=total_items,
                ):
                    completed_items = progress.completed_items
                    yield progress
            except Exception as error:
                errors.append(f"{path}: {error}")
                yield self._failed_progress(
                    phase=UninstallPhase.REMOVING_FILES,
                    path=path,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=str(error),
                )

        for _, location in registry_locations:
            if self._registry is None:
                error = "未配置注册表后端，无法清理注册表"
                errors.append(error)
                yield self._failed_progress(
                    phase=UninstallPhase.REMOVING_REGISTRY,
                    path=location.path,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=error,
                )
                continue
            try:
                if location.value_names:
                    for value_name in location.value_names:
                        self._registry.delete_value(
                            location.hive,
                            location.path,
                            value_name,
                        )
                        completed_items += 1
                        yield self._progress(
                            phase=UninstallPhase.REMOVING_REGISTRY,
                            path=f"{location.hive.value}\\{location.path}\\{value_name}",
                            completed_items=completed_items,
                            total_items=total_items,
                            message="正在清理注册表值",
                        )
                else:
                    self._registry.delete_key(
                        location.hive,
                        location.path,
                        recursive=location.recursive,
                    )
                    completed_items += 1
                    yield self._progress(
                        phase=UninstallPhase.REMOVING_REGISTRY,
                        path=f"{location.hive.value}\\{location.path}",
                        completed_items=completed_items,
                        total_items=total_items,
                        message="正在清理注册表项",
                    )
            except Exception as error:
                errors.append(f"{location.path}: {error}")
                yield self._failed_progress(
                    phase=UninstallPhase.REMOVING_REGISTRY,
                    path=location.path,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=str(error),
                )

        yield from self._final_progress(
            uninstall,
            completed_items=completed_items,
            total_items=total_items,
            errors=errors,
        )

    def _final_progress(
        self,
        uninstall: Uninstall,
        *,
        completed_items: int,
        total_items: int,
        errors: list[str],
    ) -> Iterator[UninstallProgress]:
        if errors:
            yield UninstallProgress(
                phase=UninstallPhase.FAILED,
                progress=100,
                current_directory=uninstall.dir,
                application_id=uninstall.id,
                completed_items=completed_items,
                total_items=total_items,
                message="卸载完成，但有部分项目清理失败",
                succeeded=False,
                error="; ".join(errors),
            )
        else:
            yield UninstallProgress(
                phase=UninstallPhase.COMPLETED,
                progress=100,
                current_directory=uninstall.dir,
                application_id=uninstall.id,
                completed_items=completed_items,
                total_items=total_items,
                message="应用及其快捷方式已清理完成",
            )

    def _remove_path(
        self,
        path: Path,
        *,
        phase: UninstallPhase,
        completed_ref: list[int],
        total_items: int,
    ) -> Iterator[UninstallProgress]:
        if not self._filesystem.exists(path):
            return
        if self._filesystem.is_dir(path):
            for child in self._filesystem.list_dir(path):
                yield from self._remove_path(
                    child,
                    phase=phase,
                    completed_ref=completed_ref,
                    total_items=total_items,
                )
            self._filesystem.remove_dir(path)
        else:
            self._filesystem.remove_file(path)
        completed_ref[0] += 1
        yield self._progress(
            phase=phase,
            path=path,
            completed_items=completed_ref[0],
            total_items=total_items,
            message=f"已清理: {path}",
        )

    def _count_items(self, path: PathLike) -> int:
        path_object = Path(path)
        if not self._filesystem.exists(path_object):
            return 0
        if not self._filesystem.is_dir(path_object):
            return 1
        return 1 + sum(
            self._count_items(child)
            for child in self._filesystem.list_dir(path_object)
        )

    def _cleanup_paths(self, uninstall: Uninstall) -> tuple[str, ...]:
        candidates = (
            uninstall.shortcut_paths
            + [uninstall.dir]
            + uninstall.program_data_dirs
            + uninstall.app_data_dirs
            + uninstall.cache_dirs
        )
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = os.path.normcase(os.path.abspath(candidate))
            if normalized not in seen:
                seen.add(normalized)
                unique.append(candidate)
        return tuple(unique)

    def _progress(
        self,
        *,
        phase: UninstallPhase,
        path: PathLike,
        completed_items: int,
        total_items: int,
        message: str,
    ) -> UninstallProgress:
        progress = 100.0 if total_items == 0 else completed_items / total_items * 100
        path_object = Path(path)
        return UninstallProgress(
            phase=phase,
            progress=min(100.0, progress),
            current_directory=str(self._current_directory(path_object)),
            current_path=str(path_object),
            completed_items=completed_items,
            total_items=total_items,
            message=message,
        )

    def _failed_progress(
        self,
        *,
        phase: UninstallPhase,
        path: PathLike,
        completed_items: int,
        total_items: int,
        error: str,
    ) -> UninstallProgress:
        progress = 100.0 if total_items == 0 else completed_items / total_items * 100
        path_object = Path(path)
        return UninstallProgress(
            phase=phase,
            progress=min(100.0, progress),
            current_directory=str(self._current_directory(path_object)),
            current_path=str(path_object),
            completed_items=completed_items,
            total_items=total_items,
            message="清理项目失败，继续处理其他项目",
            succeeded=False,
            error=error,
        )

    def _current_directory(self, path: Path) -> Path:
        if self._filesystem.exists(path) and self._filesystem.is_dir(path):
            return path
        return path.parent

    def _resolve_install_dir(self, shortcut: ShortcutInfo, target: Path) -> Path:
        if shortcut.working_directory and self._filesystem.is_dir(
            shortcut.working_directory
        ):
            return shortcut.working_directory
        return target.parent

    def _prefer_registry_install_dir(
        self,
        fallback: Path,
        records: list[UninstallRegistryRecord],
        target_path: Path,
    ) -> Path:
        target_key = self._path_key(target_path)
        for record in records:
            if not record.install_location:
                continue
            candidate = Path(record.install_location)
            candidate_key = self._path_key(candidate)
            target_in_candidate = target_key.startswith(candidate_key + os.sep)
            if target_key == candidate_key or target_in_candidate:
                if self._filesystem.is_dir(candidate):
                    return candidate
        return fallback

    def _find_related_shortcuts(
        self,
        shortcut: ShortcutInfo,
        target: Path,
    ) -> list[Path]:
        result: list[Path] = []
        target_key = self._path_key(target)
        for root in self._shortcut_roots():
            for candidate in self._iter_files(root):
                if candidate.suffix.lower() != ".lnk":
                    continue
                try:
                    candidate_info = self._shortcut_resolver.resolve(candidate)
                except (OSError, ValueError):
                    continue
                if self._path_key(candidate_info.target_path) == target_key:
                    result.append(candidate)
        return result

    def _find_registry_records(
        self,
        *,
        shortcut_name: str,
        target_path: Path,
        install_dir: Path,
    ) -> list[UninstallRegistryRecord]:
        return [
            record
            for record in self._all_registry_records()
            if self._record_matches(
                record,
                shortcut_name=shortcut_name,
                target_path=target_path,
                install_dir=install_dir,
            )
        ]

    def _all_registry_records(self) -> list[UninstallRegistryRecord]:
        """读取所有卸载注册表记录，不按快捷方式名称合并。"""
        if self._registry is None:
            return []
        records: list[UninstallRegistryRecord] = []
        for hive, root in _UNINSTALL_REGISTRY_PATHS:
            if not self._registry.key_exists(hive, root):
                continue
            for child in self._registry.list_subkeys(hive, root):
                path = f"{root}\\{child}"
                values = self._read_registry_values(hive, path)
                record = self._record_from_values(hive, path, values)
                if record is not None:
                    records.append(record)
        return records

    def _read_registry_values(
        self,
        hive: RegistryHive,
        path: str,
    ) -> dict[str, object]:
        assert self._registry is not None
        return {
            value.name.casefold(): value.data
            for value in self._registry.list_values(hive, path)
        }

    def _record_from_values(
        self,
        hive: RegistryHive,
        path: str,
        values: dict[str, object],
    ) -> UninstallRegistryRecord | None:
        display_name = self._as_text(values.get("displayname"))
        if not display_name:
            return None
        return UninstallRegistryRecord(
            hive=hive,
            path=path,
            display_name=display_name,
            display_version=self._as_text(values.get("displayversion")),
            publisher=self._as_text(values.get("publisher")),
            install_location=self._as_text(values.get("installlocation")),
            display_icon=self._as_text(values.get("displayicon")),
            uninstall_string=self._as_text(values.get("uninstallstring")),
            quiet_uninstall_string=self._as_text(values.get("quietuninstallstring")),
            estimated_size_kb=self._as_int(values.get("estimatedsize")),
            windows_installer=bool(values.get("windowsinstaller", False)),
            system_component=bool(values.get("systemcomponent", False)),
            no_modify=bool(values.get("nomodify", False)),
            no_remove=bool(values.get("noremove", False)),
            install_date=self._as_text(values.get("installdate")),
        )

    def _record_matches(
        self,
        record: UninstallRegistryRecord,
        *,
        shortcut_name: str,
        target_path: Path,
        install_dir: Path,
    ) -> bool:
        target_key = self._path_key(target_path)
        install_key = self._path_key(install_dir)
        if record.install_location:
            record_install_key = self._path_key(Path(record.install_location))
            target_in_install_dir = target_key.startswith(record_install_key + os.sep)
            if install_key == record_install_key or target_in_install_dir:
                return True
        display_name = (record.display_name or "").casefold()
        return display_name == shortcut_name.casefold()

    def _commands_from_records(
        self,
        records: list[UninstallRegistryRecord],
    ) -> list[UninstallCommand]:
        commands: list[UninstallCommand] = []
        seen: set[str] = set()
        for record in records:
            command = record.quiet_uninstall_string or record.uninstall_string
            if not command or record.no_remove:
                continue
            if command.casefold() in seen:
                continue
            seen.add(command.casefold())
            commands.append(
                UninstallCommand(
                    command=command,
                    quiet_command=record.quiet_uninstall_string,
                    working_dir=record.install_location,
                )
            )
        return commands

    def _registry_operation_count(self, uninstall: Uninstall) -> int:
        return sum(
            len(location.value_names) if location.value_names else 1
            for location in uninstall.registry_keys
        )

    def _shortcut_roots(self) -> tuple[Path, ...]:
        home = Path.home()
        app_data = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        return (
            home / "Desktop",
            Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
            app_data / "Microsoft/Windows/Start Menu/Programs",
            program_data / "Microsoft/Windows/Start Menu/Programs",
        )

    def _iter_files(self, root: Path) -> Iterator[Path]:
        if not self._filesystem.exists(root) or not self._filesystem.is_dir(root):
            return
        for child in self._filesystem.list_dir(root):
            if self._filesystem.is_dir(child):
                yield from self._iter_files(child)
            else:
                yield child

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(os.path.normpath(str(path)))

    @staticmethod
    def _as_text(value: object) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _as_int(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None


class WindowsSoftwareUninstaller(SoftwareUninstaller):
    """使用默认 Windows 后端的卸载器。"""

    def __init__(
        self,
        windows_io: WindowsIO | None = None,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        windows_io = windows_io or WindowsIO()
        super().__init__(
            windows_io.filesystem,
            windows_io.shortcut_resolver,
            registry=windows_io.registry,
            process_runner=windows_io.process_runner,
            event_publisher=event_publisher or windows_io.event_publisher,
        )


__all__ = ["SoftwareUninstaller", "WindowsSoftwareUninstaller"]
