"""通过桌面快捷方式发现并卸载 Windows 应用。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

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
    RegistryLocation,
    Uninstall,
    UninstallCommand,
    UninstallPhase,
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


class SoftwareUninstaller:
    """可替换 Windows I/O 后端的应用卸载编排器。

    ``uninstall`` 是同步生成器：调用方可以在每个文件、目录或注册表项
    处理完成后立即拿到一个 ``UninstallProgress``，适合直接接 UI 或 RPC
    的流式响应。
    """

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

    def uninstall(self, shortcut_path: PathLike) -> Iterator[UninstallProgress]:
        """卸载应用并同时向 core 事件总线发布进度。"""
        for progress in self._uninstall(shortcut_path):
            if self._event_publisher is not None:
                self._event_publisher.publish(UninstallProgressEvent(progress))
            yield progress

    def _uninstall(self, shortcut_path: PathLike) -> Iterator[UninstallProgress]:
        """卸载快捷方式对应的应用，并实时返回清理进度。"""
        uninstall = self.inspect(shortcut_path)
        yield UninstallProgress(
            phase=UninstallPhase.INSPECTING,
            progress=0,
            current_directory=str(Path(uninstall.id).parent),
            current_path=uninstall.id,
            message="已识别应用，准备清理",
        )

        paths = self._cleanup_paths(uninstall)
        total_items = sum(self._count_items(path) for path in paths)
        total_items += len(uninstall.uninstall_commands)
        total_items += self._registry_operation_count(uninstall)
        completed_items = 0
        errors: list[str] = []

        for command in uninstall.uninstall_commands:
            yield self._progress(
                phase=UninstallPhase.RUNNING_UNINSTALLER,
                path=command.working_dir or uninstall.dir,
                completed_items=completed_items,
                total_items=total_items,
                message=f"正在运行卸载程序: {command.command}",
            )
            if self._process_runner is None:
                error = "未配置进程执行后端，无法运行官方卸载程序"
                errors.append(error)
                yield self._failed_progress(
                    phase=UninstallPhase.RUNNING_UNINSTALLER,
                    path=command.working_dir or uninstall.dir,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=error,
                )
                continue
            try:
                result = self._process_runner.run(
                    command.command,
                    working_dir=command.working_dir,
                )
                completed_items += 1
                if result.return_code != 0:
                    error = f"卸载程序返回错误码 {result.return_code}"
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
                        message="官方卸载程序执行完成",
                    )
            except Exception as error:
                errors.append(str(error))
                completed_items += 1
                yield self._failed_progress(
                    phase=UninstallPhase.RUNNING_UNINSTALLER,
                    path=command.working_dir or uninstall.dir,
                    completed_items=completed_items,
                    total_items=total_items,
                    error=str(error),
                )

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

        for location in uninstall.registry_keys:
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

        if errors:
            yield UninstallProgress(
                phase=UninstallPhase.FAILED,
                progress=100,
                current_directory=uninstall.dir,
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
                if record is None or not self._record_matches(
                    record,
                    shortcut_name=shortcut_name,
                    target_path=target_path,
                    install_dir=install_dir,
                ):
                    continue
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
