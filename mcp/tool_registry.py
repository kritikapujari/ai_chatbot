"""
mcp/tool_registry.py

Defines every GitHub MCP tool available to the agent.

Tool names, descriptions, and parameter schemas match the official
GitHub MCP Server (github/github-mcp-server) tool catalogue exactly.
Each tool is classified as READ, WRITE, or DESTRUCTIVE.

Classification rules:
  READ        — query only, no mutation of GitHub state
  WRITE       — creates or modifies GitHub resources (requires user approval)
  DESTRUCTIVE — irreversible deletions (requires explicit typed confirmation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

OperationType = Literal["read", "write", "destructive"]


@dataclass
class ToolDefinition:
    """Schema for a single GitHub MCP tool."""

    name: str
    description: str
    operation_type: OperationType
    parameters: Dict[str, Any]  # JSON Schema object
    required_params: List[str] = field(default_factory=list)

    @property
    def is_write(self) -> bool:
        return self.operation_type in ("write", "destructive")

    @property
    def is_destructive(self) -> bool:
        return self.operation_type == "destructive"

    def to_openai_function(self) -> Dict[str, Any]:
        """Serialize to OpenAI/Gemini function-calling schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required_params,
            },
        }


# ---------------------------------------------------------------------------
# Tool catalogue — mirrors github/github-mcp-server official tool names
# ---------------------------------------------------------------------------

