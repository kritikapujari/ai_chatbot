"""
tests/test_mcp.py

Unit tests for the MCP layer:
  - GitHubMCPClientBase instantiation errors
  - ToolResult formatting
  - diff generation
  - error hierarchy
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── MCP Error Hierarchy ─────────────────────────────────────────────────────

class TestMCPErrorHierarchy:
    def test_base_error_is_exception(self):
        from mcp.errors import MCPError
        e = MCPError("base error", tool="test")
        assert isinstance(e, Exception)
        assert e.tool == "test"

    def test_auth_error_inherits_from_mcp(self):
        from mcp.errors import AuthenticationError, MCPError
        e = AuthenticationError("bad creds", tool="init")
        assert isinstance(e, MCPError)

    def test_rate_limit_inherits_from_mcp(self):
        from mcp.errors import RateLimitError, MCPError
        e = RateLimitError("rate limited", tool="search_code")
        assert isinstance(e, MCPError)

    def test_tool_not_found_inherits_from_mcp(self):
        from mcp.errors import ToolNotFoundError, MCPError
        e = ToolNotFoundError("no such tool", tool="fake_tool")
        assert isinstance(e, MCPError)


# ─── ToolResult Formatting ────────────────────────────────────────────────────

class TestToolResult:
    def test_success_with_raw_text(self):
        from mcp.github_client import ToolResult
        r = ToolResult(tool="get_file_contents", success=True, data={}, raw_text="file content here")
        assert r.format_for_llm() == "file content here"

    def test_success_with_string_data(self):
        from mcp.github_client import ToolResult
        r = ToolResult(tool="search_code", success=True, data="some string data")
        assert r.format_for_llm() == "some string data"

    def test_success_with_dict_data(self):
        from mcp.github_client import ToolResult
        import json
        r = ToolResult(tool="get_repository", success=True, data={"name": "test_repo"})
        formatted = r.format_for_llm()
        data = json.loads(formatted)
        assert data["name"] == "test_repo"

    def test_failure_format(self):
        from mcp.github_client import ToolResult
        r = ToolResult(tool="create_issue", success=False, data=None, error="Permission denied")
        formatted = r.format_for_llm()
        assert "Tool Error" in formatted or "Error" in formatted
        assert "Permission denied" in formatted

    def test_to_dict(self):
        from mcp.github_client import ToolResult
        r = ToolResult(tool="list_issues", success=True, data=[{"number": 1}])
        d = r.to_dict()
        assert d["tool"] == "list_issues"
        assert d["success"] is True


# ─── Diff Generation ─────────────────────────────────────────────────────────

class TestDiffGeneration:
    def test_simple_diff(self):
        from mcp.github_client import GitHubMCPClient
        old = "line 1\nline 2\nline 3\n"
        new = "line 1\nline 2 modified\nline 3\n"
        diff = GitHubMCPClient.generate_diff(old, new, "test.py")
        assert "-line 2\n" in diff or "- line 2" in diff
        assert "+line 2 modified" in diff or "+ line 2 modified" in diff

    def test_no_change_diff(self):
        from mcp.github_client import GitHubMCPClient
        content = "unchanged content\n"
        diff = GitHubMCPClient.generate_diff(content, content, "test.py")
        assert diff == "(no changes)"

    def test_diff_includes_filename(self):
        from mcp.github_client import GitHubMCPClient
        diff = GitHubMCPClient.generate_diff("old\n", "new\n", "README.md")
        assert "README.md" in diff


# ─── Base Client Authentication Guard ────────────────────────────────────────

class TestClientAuthGuard:
    def test_no_token_raises_auth_error(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        from mcp.client import GitHubMCPClientBase
        from mcp.errors import AuthenticationError
        with pytest.raises((AuthenticationError, Exception)):
            GitHubMCPClientBase(token="")

    def test_pygithub_not_available_raises(self, monkeypatch):
        """If PyGithub is missing, MCPError should be raised."""
        import mcp.client as client_mod
        monkeypatch.setattr(client_mod, "PYGITHUB_AVAILABLE", False)
        from mcp.errors import MCPError
        with pytest.raises(MCPError, match="PyGithub"):
            client_mod.GitHubMCPClientBase(token="fake_token")


# ─── Tool Registry Completeness Check ────────────────────────────────────────

class TestToolRegistryCompleteness:
    """Verify that every tool in the registry has a corresponding handler
    in GitHubMCPClient (catches regressions where registry and client drift)."""

    def test_all_registry_tools_have_handlers(self):
        from mcp.tool_registry import TOOL_REGISTRY
        from mcp.github_client import GitHubMCPClient

        # We can only check method existence, not call them without a real token
        for tool in TOOL_REGISTRY.all_tools():
            handler_name = f"_tool_{tool.name}"
            assert hasattr(GitHubMCPClient, handler_name), (
                f"GitHubMCPClient is missing handler: {handler_name}"
            )

    def test_no_duplicate_tool_names(self):
        from mcp.tool_registry import TOOL_REGISTRY
        names = TOOL_REGISTRY.names()
        assert len(names) == len(set(names)), "Duplicate tool names found in registry"

    def test_required_params_subset_of_parameters(self):
        from mcp.tool_registry import TOOL_REGISTRY
        for tool in TOOL_REGISTRY.all_tools():
            for req in tool.required_params:
                assert req in tool.parameters, (
                    f"Tool '{tool.name}': required param '{req}' not in parameters"
                )


# ─── Security: Prompt Injection Check ────────────────────────────────────────

class TestPromptInjectionDefense:
    def test_security_preamble_is_present(self):
        """The security preamble must be in the orchestrator and contain key instructions."""
        from agent.orchestrator import SECURITY_PREAMBLE
        assert "UNTRUSTED" in SECURITY_PREAMBLE or "untrusted" in SECURITY_PREAMBLE.lower()
        assert "WRITE" in SECURITY_PREAMBLE or "write" in SECURITY_PREAMBLE.lower()

    def test_security_preamble_injected_in_messages(self, monkeypatch):
        """When building initial messages, the security preamble must appear in the system message."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        from agent.orchestrator import AgentOrchestrator, SECURITY_PREAMBLE
        orch = AgentOrchestrator(backend="ollama", model="llama3", github_token="")
        messages = orch._build_initial_messages(
            system_prompt="Be helpful.",
            history=[],
            user_message="Do something.",
        )
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert SECURITY_PREAMBLE[:50] in system_msg["content"]
