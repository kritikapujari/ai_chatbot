"""
mcp/client.py

Base GitHub MCP client — handles authentication, connection health, and rate limiting.

Authentication uses GITHUB_PERSONAL_ACCESS_TOKEN (same env variable as the official
GitHub MCP Server docker image), loaded from .env via python-dotenv.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    # pyrefly: ignore [missing-import]
    from github import Github, GithubException, RateLimitExceededException
    # pyrefly: ignore [missing-import]
    from github.GithubException import UnknownObjectException, BadCredentialsException
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False

from .errors import AuthenticationError, RateLimitError, MCPError


class GitHubMCPClientBase:
    """
    Manages a PyGithub connection authenticated by GITHUB_PERSONAL_ACCESS_TOKEN.

    Raises AuthenticationError on missing/invalid token.
    Raises MCPError for connection issues.
    """

    def __init__(self, token: Optional[str] = None):
        if not PYGITHUB_AVAILABLE:
            raise MCPError(
                "PyGithub is not installed. Run: pip install PyGithub",
                tool="init",
            )

        self._token = token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "").strip()
        if not self._token:
            raise AuthenticationError(
                "GITHUB_PERSONAL_ACCESS_TOKEN is not set. "
                "Add it to your .env file to enable GitHub Agent Mode.",
                tool="init",
            )

        try:
            self._gh = Github(self._token)
            # Trigger a lightweight API call to validate the token
            self._user = self._gh.get_user()
            _ = self._user.login  # forces the request
        except BadCredentialsException:
            raise AuthenticationError(
                "GitHub token is invalid or expired.",
                tool="init",
                status_code=401,
            )
        except RateLimitExceededException as exc:
            raise RateLimitError(str(exc), tool="init")
        except Exception as exc:
            raise MCPError(f"Failed to connect to GitHub: {exc}", tool="init")

    @property
    def authenticated_user(self) -> str:
        """Return the username of the authenticated token owner."""
        try:
            return self._user.login
        except Exception:
            return "unknown"

    def check_connection(self) -> dict:
        """Return connection status info. Never raises."""
        try:
            login = self._gh.get_user().login
            rate = self._gh.get_rate_limit().resources.core
            return {
                "connected": True,
                "user": login,
                "rate_limit_remaining": rate.remaining,
                "rate_limit_total": rate.limit,
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def _handle_github_exception(self, exc: Exception, tool: str) -> None:
        """
        Convert a GithubException to the appropriate MCPError subclass.
        Always raises — never returns normally.
        """
        if not PYGITHUB_AVAILABLE:
            raise MCPError(str(exc), tool=tool)

        if isinstance(exc, BadCredentialsException):
            raise AuthenticationError(str(exc), tool=tool, status_code=401)
        if isinstance(exc, RateLimitExceededException):
            raise RateLimitError(str(exc), tool=tool)
        if isinstance(exc, UnknownObjectException):
            from .errors import RepositoryNotFoundError
            raise RepositoryNotFoundError(str(exc), tool=tool, status_code=404)
        if isinstance(exc, GithubException):
            status = exc.status if hasattr(exc, "status") else 0
            if status == 403:
                from .errors import PermissionDeniedError
                raise PermissionDeniedError(str(exc), tool=tool, status_code=403)
            raise MCPError(str(exc), tool=tool, status_code=status)
        raise MCPError(str(exc), tool=tool)
