"""
tests/test_agent.py

Unit tests for the agent layer:
  - tool classification / permission system
  - PendingAction / AgentResult dataclasses
  - audit log (read/write)
  - agent orchestrator instantiation
"""

import os
import sys
import json
import tempfile
import pytest

# Make sure the chatbot root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Permissions ─────────────────────────────────────────────────────────────

class TestPermissions:
    def test_read_tools_are_read(self):
        from agent.permissions import classify_tool, requires_approval
        read_tools = [
            "get_file_contents", "list_branches", "list_commits", "get_commit",
            "get_repository", "search_repositories", "list_tags",
            "list_issues", "get_issue", "list_issue_comments", "search_issues",
            "list_pull_requests", "get_pull_request", "get_pull_request_diff",
            "list_pull_request_comments", "search_code",
        ]
        for tool in read_tools:
            assert classify_tool(tool) == "read", f"{tool} should be 'read'"
            assert not requires_approval(tool), f"{tool} should not require approval"

    def test_write_tools_require_approval(self):
        from agent.permissions import classify_tool, requires_approval
        write_tools = [
            "create_issue", "update_issue", "add_issue_comment",
            "create_pull_request", "update_pull_request",
            "create_or_update_file", "push_files", "create_branch",
        ]
        for tool in write_tools:
            assert classify_tool(tool) == "write", f"{tool} should be 'write'"
            assert requires_approval(tool), f"{tool} should require approval"

    def test_destructive_tools(self):
        from agent.permissions import classify_tool, is_destructive, requires_approval
        assert classify_tool("delete_branch") == "destructive"
        assert is_destructive("delete_branch")
        assert requires_approval("delete_branch")  # destructive also needs approval

    def test_unknown_tool_defaults_to_write(self):
        from agent.permissions import classify_tool, requires_approval
        assert classify_tool("nonexistent_tool") == "write"
        assert requires_approval("nonexistent_tool")


# ─── Tool Registry ────────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_registry_has_tools(self):
        from mcp.tool_registry import TOOL_REGISTRY
        tools = TOOL_REGISTRY.all_tools()
        assert len(tools) > 0

    def test_read_tools_subset(self):
        from mcp.tool_registry import TOOL_REGISTRY
        read_tools = TOOL_REGISTRY.read_tools()
        for t in read_tools:
            assert not t.is_write, f"{t.name} is in read_tools but is_write=True"

    def test_write_tools_subset(self):
        from mcp.tool_registry import TOOL_REGISTRY
        write_tools = TOOL_REGISTRY.write_tools()
        for t in write_tools:
            assert t.is_write, f"{t.name} is in write_tools but is_write=False"

    def test_known_tools_exist(self):
        from mcp.tool_registry import TOOL_REGISTRY
        for name in ["get_file_contents", "create_issue", "delete_branch"]:
            t = TOOL_REGISTRY.get(name)
            assert t.name == name

    def test_openai_functions_format(self):
        from mcp.tool_registry import TOOL_REGISTRY
        functions = TOOL_REGISTRY.openai_functions()
        assert isinstance(functions, list)
        assert len(functions) > 0
        for fn in functions:
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_tool_not_found_raises(self):
        from mcp.tool_registry import TOOL_REGISTRY
        from mcp.errors import ToolNotFoundError
        with pytest.raises(ToolNotFoundError):
            TOOL_REGISTRY.get("does_not_exist")


# ─── Approval Dataclasses ─────────────────────────────────────────────────────

class TestPendingAction:
    def _make_pending(self, op_type="write"):
        from agent.approval import PendingAction
        return PendingAction(
            tool_name="create_issue",
            tool_args={"owner": "a", "repo": "b", "title": "Test"},
            operation_type=op_type,
            repository="a/b",
            description="Create test issue",
            tool_call_id="call_abc123",
        )

    def test_write_not_destructive(self):
        p = self._make_pending("write")
        assert not p.is_destructive()

    def test_destructive_is_destructive(self):
        p = self._make_pending("destructive")
        assert p.is_destructive()

    def test_display_title_write(self):
        p = self._make_pending("write")
        assert "Approval" in p.display_title()

    def test_display_title_destructive(self):
        p = self._make_pending("destructive")
        assert "DESTRUCTIVE" in p.display_title().upper()

    def test_display_summary_contains_tool(self):
        p = self._make_pending()
        summary = p.display_summary()
        assert "create_issue" in summary

    def test_tool_call_id_stored(self):
        p = self._make_pending()
        assert p.tool_call_id == "call_abc123"


