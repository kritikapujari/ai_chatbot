"""
mcp/errors.py

Custom exception hierarchy for the MCP / GitHub integration layer.
All exceptions inherit from MCPError so callers can catch them broadly,
but sub-classes allow granular handling in the agent and UI.
"""


class MCPError(Exception):
    """Base exception for all MCP / GitHub tool errors."""

    def __init__(self, message: str, tool: str = "", status_code: int = 0):
        super().__init__(message)
        self.tool = tool
        self.status_code = status_code

    def user_message(self) -> str:
        return str(self)


class AuthenticationError(MCPError):
    """GitHub token is missing, invalid, or expired."""

    def user_message(self) -> str:
        return (
            "⚠️ GitHub Authentication Failed\n\n"
            "Please check that GITHUB_PERSONAL_ACCESS_TOKEN is set correctly in your .env file "
            "and that the token has not expired."
        )


class PermissionDeniedError(MCPError):
    """Token lacks required scope for this operation."""

    def user_message(self) -> str:
        return (
            "⚠️ GitHub Permission Denied\n\n"
            f"The GitHub token does not have permission to perform: {self.tool}.\n"
            "You may need to add the 'repo' scope to your Personal Access Token."
        )


class RepositoryNotFoundError(MCPError):
    """Repository does not exist or is not accessible."""

    def user_message(self) -> str:
        return (
            "⚠️ Repository Not Found\n\n"
            "The specified repository could not be found. "
            "Check that the repository name is correct and the token has access."
        )


class ToolNotFoundError(MCPError):
    """Requested tool does not exist in the registry."""

    def user_message(self) -> str:
        return f"⚠️ Unknown tool: '{self.tool}'. This tool is not registered."


class ToolExecutionError(MCPError):
    """Tool ran but returned an error result."""

    def user_message(self) -> str:
        return f"⚠️ Tool '{self.tool}' failed: {self}"


class RateLimitError(MCPError):
    """GitHub API rate limit exceeded."""

    def __init__(self, message: str, tool: str = "", reset_timestamp: int = 0):
        super().__init__(message, tool)
        self.reset_timestamp = reset_timestamp

    def user_message(self) -> str:
        return (
            "⚠️ GitHub API Rate Limit Reached\n\n"
            "Too many requests have been made to the GitHub API. "
            "Please wait a moment before trying again."
        )


class InvalidArgumentsError(MCPError):
    """Tool was called with missing or invalid arguments."""

    def user_message(self) -> str:
        return f"⚠️ Invalid arguments for tool '{self.tool}': {self}"


class UserCancelledError(MCPError):
    """User explicitly cancelled a pending write operation."""

    def user_message(self) -> str:
        return "Operation cancelled by user."
