"""
mcp/tool_registry.py

Central registry for the agent.

The agent can operate across:

    LOCAL WORKSPACE
        - list files/directories
        - read files
        - write/create files
        - delete files
        - move/rename files
        - search text/code
        - inspect file metadata

    TERMINAL / SHELL
        - run commands
        - run tests
        - install dependencies
        - inspect git
        - build projects

    GITHUB
        - repositories
        - files
        - code search
        - issues
        - pull requests
        - branches
        - commits
        - file writes

    WEB
        - web search
        - webpage fetching

IMPORTANT:
    This file only DEFINES the tools.

The actual implementation must exist in the corresponding executor,
for example:

    local_file_client.py
    shell_client.py
    github_client.py
    web_client.py

The agent should NEVER directly manipulate files or execute commands.
Everything goes through registered tools.

Security model:

    READ
        Can execute automatically.

    WRITE
        Requires user approval unless the application explicitly enables
        trusted/autonomous mode.

    DESTRUCTIVE
        Always requires explicit user approval.

Local filesystem access should be restricted to the configured workspace
directory. Do NOT allow arbitrary paths such as C:\\Windows or /etc unless
the application explicitly opts into that behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


OperationType = Literal[
    "read",
    "write",
    "destructive",
]


# ============================================================================
# TOOL DEFINITION
# ============================================================================

@dataclass
class ToolDefinition:
    """Schema for a single agent tool."""

    name: str
    description: str
    operation_type: OperationType
    parameters: Dict[str, Any]
    required_params: List[str] = field(default_factory=list)

    @property
    def is_write(self) -> bool:
        return self.operation_type in ("write", "destructive")

    @property
    def is_destructive(self) -> bool:
        return self.operation_type == "destructive"

    def to_openai_function(self) -> Dict[str, Any]:
        """
        Convert to OpenAI/OpenRouter-compatible function schema.

        The same schema can be supplied to models that support
        OpenAI-style tool calling.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params,
                    "additionalProperties": False,
                },
            },
        }


# ============================================================================
# TOOL CATALOGUE
# ============================================================================

