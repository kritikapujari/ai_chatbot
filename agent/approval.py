"""
agent/approval.py

Dataclasses and helpers for the write-confirmation workflow.

The approval system works as a state machine in Streamlit's session_state:

  1. Agent encounters a write tool → returns AgentResult(pending_action=...)
  2. Streamlit UI renders the approval widget
  3. User clicks Approve or Cancel
  4. Agent resumes from pending_action.messages with the result

Security guarantee:
  Each PendingAction carries the exact tool_name + args that were proposed.
  The approval UI renders only from the PendingAction — it cannot be
  manipulated by repository content to swap the approved operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PendingAction:
    """
    Represents a write/destructive tool call awaiting user approval.

    Attributes:
        tool_name:       Exact MCP tool name to execute upon approval
        tool_args:       Exact arguments to pass to the tool
        operation_type:  "write" or "destructive"
        repository:      "owner/repo" string for display
        description:     Human-readable summary of what will happen
        diff:            Optional unified diff for file modifications
        multi_step:      For multi-step sequences, a human-readable step list
        messages:        Full LLM message history to resume from after approval
        backend:         LLM backend name (for audit logging)
        model:           LLM model name (for audit logging)
    """

    tool_name: str
    tool_args: Dict[str, Any]
    operation_type: str  # "write" | "destructive"
    repository: str
    description: str
    diff: Optional[str] = None
    multi_step: Optional[List[str]] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    backend: str = ""
    model: str = ""
    tool_call_id: str = ""  # The exact call ID from the LLM (important for OpenRouter)

    def is_destructive(self) -> bool:
        return self.operation_type == "destructive"

    def display_title(self) -> str:
        if self.is_destructive():
            return "⚠️ DESTRUCTIVE OPERATION — Explicit Confirmation Required"
        return "🔐 Write Operation — Approval Required"

    def display_summary(self) -> str:
        """Generate the summary text shown in the approval widget."""
        lines = [
            f"**Tool:** `{self.tool_name}`",
            f"**Repository:** `{self.repository}`",
            "",
            self.description,
        ]
        if self.multi_step:
            lines.append("\n**Planned operations:**")
            for i, step in enumerate(self.multi_step, 1):
                lines.append(f"{i}. {step}")
        return "\n".join(lines)


@dataclass
class AgentResult:
    """
    The result returned by the agent orchestrator for one user message.

    Exactly one of (answer, pending_action) will be set:
      - answer:         Agent completed the task — display this to the user
      - pending_action: Agent needs write approval — show the confirmation UI

    activity_log:  List of human-readable strings describing what the agent did
    error:         Non-empty if the agent failed
    """

    answer: Optional[str] = None
    pending_action: Optional[PendingAction] = None
    activity_log: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def needs_approval(self) -> bool:
        return self.pending_action is not None

    @property
    def is_complete(self) -> bool:
        return self.answer is not None

    @property
    def is_error(self) -> bool:
        return self.error is not None
