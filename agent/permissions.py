"""
agent/permissions.py

Classifies every GitHub MCP tool as READ, WRITE, or DESTRUCTIVE.

Classification rules:
  READ        — safe, no mutation of GitHub state
  WRITE       — creates or modifies GitHub resources (requires user approval)
  DESTRUCTIVE — irreversible deletions (requires extra confirmation)

Conservative policy: any unrecognised tool is classified as WRITE.
"""

from typing import Literal

OperationType = Literal["read", "write", "destructive"]

# ---------------------------------------------------------------------------
# Tool classification table (must stay in sync with mcp/tool_registry.py)
# ---------------------------------------------------------------------------
_CLASSIFICATION: dict[str, OperationType] = {
    # READ — repository
    "get_file_contents": "read",
    "list_branches": "read",
    "list_commits": "read",
    "get_commit": "read",
    "get_repository": "read",
    "search_repositories": "read",
    "list_tags": "read",
    # READ — issues
    "list_issues": "read",
    "get_issue": "read",
    "list_issue_comments": "read",
    "search_issues": "read",
    # READ — pull requests
    "list_pull_requests": "read",
    "get_pull_request": "read",
    "get_pull_request_diff": "read",
    "list_pull_request_comments": "read",
    # READ — code
    "search_code": "read",
    # WRITE — issues
    "create_issue": "write",
    "update_issue": "write",
    "add_issue_comment": "write",
    # WRITE — pull requests
    "create_pull_request": "write",
    "update_pull_request": "write",
    # WRITE — files
    "create_or_update_file": "write",
    "push_files": "write",
    # WRITE — branches
    "create_branch": "write",
    # DESTRUCTIVE
    "delete_branch": "destructive",
}


def classify_tool(tool_name: str) -> OperationType:
    """
    Returns the operation type for a given tool name.
    Falls back to 'write' (safe default) for unknown tools.
    """
    return _CLASSIFICATION.get(tool_name, "write")


def requires_approval(tool_name: str) -> bool:
    """Returns True if the tool requires explicit user approval before execution."""
    return classify_tool(tool_name) in ("write", "destructive")


def is_destructive(tool_name: str) -> bool:
    """Returns True if the tool is classified as destructive."""
    return classify_tool(tool_name) == "destructive"
