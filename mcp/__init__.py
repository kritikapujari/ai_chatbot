"""
mcp/__init__.py
"""
from .errors import (
    MCPError,
    AuthenticationError,
    PermissionDeniedError,
    RepositoryNotFoundError,
    ToolNotFoundError,
    ToolExecutionError,
    RateLimitError,
    InvalidArgumentsError,
    UserCancelledError,
)
from .tool_registry import ToolRegistry, ToolDefinition, TOOL_REGISTRY
from .github_client import GitHubMCPClient

__all__ = [
    "MCPError",
    "AuthenticationError",
    "PermissionDeniedError",
    "RepositoryNotFoundError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "RateLimitError",
    "InvalidArgumentsError",
    "UserCancelledError",
    "ToolRegistry",
    "ToolDefinition",
    "TOOL_REGISTRY",
    "GitHubMCPClient",
]
