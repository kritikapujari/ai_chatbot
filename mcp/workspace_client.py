"""
mcp/workspace_client.py

Local workspace tools for the agent.

This is what allows the agent to behave more like Claude Code:
- inspect project directories
- search text/code across the project
- read files
- create files
- modify files
- delete files
- run development commands
- inspect command output

IMPORTANT:
All WRITE and COMMAND operations must be approved by the orchestrator.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .github_client import ToolResult


class WorkspaceClient:
    """
    Executes tools against the local project workspace.

    workspace_root should normally be the directory containing
    the chatbot/project being worked on.
    """

    MAX_FILE_SIZE = 2 * 1024 * 1024
    MAX_SEARCH_RESULTS = 200
    MAX_OUTPUT = 20000

    IGNORED_DIRECTORIES = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".next",
        "dist",
        "build",
        ".idea",
        ".vscode",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
    }

    BINARY_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
        ".so",
        ".bin",
        ".mp4",
        ".mov",
        ".avi",
        ".mp3",
        ".wav",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
    }

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()

        if not self.workspace_root.exists():
            raise ValueError(
                f"Workspace does not exist: {self.workspace_root}"
            )

        if not self.workspace_root.is_dir():
            raise ValueError(
                f"Workspace is not a directory: {self.workspace_root}"
            )

    # ------------------------------------------------------------------
    # SECURITY
    # ------------------------------------------------------------------

    def _safe_path(self, path: str) -> Path:
        """
        Resolve a user/agent supplied path and prevent path traversal.
        """

        if not path:
            path = "."

        candidate = (self.workspace_root / path).resolve()

        try:
            candidate.relative_to(self.workspace_root)
        except ValueError:
            raise ValueError(
                "Access denied: path is outside the workspace."
            )

        return candidate

    def _relative(self, path: Path) -> str:
        return str(path.relative_to(self.workspace_root)).replace("\\", "/")

    def _is_binary(self, path: Path) -> bool:
        return path.suffix.lower() in self.BINARY_EXTENSIONS

    def _should_ignore(self, path: Path) -> bool:
        return any(
            part in self.IGNORED_DIRECTORIES
            for part in path.parts
        )

    # ------------------------------------------------------------------
    # READ: LIST DIRECTORY
    # ------------------------------------------------------------------

    def _tool_list_directory(
        self,
        path: str = ".",
        recursive: bool = False,
    ) -> ToolResult:

        try:
            directory = self._safe_path(path)

            if not directory.exists():
                return ToolResult(
                    tool="list_directory",
                    success=False,
                    data=None,
                    error=f"Directory does not exist: {path}",
                )

            if not directory.is_dir():
                return ToolResult(
                    tool="list_directory",
                    success=False,
                    data=None,
                    error=f"Not a directory: {path}",
                )

            items = []

            if recursive:
                iterator = directory.rglob("*")
            else:
                iterator = directory.iterdir()

            for item in iterator:
                if self._should_ignore(item):
                    continue

                try:
                    relative = self._relative(item)
                    stat = item.stat()

                    items.append({
                        "path": relative,
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                    })

                except OSError:
                    continue

                if len(items) >= 1000:
                    break

            items.sort(key=lambda x: x["path"])

            text = (
                f"Directory listing: {self._relative(directory)}\n\n"
                + "\n".join(
                    f"[{item['type']}] {item['path']}"
                    for item in items
                )
            )

            return ToolResult(
                tool="list_directory",
                success=True,
                data=items,
                raw_text=text,
            )

        except Exception as exc:
            return ToolResult(
                tool="list_directory",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # READ: FILE
    # ------------------------------------------------------------------

    def _tool_read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> ToolResult:

        try:
            file_path = self._safe_path(path)

            if not file_path.exists():
                return ToolResult(
                    tool="read_file",
                    success=False,
                    data=None,
                    error=f"File does not exist: {path}",
                )

            if not file_path.is_file():
                return ToolResult(
                    tool="read_file",
                    success=False,
                    data=None,
                    error=f"Not a file: {path}",
                )

            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                return ToolResult(
                    tool="read_file",
                    success=False,
                    data=None,
                    error=(
                        f"File is too large to read directly "
                        f"({file_path.stat().st_size} bytes). "
                        f"Use search_text or targeted reading."
                    ),
                )

            if self._is_binary(file_path):
                return ToolResult(
                    tool="read_file",
                    success=False,
                    data=None,
                    error=f"Binary file cannot be read as text: {path}",
                )

            content = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            lines = content.splitlines()

            start = max(start_line - 1, 0)

            if end_line is None:
                selected = lines[start:]
            else:
                selected = lines[start:end_line]

            numbered = "\n".join(
                f"{i + start + 1}: {line}"
                for i, line in enumerate(selected)
            )

            return ToolResult(
                tool="read_file",
                success=True,
                data={
                    "path": path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "content": "\n".join(selected),
                },
                raw_text=f"File: {path}\n\n{numbered}",
            )

        except Exception as exc:
            return ToolResult(
                tool="read_file",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # READ: SEARCH TEXT / CODE
    # ------------------------------------------------------------------

    def _tool_search_text(
        self,
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        case_sensitive: bool = False,
        use_regex: bool = False,
    ) -> ToolResult:

        try:
            if not query:
                return ToolResult(
                    tool="search_text",
                    success=False,
                    data=None,
                    error="Search query cannot be empty.",
                )

            root = self._safe_path(path)

            if not root.exists():
                return ToolResult(
                    tool="search_text",
                    success=False,
                    data=None,
                    error=f"Search path does not exist: {path}",
                )

            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE

                try:
                    pattern = re.compile(query, flags)
                except re.error as exc:
                    return ToolResult(
                        tool="search_text",
                        success=False,
                        data=None,
                        error=f"Invalid regex: {exc}",
                    )
            else:
                pattern = None
                search_query = (
                    query if case_sensitive else query.lower()
                )

            results: List[Dict[str, Any]] = []

            files = root.rglob("*") if root.is_dir() else [root]

            for file_path in files:

                if len(results) >= self.MAX_SEARCH_RESULTS:
                    break

                if not file_path.is_file():
                    continue

                if self._should_ignore(file_path):
                    continue

                if not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue

                if self._is_binary(file_path):
                    continue

                try:
                    if file_path.stat().st_size > self.MAX_FILE_SIZE:
                        continue

                    content = file_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )

                    lines = content.splitlines()

                    for line_number, line in enumerate(
                        lines,
                        start=1,
                    ):

                        matched = False

                        if pattern:
                            matched = bool(pattern.search(line))
                        else:
                            value = (
                                line
                                if case_sensitive
                                else line.lower()
                            )

                            matched = search_query in value

                        if matched:

                            results.append({
                                "path": self._relative(file_path),
                                "line": line_number,
                                "text": line[:1000],
                            })

                            if len(results) >= self.MAX_SEARCH_RESULTS:
                                break

                except (
                    UnicodeDecodeError,
                    PermissionError,
                    OSError,
                ):
                    continue

            text = (
                f"Search results for: {query}\n"
                f"Path: {path}\n"
                f"Matches: {len(results)}\n\n"
            )

            text += "\n".join(
                f"{r['path']}:{r['line']}: {r['text']}"
                for r in results
            )

            if len(results) >= self.MAX_SEARCH_RESULTS:
                text += (
                    "\n\n[Search result limit reached. "
                    "Narrow the query.]"
                )

            return ToolResult(
                tool="search_text",
                success=True,
                data=results,
                raw_text=text,
            )

        except Exception as exc:
            return ToolResult(
                tool="search_text",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # READ: FIND FILES
    # ------------------------------------------------------------------

    def _tool_find_files(
        self,
        pattern: str,
        path: str = ".",
    ) -> ToolResult:

        try:
            root = self._safe_path(path)

            matches = []

            for file_path in root.rglob("*"):

                if len(matches) >= 500:
                    break

                if not file_path.is_file():
                    continue

                if self._should_ignore(file_path):
                    continue

                if fnmatch.fnmatch(file_path.name, pattern):
                    matches.append(self._relative(file_path))

            matches.sort()

            return ToolResult(
                tool="find_files",
                success=True,
                data=matches,
                raw_text=(
                    f"Files matching '{pattern}':\n\n"
                    + "\n".join(matches)
                ),
            )

        except Exception as exc:
            return ToolResult(
                tool="find_files",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # WRITE: WRITE FILE
    # ------------------------------------------------------------------

    def _tool_write_file(
        self,
        path: str,
        content: str,
    ) -> ToolResult:

        try:
            file_path = self._safe_path(path)

            file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            file_path.write_text(
                content,
                encoding="utf-8",
            )

            return ToolResult(
                tool="write_file",
                success=True,
                data={
                    "path": path,
                    "size": len(content.encode("utf-8")),
                },
                raw_text=(
                    f"File written successfully: {path}"
                ),
            )

        except Exception as exc:
            return ToolResult(
                tool="write_file",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # WRITE: DELETE FILE
    # ------------------------------------------------------------------

    def _tool_delete_file(
        self,
        path: str,
    ) -> ToolResult:

        try:
            file_path = self._safe_path(path)

            if not file_path.exists():
                return ToolResult(
                    tool="delete_file",
                    success=False,
                    data=None,
                    error=f"File does not exist: {path}",
                )

            if not file_path.is_file():
                return ToolResult(
                    tool="delete_file",
                    success=False,
                    data=None,
                    error=f"Not a file: {path}",
                )

            file_path.unlink()

            return ToolResult(
                tool="delete_file",
                success=True,
                data={"path": path},
                raw_text=f"Deleted file: {path}",
            )

        except Exception as exc:
            return ToolResult(
                tool="delete_file",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # COMMAND EXECUTION
    # ------------------------------------------------------------------

    def _tool_run_command(
        self,
        command: str,
        timeout: int = 120,
    ) -> ToolResult:

        try:
            if not command.strip():
                return ToolResult(
                    tool="run_command",
                    success=False,
                    data=None,
                    error="Command cannot be empty.",
                )

            # Basic command timeout protection.
            timeout = max(1, min(timeout, 600))

            result = subprocess.run(
                command,
                cwd=str(self.workspace_root),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            output = (
                f"Exit code: {result.returncode}\n\n"
                f"STDOUT:\n{stdout}\n\n"
                f"STDERR:\n{stderr}"
            )

            output = output[-self.MAX_OUTPUT:]

            return ToolResult(
                tool="run_command",
                success=result.returncode == 0,
                data={
                    "exit_code": result.returncode,
                    "stdout": stdout[-10000:],
                    "stderr": stderr[-10000:],
                },
                raw_text=output,
                error=(
                    None
                    if result.returncode == 0
                    else f"Command exited with code {result.returncode}"
                ),
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool="run_command",
                success=False,
                data=None,
                error=f"Command timed out after {timeout} seconds.",
            )

        except Exception as exc:
            return ToolResult(
                tool="run_command",
                success=False,
                data=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # DISPATCH
    # ------------------------------------------------------------------

    def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> ToolResult:

        handler = getattr(
            self,
            f"_tool_{tool_name}",
            None,
        )

        if handler is None:
            return ToolResult(
                tool=tool_name,
                success=False,
                data=None,
                error=f"Workspace tool '{tool_name}' is not implemented.",
            )

        try:
            return handler(**args)
        except Exception as exc:
            return ToolResult(
                tool=tool_name,
                success=False,
                data=None,
                error=str(exc),
            )