_TOOLS: List[ToolDefinition] = [

    # ========================================================================
    # LOCAL WORKSPACE — READ
    # ========================================================================

    ToolDefinition(
        name="list_directory",
        description=(
            "Lists files and directories inside the current project workspace. "
            "Use this to understand project structure before modifying files."
        ),
        operation_type="read",
        parameters={
            "path": {
                "type": "string",
                "description": (
                    "Relative path inside the workspace. "
                    "Use '.' for the workspace root."
                ),
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to recursively list nested files.",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum recursive depth.",
            },
        },
        required_params=["path"],
    ),

    ToolDefinition(
        name="read_file",
        description=(
            "Reads the complete contents of a local project file. "
            "Use this when you need to understand or modify source code, "
            "configuration, documentation, JSON, YAML, CSV, Markdown, etc."
        ),
        operation_type="read",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional starting line number.",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional ending line number.",
            },
        },
        required_params=["path"],
    ),

    ToolDefinition(
        name="file_info",
        description=(
            "Gets metadata about a local file or directory, including "
            "size, type, timestamps, and path."
        ),
        operation_type="read",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative path inside the workspace.",
            },
        },
        required_params=["path"],
    ),

    # ========================================================================
    # LOCAL WORKSPACE — SEARCH
    # ========================================================================

    ToolDefinition(
        name="search_text",
        description=(
            "Searches for text across files in the local project workspace. "
            "Use this to find function names, variables, imports, API routes, "
            "configuration values, error messages, TODOs, class names, or any "
            "other exact/partial text. This is one of the primary tools for "
            "understanding an unfamiliar codebase."
        ),
        operation_type="read",
        parameters={
            "query": {
                "type": "string",
                "description": "Text, phrase, symbol, or regex to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory/file to search inside. Defaults to '.'.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether the search should be case-sensitive.",
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat query as a regular expression.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of matching lines/files.",
            },
        },
        required_params=["query"],
    ),

    ToolDefinition(
        name="search_code",
        description=(
            "Searches source code in the local workspace. "
            "Use this for code symbols, functions, classes, imports, API "
            "endpoints, environment variables, model names, database queries, "
            "and implementation patterns. Prefer this over blindly reading "
            "every file in a large repository."
        ),
        operation_type="read",
        parameters={
            "query": {
                "type": "string",
                "description": "Code symbol, function, class, import, or pattern.",
            },
            "path": {
                "type": "string",
                "description": "Optional directory to search.",
            },
            "file_extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional extensions such as ['.py', '.js', '.ts', '.tsx']."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results.",
            },
        },
        required_params=["query"],
    ),

    ToolDefinition(
        name="find_files",
        description=(
            "Finds files in the workspace by filename, extension, or glob "
            "pattern. Use this when you know approximately what file you need."
        ),
        operation_type="read",
        parameters={
            "pattern": {
                "type": "string",
                "description": (
                    "Filename or glob pattern, for example '*.py', "
                    "'package.json', 'app.*', or '**/*.tsx'."
                ),
            },
            "path": {
                "type": "string",
                "description": "Directory from which to search.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results.",
            },
        },
        required_params=["pattern"],
    ),

    # ========================================================================
    # LOCAL WORKSPACE — WRITE
    # ========================================================================

    ToolDefinition(
        name="write_file",
        description=(
            "Creates or completely replaces a local workspace file. "
            "Use this after inspecting the existing file and determining "
            "the required changes."
        ),
        operation_type="write",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
            "content": {
                "type": "string",
                "description": "Complete new file contents.",
            },
        },
        required_params=["path", "content"],
    ),

    ToolDefinition(
        name="edit_file",
        description=(
            "Edits an existing local file by replacing an exact text block "
            "with new text. The old text must exist exactly once unless the "
            "tool implementation explicitly supports multiple replacements."
        ),
        operation_type="write",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative file path.",
            },
            "old_text": {
                "type": "string",
                "description": "Exact text that should be replaced.",
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text.",
            },
        },
        required_params=[
            "path",
            "old_text",
            "new_text",
        ],
    ),

    ToolDefinition(
        name="create_directory",
        description="Creates a directory inside the local workspace.",
        operation_type="write",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative directory path.",
            },
        },
        required_params=["path"],
    ),

    ToolDefinition(
        name="move_file",
        description=(
            "Moves or renames a file/directory inside the workspace."
        ),
        operation_type="write",
        parameters={
            "source": {
                "type": "string",
                "description": "Current relative path.",
            },
            "destination": {
                "type": "string",
                "description": "New relative path.",
            },
        },
        required_params=[
            "source",
            "destination",
        ],
    ),

    # ========================================================================
    # LOCAL WORKSPACE — DESTRUCTIVE
    # ========================================================================

    ToolDefinition(
        name="delete_file",
        description=(
            "Deletes a local workspace file or directory. "
            "This is destructive and always requires explicit user approval."
        ),
        operation_type="destructive",
        parameters={
            "path": {
                "type": "string",
                "description": "Relative path to delete.",
            },
            "recursive": {
                "type": "boolean",
                "description": "Required when deleting a non-empty directory.",
            },
        },
        required_params=["path"],
    ),

    # ========================================================================
    # TERMINAL / SHELL — READ
    # ========================================================================

    ToolDefinition(
        name="run_command",
        description=(
            "Runs a shell command inside the configured project workspace. "
            "Use this to inspect the project, run tests, run linters, build "
            "the application, check package versions, inspect git status, "
            "or execute project-specific development commands."
        ),
        operation_type="write",
        parameters={
            "command": {
                "type": "string",
                "description": "Command to execute.",
            },
            "working_directory": {
                "type": "string",
                "description": "Relative workspace directory.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds.",
            },
        },
        required_params=["command"],
    ),

    ToolDefinition(
        name="run_tests",
        description=(
            "Runs the project's test suite. The agent should use this after "
            "making code changes to verify that the implementation works."
        ),
        operation_type="write",
        parameters={
            "command": {
                "type": "string",
                "description": (
                    "Optional test command. If omitted, infer the project's "
                    "test runner from its configuration."
                ),
            },
            "working_directory": {
                "type": "string",
                "description": "Project directory.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time.",
            },
        },
        required_params=[],
    ),

    # ========================================================================
    # GIT — READ
    # ========================================================================

    ToolDefinition(
        name="git_status",
        description=(
            "Gets the current Git status of the local project."
        ),
        operation_type="read",
        parameters={},
        required_params=[],
    ),

    ToolDefinition(
        name="git_diff",
        description=(
            "Gets the current uncommitted Git diff so the agent can inspect "
            "changes before committing."
        ),
        operation_type="read",
        parameters={
            "staged": {
                "type": "boolean",
                "description": "Whether to show staged changes.",
            },
        },
        required_params=[],
    ),

    ToolDefinition(
        name="git_log",
        description="Gets recent Git commit history.",
        operation_type="read",
        parameters={
            "limit": {
                "type": "integer",
                "description": "Number of commits.",
            },
        },
        required_params=[],
    ),

    # ========================================================================
    # GIT — WRITE
    # ========================================================================

    ToolDefinition(
        name="git_create_branch",
        description="Creates a new local Git branch.",
        operation_type="write",
        parameters={
            "branch": {
                "type": "string",
                "description": "New branch name.",
            },
            "from_ref": {
                "type": "string",
                "description": "Optional source branch/commit.",
            },
        },
        required_params=["branch"],
    ),

    ToolDefinition(
        name="git_commit",
        description=(
            "Creates a Git commit containing the current staged changes."
        ),
        operation_type="write",
        parameters={
            "message": {
                "type": "string",
                "description": "Commit message.",
            },
        },
        required_params=["message"],
    ),

    ToolDefinition(
        name="git_push",
        description=(
            "Pushes local Git commits to a remote repository."
        ),
        operation_type="write",
        parameters={
            "remote": {
                "type": "string",
                "description": "Remote name, normally 'origin'.",
            },
            "branch": {
                "type": "string",
                "description": "Branch to push.",
            },
        },
        required_params=[],
    ),

    # ========================================================================
    # GITHUB — REPOSITORY READ
    # ========================================================================

    ToolDefinition(
        name="get_repository",
        description="Gets metadata and details about a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
        },
        required_params=["owner", "repo"],
    ),

    ToolDefinition(
        name="get_file_contents",
        description=(
            "Gets a file or directory from a GitHub repository."
        ),
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "ref": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "path",
        ],
    ),

    ToolDefinition(
        name="list_branches",
        description="Lists branches in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "page": {"type": "integer"},
            "per_page": {"type": "integer"},
        },
        required_params=["owner", "repo"],
    ),

    ToolDefinition(
        name="list_commits",
        description="Lists commits from a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "sha": {"type": "string"},
            "path": {"type": "string"},
            "author": {"type": "string"},
            "since": {"type": "string"},
            "until": {"type": "string"},
            "per_page": {"type": "integer"},
        },
        required_params=["owner", "repo"],
    ),

    ToolDefinition(
        name="get_commit",
        description="Gets detailed information about a GitHub commit.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "sha": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "sha",
        ],
    ),

    ToolDefinition(
        name="search_repositories",
        description="Searches GitHub repositories.",
        operation_type="read",
        parameters={
            "query": {"type": "string"},
            "page": {"type": "integer"},
            "per_page": {"type": "integer"},
        },
        required_params=["query"],
    ),

    ToolDefinition(
        name="list_tags",
        description="Lists tags in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "per_page": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
        ],
    ),

    # ========================================================================
    # GITHUB — CODE SEARCH
    # ========================================================================

    ToolDefinition(
        name="github_search_code",
        description=(
            "Searches source code across GitHub repositories. "
            "Use this when code may exist remotely and is not available "
            "in the local workspace."
        ),
        operation_type="read",
        parameters={
            "query": {
                "type": "string",
                "description": "GitHub code search query.",
            },
            "per_page": {
                "type": "integer",
                "description": "Maximum results.",
            },
        },
        required_params=["query"],
    ),

    # ========================================================================
    # GITHUB — ISSUES
    # ========================================================================

    ToolDefinition(
        name="list_issues",
        description="Lists issues in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
            },
            "labels": {"type": "string"},
            "assignee": {"type": "string"},
            "per_page": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
        ],
    ),

    ToolDefinition(
        name="get_issue",
        description="Gets a GitHub issue.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
            "issue_number",
        ],
    ),

    ToolDefinition(
        name="list_issue_comments",
        description="Lists comments on a GitHub issue.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
            "issue_number",
        ],
    ),

    ToolDefinition(
        name="search_issues",
        description="Searches GitHub issues and pull requests.",
        operation_type="read",
        parameters={
            "query": {"type": "string"},
            "per_page": {"type": "integer"},
        },
        required_params=["query"],
    ),

    # ========================================================================
    # GITHUB — PULL REQUESTS
    # ========================================================================

    ToolDefinition(
        name="list_pull_requests",
        description="Lists pull requests in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
            },
            "head": {"type": "string"},
            "base": {"type": "string"},
            "per_page": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
        ],
    ),

    ToolDefinition(
        name="get_pull_request",
        description="Gets a GitHub pull request.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "pull_number": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
            "pull_number",
        ],
    ),

    ToolDefinition(
        name="get_pull_request_diff",
        description="Gets the file-level diff of a GitHub pull request.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "pull_number": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
            "pull_number",
        ],
    ),

    ToolDefinition(
        name="list_pull_request_comments",
        description="Lists review comments on a GitHub pull request.",
        operation_type="read",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "pull_number": {"type": "integer"},
        },
        required_params=[
            "owner",
            "repo",
            "pull_number",
        ],
    ),

    # ========================================================================
    # GITHUB — WRITE
    # ========================================================================

    ToolDefinition(
        name="create_issue",
        description="Creates a GitHub issue.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
            },
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        required_params=[
            "owner",
            "repo",
            "title",
        ],
    ),

    ToolDefinition(
        name="update_issue",
        description="Updates a GitHub issue.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "state": {
                "type": "string",
                "enum": ["open", "closed"],
            },
        },
        required_params=[
            "owner",
            "repo",
            "issue_number",
        ],
    ),

    ToolDefinition(
        name="add_issue_comment",
        description="Adds a comment to a GitHub issue.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
            "body": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "issue_number",
            "body",
        ],
    ),

    # ========================================================================
    # GITHUB — PR WRITE
    # ========================================================================

    ToolDefinition(
        name="create_pull_request",
        description="Creates a GitHub pull request.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "head": {"type": "string"},
            "base": {"type": "string"},
            "draft": {"type": "boolean"},
        },
        required_params=[
            "owner",
            "repo",
            "title",
            "head",
            "base",
        ],
    ),

    ToolDefinition(
        name="update_pull_request",
        description="Updates a GitHub pull request.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "pull_number": {"type": "integer"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "state": {
                "type": "string",
                "enum": ["open", "closed"],
            },
        },
        required_params=[
            "owner",
            "repo",
            "pull_number",
        ],
    ),

    # ========================================================================
    # GITHUB — FILE WRITE
    # ========================================================================

    ToolDefinition(
        name="create_or_update_file",
        description=(
            "Creates or updates a file in a GitHub repository."
        ),
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "message": {"type": "string"},
            "content": {"type": "string"},
            "branch": {"type": "string"},
            "sha": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "path",
            "message",
            "content",
        ],
    ),

    ToolDefinition(
        name="push_files",
        description=(
            "Pushes multiple files to a GitHub repository in a single commit."
        ),
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "branch": {"type": "string"},
            "message": {"type": "string"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": [
                        "path",
                        "content",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        required_params=[
            "owner",
            "repo",
            "branch",
            "message",
            "files",
        ],
    ),

    # ========================================================================
    # GITHUB — BRANCHES
    # ========================================================================

    ToolDefinition(
        name="create_branch",
        description="Creates a GitHub branch.",
        operation_type="write",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "branch": {"type": "string"},
            "from_branch": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "branch",
        ],
    ),

    ToolDefinition(
        name="delete_branch",
        description=(
            "Deletes a GitHub branch. This is destructive."
        ),
        operation_type="destructive",
        parameters={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "branch": {"type": "string"},
        },
        required_params=[
            "owner",
            "repo",
            "branch",
        ],
    ),

    # ========================================================================
    # WEB — READ
    # ========================================================================

    ToolDefinition(
        name="web_search",
        description=(
            "Searches the public web for current information, documentation, "
            "news, APIs, tutorials, repositories, and other online resources."
        ),
        operation_type="read",
        parameters={
            "query": {
                "type": "string",
                "description": "Natural language search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results.",
            },
        },
        required_params=["query"],
    ),

    ToolDefinition(
        name="web_fetch",
        description=(
            "Fetches and extracts readable content from a public webpage."
        ),
        operation_type="read",
        parameters={
            "url": {
                "type": "string",
                "description": "HTTP/HTTPS URL.",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum extracted characters.",
            },
        },
        required_params=["url"],
    ),
]