class TestAgentResult:
    def test_answer_result(self):
        from agent.approval import AgentResult
        r = AgentResult(answer="Hello!", activity_log=["step 1"])
        assert r.is_complete
        assert not r.is_error
        assert not r.needs_approval

    def test_error_result(self):
        from agent.approval import AgentResult
        r = AgentResult(error="Something went wrong")
        assert r.is_error
        assert not r.is_complete
        assert not r.needs_approval

    def test_pending_result(self):
        from agent.approval import AgentResult, PendingAction
        p = PendingAction(
            tool_name="create_issue",
            tool_args={},
            operation_type="write",
            repository="a/b",
            description="test",
        )
        r = AgentResult(pending_action=p)
        assert r.needs_approval
        assert not r.is_complete
        assert not r.is_error


# ─── Audit Log ───────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_log_and_read(self, tmp_path, monkeypatch):
        import agent.audit as audit_mod

        # Redirect audit to tmp file
        tmp_log = str(tmp_path / "test_audit.jsonl")
        monkeypatch.setattr(audit_mod, "_AUDIT_PATH", tmp_log)

        audit_mod.log_tool_action(
            tool="get_file_contents",
            operation_type="read",
            repository="owner/repo",
            path="app.py",
            backend="ollama",
            model="llama3",
            user_approved=None,
            status="success",
        )

        records = audit_mod.get_recent_audit(10)
        assert len(records) == 1
        r = records[0]
        assert r["tool"] == "get_file_contents"
        assert r["status"] == "success"
        assert r["repository"] == "owner/repo"
        assert "timestamp" in r

    def test_no_sensitive_fields_logged(self, tmp_path, monkeypatch):
        import agent.audit as audit_mod
        tmp_log = str(tmp_path / "test_audit2.jsonl")
        monkeypatch.setattr(audit_mod, "_AUDIT_PATH", tmp_log)

        audit_mod.log_tool_action(
            tool="create_issue",
            operation_type="write",
            repository="a/b",
            backend="gemini",
            model="gemini-1.5-flash",
            user_approved=True,
            status="success",
        )

        with open(tmp_log) as f:
            content = f.read()

        # Must not contain any credential-like strings
        for bad_word in ["api_key", "token", "password", "secret"]:
            assert bad_word not in content.lower(), f"Found sensitive key '{bad_word}' in audit log"

    def test_empty_log_returns_empty_list(self, tmp_path, monkeypatch):
        import agent.audit as audit_mod
        tmp_log = str(tmp_path / "nonexistent.jsonl")
        monkeypatch.setattr(audit_mod, "_AUDIT_PATH", tmp_log)
        records = audit_mod.get_recent_audit(10)
        assert records == []

    def test_audit_failure_does_not_raise(self, monkeypatch):
        import agent.audit as audit_mod
        # Set an unwritable path
        monkeypatch.setattr(audit_mod, "_AUDIT_PATH", "/definitely/does/not/exist/audit.jsonl")
        # Should NOT raise
        audit_mod.log_tool_action(
            tool="test",
            operation_type="read",
            repository="",
            backend="",
            model="",
            user_approved=None,
            status="success",
        )


# ─── Error Hierarchy ─────────────────────────────────────────────────────────

class TestMCPErrors:
    def test_auth_error_message(self):
        from mcp.errors import AuthenticationError
        e = AuthenticationError("Bad token", tool="init", status_code=401)
        assert "Authentication" in e.user_message()

    def test_rate_limit_message(self):
        from mcp.errors import RateLimitError
        e = RateLimitError("Rate limit exceeded", tool="search_code")
        assert "Rate Limit" in e.user_message()

    def test_permission_denied_message(self):
        from mcp.errors import PermissionDeniedError
        e = PermissionDeniedError("403 Forbidden", tool="create_issue", status_code=403)
        msg = e.user_message()
        assert "Permission" in msg or "permission" in msg

    def test_not_found_message(self):
        from mcp.errors import RepositoryNotFoundError
        e = RepositoryNotFoundError("404", tool="get_file_contents", status_code=404)
        assert "Not Found" in e.user_message() or "not found" in e.user_message()

    def test_cancelled_message(self):
        from mcp.errors import UserCancelledError
        e = UserCancelledError("Cancelled", tool="create_issue")
        assert "cancelled" in e.user_message().lower()


# ─── Orchestrator — no-token guard ───────────────────────────────────────────

class TestOrchestratorNoToken:
    def test_run_without_token_returns_error(self, monkeypatch):
        """Orchestrator should return an error AgentResult if no GitHub token is set."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        from agent.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(backend="ollama", model="llama3", github_token="")
        result = orch.run(user_message="List files")
        assert result.is_error
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in result.error or "not available" in result.error.lower()
