"""
agent/audit.py

Append-only audit log for all agent tool actions.

Every tool call — successful or failed, approved or cancelled — is logged
to agent_audit.jsonl in the project root.

Fields logged:
  timestamp, agent_mode, backend, model, tool, operation_type,
  repository, path (optional), user_approved, status

Fields NEVER logged:
  API keys, GitHub tokens, passwords, file content, issue bodies,
  or any other sensitive data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Audit log file lives next to app.py
_AUDIT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_audit.jsonl")

_SENSITIVE_KEYS = {
    "token", "api_key", "password", "secret", "credential",
    "github_personal_access_token", "openrouter_api_key",
    "gemini_api_key", "authorization",
}


def _sanitize(args: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from tool arguments before logging."""
    return {k: v for k, v in args.items() if k.lower() not in _SENSITIVE_KEYS}


def log_tool_action(
    *,
    tool: str,
    operation_type: str,
    repository: str = "",
    path: str = "",
    backend: str = "",
    model: str = "",
    user_approved: Optional[bool],
    status: str,
    error: str = "",
) -> None:
    """
    Append a single tool action record to agent_audit.jsonl.
    Never raises — log failures are silently swallowed.
    """
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": True,
            "backend": backend,
            "model": model,
            "tool": tool,
            "operation_type": operation_type,
            "repository": repository,
            "path": path,
            "user_approved": user_approved,
            "status": status,
        }
        if error:
            record["error"] = error[:500]  # Truncate long errors

        with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # Audit log failures must never crash the agent


def get_recent_audit(n: int = 10) -> List[Dict[str, Any]]:
    """
    Returns the n most recent audit log entries.
    Returns an empty list if the log file doesn't exist or is unreadable.
    """
    try:
        if not os.path.exists(_AUDIT_PATH):
            return []
        with open(_AUDIT_PATH, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records[-n:]
    except Exception:
        return []


def get_audit_path() -> str:
    return _AUDIT_PATH