# ============================================================================
# REGISTRY
# ============================================================================

class ToolRegistry:
    """
    Central registry used by the agent.

    Responsibilities:

        - Tool lookup
        - Tool categorization
        - LLM function schema generation
        - Read/write filtering
        - Approval classification
    """

    def __init__(self, tools: List[ToolDefinition]):
        self._tools: Dict[str, ToolDefinition] = {
            tool.name: tool
            for tool in tools
        }

    # ------------------------------------------------------------------
    # LOOKUP
    # ------------------------------------------------------------------

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            from .errors import ToolNotFoundError

            raise ToolNotFoundError(
                f"Tool '{name}' not found in registry.",
                tool=name,
            )

        return self._tools[name]

    def exists(self, name: str) -> bool:
        return name in self._tools

    # ------------------------------------------------------------------
    # LISTING
    # ------------------------------------------------------------------

    def all_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def read_tools(self) -> List[ToolDefinition]:
        return [
            tool
            for tool in self._tools.values()
            if tool.operation_type == "read"
        ]

    def write_tools(self) -> List[ToolDefinition]:
        return [
            tool
            for tool in self._tools.values()
            if tool.operation_type == "write"
        ]

    def destructive_tools(self) -> List[ToolDefinition]:
        return [
            tool
            for tool in self._tools.values()
            if tool.operation_type == "destructive"
        ]

    # ------------------------------------------------------------------
    # CATEGORIES
    # ------------------------------------------------------------------

    def local_tools(self) -> List[ToolDefinition]:
        names = {
            "list_directory",
            "read_file",
            "file_info",
            "search_text",
            "search_code",
            "find_files",
            "write_file",
            "edit_file",
            "create_directory",
            "move_file",
            "delete_file",
        }

        return [
            tool
            for tool in self._tools.values()
            if tool.name in names
        ]

    def shell_tools(self) -> List[ToolDefinition]:
        names = {
            "run_command",
            "run_tests",
        }

        return [
            tool
            for tool in self._tools.values()
            if tool.name in names
        ]

    def git_tools(self) -> List[ToolDefinition]:
        names = {
            "git_status",
            "git_diff",
            "git_log",
            "git_create_branch",
            "git_commit",
            "git_push",
        }

        return [
            tool
            for tool in self._tools.values()
            if tool.name in names
        ]

    def github_tools(self) -> List[ToolDefinition]:
        github_names = {
            "get_repository",
            "get_file_contents",
            "list_branches",
            "list_commits",
            "get_commit",
            "search_repositories",
            "list_tags",
            "github_search_code",
            "list_issues",
            "get_issue",
            "list_issue_comments",
            "search_issues",
            "list_pull_requests",
            "get_pull_request",
            "get_pull_request_diff",
            "list_pull_request_comments",
            "create_issue",
            "update_issue",
            "add_issue_comment",
            "create_pull_request",
            "update_pull_request",
            "create_or_update_file",
            "push_files",
            "create_branch",
            "delete_branch",
        }

        return [
            tool
            for tool in self._tools.values()
            if tool.name in github_names
        ]

    def web_tools(self) -> List[ToolDefinition]:
        names = {
            "web_search",
            "web_fetch",
        }

        return [
            tool
            for tool in self._tools.values()
            if tool.name in names
        ]

    # ------------------------------------------------------------------
    # LLM SCHEMAS
    # ------------------------------------------------------------------

    def openai_functions(self) -> List[Dict[str, Any]]:
        """
        Returns all tools in OpenAI-compatible tool-calling format.
        """
        return [
            tool.to_openai_function()
            for tool in self._tools.values()
        ]

    def read_function_schemas(self) -> List[Dict[str, Any]]:
        return [
            tool.to_openai_function()
            for tool in self.read_tools()
        ]

    def write_function_schemas(self) -> List[Dict[str, Any]]:
        return [
            tool.to_openai_function()
            for tool in self.write_tools()
        ]

    # ------------------------------------------------------------------
    # APPROVAL
    # ------------------------------------------------------------------

    def requires_approval(self, name: str) -> bool:
        """
        Determine whether a tool needs user approval.
        """
        tool = self.get(name)

        return tool.operation_type in (
            "write",
            "destructive",
        )

    def requires_explicit_confirmation(self, name: str) -> bool:
        """
        Destructive tools always require explicit confirmation.
        """
        tool = self.get(name)

        return tool.operation_type == "destructive"

    # ------------------------------------------------------------------
    # DEBUG / INFO
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "total_tools": len(self._tools),
            "read_tools": len(self.read_tools()),
            "write_tools": len(self.write_tools()),
            "destructive_tools": len(self.destructive_tools()),
            "local_tools": len(self.local_tools()),
            "shell_tools": len(self.shell_tools()),
            "git_tools": len(self.git_tools()),
            "github_tools": len(self.github_tools()),
            "web_tools": len(self.web_tools()),
        }


# ============================================================================
# SINGLETON
# ============================================================================

TOOL_REGISTRY = ToolRegistry(_TOOLS)