_TOOLS: List[ToolDefinition] = [
    # -----------------------------------------------------------------------
    # READ — Repository
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="get_file_contents",
        description=(
            "Gets the contents of a file or directory in a GitHub repository. "
            "Returns file content decoded as text, or a directory listing."
        ),
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner (username or org)"},
            "repo": {"type": "string", "description": "Repository name"},
            "path": {"type": "string", "description": "File path (e.g. 'app.py' or 'src/utils.py')"},
            "ref": {"type": "string", "description": "Git ref (branch, tag, commit SHA). Defaults to default branch."},
        },
        required_params=["owner", "repo", "path"],
    ),
    ToolDefinition(
        name="list_branches",
        description="Lists branches in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "page": {"type": "integer", "description": "Page number (default 1)"},
            "per_page": {"type": "integer", "description": "Results per page (default 30, max 100)"},
        },
        required_params=["owner", "repo"],
    ),
    ToolDefinition(
        name="list_commits",
        description="Gets list of commits in a repository with optional filtering by author, path, or date range.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "sha": {"type": "string", "description": "Branch/tag/SHA to list commits from"},
            "path": {"type": "string", "description": "Only commits touching this file path"},
            "author": {"type": "string", "description": "Filter by author (username or email)"},
            "since": {"type": "string", "description": "ISO 8601 date — only commits after this date"},
            "until": {"type": "string", "description": "ISO 8601 date — only commits before this date"},
            "per_page": {"type": "integer", "description": "Results per page (default 30, max 100)"},
        },
        required_params=["owner", "repo"],
    ),
    ToolDefinition(
        name="get_commit",
        description="Gets details about a specific commit in a repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "sha": {"type": "string", "description": "Commit SHA"},
        },
        required_params=["owner", "repo", "sha"],
    ),
    ToolDefinition(
        name="get_repository",
        description="Gets metadata and details about a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
        },
        required_params=["owner", "repo"],
    ),
    ToolDefinition(
        name="search_repositories",
        description="Searches GitHub repositories using a query string.",
        operation_type="read",
        parameters={
            "query": {"type": "string", "description": "Search query (e.g. 'chatbot language:python')"},
            "page": {"type": "integer", "description": "Page number"},
            "per_page": {"type": "integer", "description": "Results per page (max 100)"},
        },
        required_params=["query"],
    ),
    ToolDefinition(
        name="list_tags",
        description="Lists tags in a GitHub repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "per_page": {"type": "integer", "description": "Results per page"},
        },
        required_params=["owner", "repo"],
    ),
    # -----------------------------------------------------------------------
    # READ — Issues
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="list_issues",
        description="Lists issues in a repository with optional filtering by state, labels, or assignee.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue state filter"},
            "labels": {"type": "string", "description": "Comma-separated list of label names"},
            "assignee": {"type": "string", "description": "Filter by assignee username"},
            "per_page": {"type": "integer", "description": "Results per page (max 100)"},
        },
        required_params=["owner", "repo"],
    ),
    ToolDefinition(
        name="get_issue",
        description="Gets details about a specific issue in a repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "issue_number": {"type": "integer", "description": "Issue number"},
        },
        required_params=["owner", "repo", "issue_number"],
    ),
    ToolDefinition(
        name="list_issue_comments",
        description="Lists comments on a specific issue.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "issue_number": {"type": "integer", "description": "Issue number"},
        },
        required_params=["owner", "repo", "issue_number"],
    ),
    ToolDefinition(
        name="search_issues",
        description="Searches issues and pull requests across GitHub using a query string.",
        operation_type="read",
        parameters={
            "query": {"type": "string", "description": "Search query (e.g. 'repo:owner/name is:issue is:open')"},
            "per_page": {"type": "integer", "description": "Results per page"},
        },
        required_params=["query"],
    ),
    # -----------------------------------------------------------------------
    # READ — Pull Requests
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="list_pull_requests",
        description="Lists pull requests in a repository.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "PR state filter"},
            "head": {"type": "string", "description": "Filter by head branch (format: user:branch)"},
            "base": {"type": "string", "description": "Filter by base branch"},
            "per_page": {"type": "integer", "description": "Results per page"},
        },
        required_params=["owner", "repo"],
    ),
    ToolDefinition(
        name="get_pull_request",
        description="Gets details about a specific pull request.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "pull_number": {"type": "integer", "description": "Pull request number"},
        },
        required_params=["owner", "repo", "pull_number"],
    ),
    ToolDefinition(
        name="get_pull_request_diff",
        description="Gets the diff of a pull request as a string.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "pull_number": {"type": "integer", "description": "Pull request number"},
        },
        required_params=["owner", "repo", "pull_number"],
    ),
    ToolDefinition(
        name="list_pull_request_comments",
        description="Lists review comments on a pull request.",
        operation_type="read",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "pull_number": {"type": "integer", "description": "Pull request number"},
        },
        required_params=["owner", "repo", "pull_number"],
    ),
    # -----------------------------------------------------------------------
    # READ — Code Search
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="search_code",
        description="Searches code in a repository or across GitHub using a query string.",
        operation_type="read",
        parameters={
            "query": {"type": "string", "description": "Search query (e.g. 'OpenRouter repo:owner/name')"},
            "per_page": {"type": "integer", "description": "Results per page (max 100)"},
        },
        required_params=["query"],
    ),
    # -----------------------------------------------------------------------
    # WRITE — Issues (require user approval)
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="create_issue",
        description="Creates a new issue in a GitHub repository.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "title": {"type": "string", "description": "Issue title"},
            "body": {"type": "string", "description": "Issue body (Markdown supported)"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of label names to assign",
            },
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of GitHub usernames to assign",
            },
        },
        required_params=["owner", "repo", "title"],
    ),
    ToolDefinition(
        name="update_issue",
        description="Updates an existing issue's title, body, state, labels, or assignees.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "issue_number": {"type": "integer", "description": "Issue number to update"},
            "title": {"type": "string", "description": "New title"},
            "body": {"type": "string", "description": "New body"},
            "state": {"type": "string", "enum": ["open", "closed"], "description": "New state"},
        },
        required_params=["owner", "repo", "issue_number"],
    ),
    ToolDefinition(
        name="add_issue_comment",
        description="Adds a comment to an existing issue.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "issue_number": {"type": "integer", "description": "Issue number"},
            "body": {"type": "string", "description": "Comment body (Markdown supported)"},
        },
        required_params=["owner", "repo", "issue_number", "body"],
    ),
    # -----------------------------------------------------------------------
    # WRITE — Pull Requests (require user approval)
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="create_pull_request",
        description="Creates a new pull request.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "title": {"type": "string", "description": "PR title"},
            "body": {"type": "string", "description": "PR description (Markdown)"},
            "head": {"type": "string", "description": "Head branch name (the branch with changes)"},
            "base": {"type": "string", "description": "Base branch name (target branch, e.g. 'main')"},
            "draft": {"type": "boolean", "description": "Create as draft PR"},
        },
        required_params=["owner", "repo", "title", "head", "base"],
    ),
    ToolDefinition(
        name="update_pull_request",
        description="Updates a pull request's title, body, or state.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "pull_number": {"type": "integer", "description": "PR number"},
            "title": {"type": "string", "description": "New title"},
            "body": {"type": "string", "description": "New body"},
            "state": {"type": "string", "enum": ["open", "closed"], "description": "New state"},
        },
        required_params=["owner", "repo", "pull_number"],
    ),
    # -----------------------------------------------------------------------
    # WRITE — Files (require user approval + show diff)
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="create_or_update_file",
        description=(
            "Creates a new file or updates an existing file in a repository. "
            "Always show the diff to the user before calling this tool."
        ),
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "path": {"type": "string", "description": "File path in the repository"},
            "message": {"type": "string", "description": "Commit message"},
            "content": {"type": "string", "description": "New file content (plain text, NOT base64)"},
            "branch": {"type": "string", "description": "Branch to commit to (defaults to default branch)"},
            "sha": {"type": "string", "description": "Current file SHA (required for updates, not for new files)"},
        },
        required_params=["owner", "repo", "path", "message", "content"],
    ),
    ToolDefinition(
        name="push_files",
        description=(
            "Pushes multiple files to a repository in a single commit. "
            "Always show the proposed file changes to the user before calling this tool."
        ),
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "branch": {"type": "string", "description": "Branch to push to"},
            "message": {"type": "string", "description": "Commit message"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
                "description": "List of {path, content} objects",
            },
        },
        required_params=["owner", "repo", "branch", "message", "files"],
    ),
    # -----------------------------------------------------------------------
    # WRITE — Branches (require user approval)
    # -----------------------------------------------------------------------
    ToolDefinition(
        name="create_branch",
        description="Creates a new branch in a repository from a specified SHA or branch.",
        operation_type="write",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "branch": {"type": "string", "description": "New branch name"},
            "from_branch": {"type": "string", "description": "Source branch/SHA (defaults to default branch)"},
        },
        required_params=["owner", "repo", "branch"],
    ),
    ToolDefinition(
        name="delete_branch",
        description="Deletes a branch from a repository. DESTRUCTIVE — cannot be undone.",
        operation_type="destructive",
        parameters={
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "branch": {"type": "string", "description": "Branch name to delete"},
        },
        required_params=["owner", "repo", "branch"],
    ),
]


class ToolRegistry:
    """Provides lookup and schema generation for all registered tools."""

    def __init__(self, tools: List[ToolDefinition]):
        self._tools: Dict[str, ToolDefinition] = {t.name: t for t in tools}

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            from .errors import ToolNotFoundError
            raise ToolNotFoundError(f"Tool '{name}' not found in registry.", tool=name)
        return self._tools[name]

    def all_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def read_tools(self) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if not t.is_write]

    def write_tools(self) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.is_write]

    def openai_functions(self) -> List[Dict[str, Any]]:
        """Return all tool schemas in OpenAI function-calling format."""
        return [t.to_openai_function() for t in self._tools.values()]

    def names(self) -> List[str]:
        return list(self._tools.keys())


# Singleton registry used throughout the application
TOOL_REGISTRY = ToolRegistry(_TOOLS)
