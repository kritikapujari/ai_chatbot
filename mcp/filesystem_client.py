from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import os


@dataclass
class FileResult:
    tool: str
    success: bool
    data: Any = None
    error: Optional[str] = None

    def format_for_llm(self) -> str:
        if not self.success:
            return f"[Tool Error] {self.tool}: {self.error}"

        if isinstance(self.data, str):
            return self.data

        return str(self.data)


class FileSystemClient:

    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()

    def _safe_path(self, path: str) -> Path:
        candidate = (self.workspace / path).resolve()

        # Prevent ../../ escape
        if not str(candidate).startswith(str(self.workspace)):
            raise PermissionError(
                "Path is outside the configured workspace."
            )

        return candidate

    def execute(self, tool_name: str, args: Dict[str, Any]) -> FileResult:

        try:
            handler = getattr(self, f"_tool_{tool_name}", None)

            if handler is None:
                return FileResult(
                    tool=tool_name,
                    success=False,
                    error=f"Unknown filesystem tool: {tool_name}",
                )

            return handler(**args)

        except Exception as exc:
            return FileResult(
                tool=tool_name,
                success=False,
                error=str(exc),
            )

    def _tool_list_directory(
        self,
        path: str = ".",
    ) -> FileResult:

        directory = self._safe_path(path)

        if not directory.exists():
            return FileResult(
                tool="list_directory",
                success=False,
                error=f"Directory does not exist: {path}",
            )

        items = []

        for item in directory.iterdir():
            items.append({
                "name": item.name,
                "path": str(item.relative_to(self.workspace)),
                "type": "directory" if item.is_dir() else "file",
            })

        return FileResult(
            tool="list_directory",
            success=True,
            data=items,
        )

    def _tool_read_file(
        self,
        path: str,
    ) -> FileResult:

        file_path = self._safe_path(path)

        if not file_path.is_file():
            return FileResult(
                tool="read_file",
                success=False,
                error=f"File does not exist: {path}",
            )

        content = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return FileResult(
            tool="read_file",
            success=True,
            data=content,
        )

    def _tool_write_file(
        self,
        path: str,
        content: str,
    ) -> FileResult:

        file_path = self._safe_path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.write_text(
            content,
            encoding="utf-8",
        )

        return FileResult(
            tool="write_file",
            success=True,
            data=f"File written successfully: {path}",
        )

    def _tool_delete_file(
        self,
        path: str,
    ) -> FileResult:

        file_path = self._safe_path(path)

        if not file_path.exists():
            return FileResult(
                tool="delete_file",
                success=False,
                error=f"File does not exist: {path}",
            )

        file_path.unlink()

        return FileResult(
            tool="delete_file",
            success=True,
            data=f"Deleted: {path}",
        )