"""
mcp/github_client.py

Implements every registered GitHub MCP tool using the PyGithub library.

Tool names and parameter contracts match the official GitHub MCP Server exactly.
Content retrieved from GitHub (files, issues, READMEs, PRs) is treated as
UNTRUSTED DATA and is never allowed to override security policy or trigger
write operations without explicit user confirmation.

Security note:
  All content from GitHub is passed to the LLM as plain data inside the
  tool_result message. The agent system prompt explicitly instructs the LLM
  to treat this content as untrusted data, not as instructions.
"""

from __future__ import annotations

import base64
import difflib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import GitHubMCPClientBase
from .errors import InvalidArgumentsError, MCPError, ToolExecutionError

try:
    # pyrefly: ignore [missing-import]
    from github import Github
    # pyrefly: ignore [missing-import]
    from github.ContentFile import ContentFile
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False


@dataclass
class ToolResult:
    """Result of executing a GitHub MCP tool."""

    tool: str
    success: bool
    data: Any
    error: Optional[str] = None
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }

    def format_for_llm(self) -> str:
        """Format result as text for inclusion in the LLM message."""
        if not self.success:
            return f"[Tool Error] {self.tool}: {self.error}"
        if self.raw_text:
            return self.raw_text
        if isinstance(self.data, str):
            return self.data
        return json.dumps(self.data, indent=2, default=str)


class GitHubMCPClient(GitHubMCPClientBase):
    """
    Executes GitHub MCP tools via the PyGithub library.

    All tool names and signatures mirror the official github/github-mcp-server.
    """

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """
        Dispatch a tool call by name with the given arguments.
        Returns a ToolResult — never raises (errors are captured in the result).
        """
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return ToolResult(
                tool=tool_name,
                success=False,
                data=None,
                error=f"Tool '{tool_name}' is not implemented.",
            )
        try:
            return handler(**args)
        except MCPError as exc:
            return ToolResult(tool=tool_name, success=False, data=None, error=exc.user_message())
        except Exception as exc:
            return ToolResult(tool=tool_name, success=False, data=None, error=str(exc))

    # ------------------------------------------------------------------
    # READ — Repository tools
    # ------------------------------------------------------------------

    def _tool_get_file_contents(self, owner: str, repo: str, path: str, ref: str = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            kwargs = {}
            if ref:
                kwargs["ref"] = ref
            contents = gh_repo.get_contents(path, **kwargs)

            # Directory listing
            if isinstance(contents, list):
                items = []
                for item in contents:
                    items.append({
                        "name": item.name,
                        "path": item.path,
                        "type": item.type,
                        "size": item.size,
                    })
                data = {"type": "directory", "path": path, "items": items}
                text = f"Directory listing for '{path}':\n" + "\n".join(
                    f"  [{i['type']}] {i['path']} ({i['size']} bytes)" for i in items
                )
                return ToolResult(tool="get_file_contents", success=True, data=data, raw_text=text)

            # Single file
            if contents.encoding == "base64":
                decoded = base64.b64decode(contents.content).decode("utf-8", errors="replace")
            else:
                decoded = contents.decoded_content.decode("utf-8", errors="replace")

            data = {
                "type": "file",
                "path": contents.path,
                "sha": contents.sha,
                "size": contents.size,
                "content": decoded,
            }
            text = f"File: {contents.path}\nSHA: {contents.sha}\n\n{decoded}"
            return ToolResult(tool="get_file_contents", success=True, data=data, raw_text=text)
        except MCPError:
            raise
        except Exception as exc:
            self._handle_github_exception(exc, "get_file_contents")

    def _tool_list_branches(self, owner: str, repo: str, page: int = 1, per_page: int = 30) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            branches = list(gh_repo.get_branches()[:min(per_page, 100)])
            items = [{"name": b.name, "sha": b.commit.sha, "protected": b.protected} for b in branches]
            text = f"Branches in {owner}/{repo}:\n" + "\n".join(f"  • {b['name']}" + (" [protected]" if b["protected"] else "") for b in items)
            return ToolResult(tool="list_branches", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_branches")

    def _tool_list_commits(self, owner: str, repo: str, sha: str = None, path: str = None,
                           author: str = None, since: str = None, until: str = None, per_page: int = 30) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            kwargs = {}
            if sha:
                kwargs["sha"] = sha
            if path:
                kwargs["path"] = path
            if author:
                kwargs["author"] = author

            from datetime import datetime
            if since:
                kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if until:
                kwargs["until"] = datetime.fromisoformat(until.replace("Z", "+00:00"))

            commits = list(gh_repo.get_commits(**kwargs)[:min(per_page, 100)])
            items = [
                {
                    "sha": c.sha[:8],
                    "message": c.commit.message.split("\n")[0],
                    "author": c.commit.author.name,
                    "date": c.commit.author.date.isoformat(),
                }
                for c in commits
            ]
            text = f"Recent commits in {owner}/{repo}:\n" + "\n".join(
                f"  [{i['sha']}] {i['author']}: {i['message']}" for i in items
            )
            return ToolResult(tool="list_commits", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_commits")

    def _tool_get_commit(self, owner: str, repo: str, sha: str) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            c = gh_repo.get_commit(sha)
            data = {
                "sha": c.sha,
                "message": c.commit.message,
                "author": c.commit.author.name,
                "date": c.commit.author.date.isoformat(),
                "files_changed": [f.filename for f in c.files],
            }
            text = (
                f"Commit: {c.sha}\n"
                f"Author: {c.commit.author.name}\n"
                f"Date: {c.commit.author.date.isoformat()}\n"
                f"Message: {c.commit.message}\n"
                f"Files changed: {', '.join(f.filename for f in c.files)}"
            )
            return ToolResult(tool="get_commit", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "get_commit")

    def _tool_get_repository(self, owner: str, repo: str) -> ToolResult:
        try:
            r = self._gh.get_repo(f"{owner}/{repo}")
            data = {
                "full_name": r.full_name,
                "description": r.description,
                "language": r.language,
                "stars": r.stargazers_count,
                "forks": r.forks_count,
                "open_issues": r.open_issues_count,
                "default_branch": r.default_branch,
                "private": r.private,
                "url": r.html_url,
                "topics": r.get_topics(),
            }
            text = (
                f"Repository: {r.full_name}\n"
                f"Description: {r.description or 'N/A'}\n"
                f"Language: {r.language or 'N/A'}\n"
                f"Stars: {r.stargazers_count} | Forks: {r.forks_count} | Open Issues: {r.open_issues_count}\n"
                f"Default Branch: {r.default_branch}\n"
                f"URL: {r.html_url}"
            )
            return ToolResult(tool="get_repository", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "get_repository")

    def _tool_search_repositories(self, query: str, page: int = 1, per_page: int = 10) -> ToolResult:
        try:
            results = self._gh.search_repositories(query=query)
            items = []
            for r in list(results[:min(per_page, 30)]):
                items.append({
                    "full_name": r.full_name,
                    "description": r.description,
                    "stars": r.stargazers_count,
                    "language": r.language,
                    "url": r.html_url,
                })
            text = f"Repository search results for '{query}':\n" + "\n".join(
                f"  • {i['full_name']} ⭐{i['stars']} — {i['description'] or ''}" for i in items
            )
            return ToolResult(tool="search_repositories", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "search_repositories")

    def _tool_list_tags(self, owner: str, repo: str, per_page: int = 30) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            tags = list(gh_repo.get_tags()[:min(per_page, 100)])
            items = [{"name": t.name, "sha": t.commit.sha[:8]} for t in tags]
            text = f"Tags in {owner}/{repo}:\n" + "\n".join(f"  • {t['name']} ({t['sha']})" for t in items)
            return ToolResult(tool="list_tags", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_tags")

    # ------------------------------------------------------------------
    # READ — Issue tools
    # ------------------------------------------------------------------

    def _tool_list_issues(self, owner: str, repo: str, state: str = "open",
                          labels: str = None, assignee: str = None, per_page: int = 30) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            kwargs: Dict[str, Any] = {"state": state}
            if labels:
                kwargs["labels"] = [gh_repo.get_label(l.strip()) for l in labels.split(",") if l.strip()]
            if assignee:
                kwargs["assignee"] = assignee

            issues = list(gh_repo.get_issues(**kwargs)[:min(per_page, 100)])
            # Exclude PRs from issues list
            issues = [i for i in issues if not i.pull_request]
            items = [
                {
                    "number": i.number,
                    "title": i.title,
                    "state": i.state,
                    "author": i.user.login,
                    "created_at": i.created_at.isoformat(),
                    "url": i.html_url,
                    "labels": [l.name for l in i.labels],
                }
                for i in issues
            ]
            text = f"Issues in {owner}/{repo} ({state}):\n" + "\n".join(
                f"  #{i['number']}: {i['title']} [{i['state']}]" for i in items
            )
            return ToolResult(tool="list_issues", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_issues")

    def _tool_get_issue(self, owner: str, repo: str, issue_number: int) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            i = gh_repo.get_issue(issue_number)
            data = {
                "number": i.number,
                "title": i.title,
                "body": i.body,
                "state": i.state,
                "author": i.user.login,
                "created_at": i.created_at.isoformat(),
                "labels": [l.name for l in i.labels],
                "url": i.html_url,
            }
            text = (
                f"Issue #{i.number}: {i.title}\n"
                f"State: {i.state} | Author: {i.user.login}\n"
                f"Labels: {', '.join(l.name for l in i.labels) or 'none'}\n"
                f"URL: {i.html_url}\n\n"
                f"Body:\n{i.body or '(no body)'}"
            )
            return ToolResult(tool="get_issue", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "get_issue")

    def _tool_list_issue_comments(self, owner: str, repo: str, issue_number: int) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            issue = gh_repo.get_issue(issue_number)
            comments = list(issue.get_comments())
            items = [
                {
                    "id": c.id,
                    "author": c.user.login,
                    "body": c.body,
                    "created_at": c.created_at.isoformat(),
                }
                for c in comments
            ]
            text = f"Comments on issue #{issue_number} in {owner}/{repo}:\n\n" + "\n\n".join(
                f"@{c['author']} ({c['created_at'][:10]}):\n{c['body']}" for c in items
            )
            return ToolResult(tool="list_issue_comments", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_issue_comments")

    def _tool_search_issues(self, query: str, per_page: int = 10) -> ToolResult:
        try:
            results = self._gh.search_issues(query=query)
            items = []
            for i in list(results[:min(per_page, 50)]):
                items.append({
                    "number": i.number,
                    "title": i.title,
                    "state": i.state,
                    "repository": i.repository.full_name,
                    "url": i.html_url,
                })
            text = f"Search results for '{query}':\n" + "\n".join(
                f"  #{i['number']} [{i['repository']}]: {i['title']} ({i['state']})" for i in items
            )
            return ToolResult(tool="search_issues", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "search_issues")

    # ------------------------------------------------------------------
    # READ — Pull Request tools
    # ------------------------------------------------------------------

    def _tool_list_pull_requests(self, owner: str, repo: str, state: str = "open",
                                  head: str = None, base: str = None, per_page: int = 30) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            kwargs: Dict[str, Any] = {"state": state}
            if head:
                kwargs["head"] = head
            if base:
                kwargs["base"] = base
            prs = list(gh_repo.get_pulls(**kwargs)[:min(per_page, 100)])
            items = [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                    "head": pr.head.ref,
                    "base": pr.base.ref,
                    "url": pr.html_url,
                }
                for pr in prs
            ]
            text = f"Pull Requests in {owner}/{repo} ({state}):\n" + "\n".join(
                f"  #{i['number']}: {i['title']} [{i['head']} → {i['base']}]" for i in items
            )
            return ToolResult(tool="list_pull_requests", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_pull_requests")

    def _tool_get_pull_request(self, owner: str, repo: str, pull_number: int) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pull_number)
            data = {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "author": pr.user.login,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "merged": pr.merged,
                "url": pr.html_url,
            }
            text = (
                f"PR #{pr.number}: {pr.title}\n"
                f"State: {pr.state} | Author: {pr.user.login}\n"
                f"Head → Base: {pr.head.ref} → {pr.base.ref}\n"
                f"Merged: {pr.merged}\nURL: {pr.html_url}\n\n"
                f"Description:\n{pr.body or '(no description)'}"
            )
            return ToolResult(tool="get_pull_request", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "get_pull_request")

    def _tool_get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pull_number)
            # Collect file-level diffs
            files = []
            for f in pr.get_files():
                files.append({
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "patch": f.patch or "",
                })
            text = f"Diff for PR #{pull_number}:\n\n" + "\n\n".join(
                f"--- {f['filename']} ({f['status']}, +{f['additions']}/-{f['deletions']}) ---\n{f['patch']}"
                for f in files
            )
            return ToolResult(tool="get_pull_request_diff", success=True, data=files, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "get_pull_request_diff")

    def _tool_list_pull_request_comments(self, owner: str, repo: str, pull_number: int) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pull_number)
            comments = list(pr.get_review_comments())
            items = [
                {
                    "id": c.id,
                    "author": c.user.login,
                    "path": c.path,
                    "body": c.body,
                }
                for c in comments
            ]
            text = f"Review comments on PR #{pull_number}:\n\n" + "\n\n".join(
                f"@{c['author']} on {c['path']}:\n{c['body']}" for c in items
            )
            return ToolResult(tool="list_pull_request_comments", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "list_pull_request_comments")

    # ------------------------------------------------------------------
    # READ — Code Search
    # ------------------------------------------------------------------

    def _tool_search_code(self, query: str, per_page: int = 10) -> ToolResult:
        try:
            results = self._gh.search_code(query=query)
            items = []
            for r in list(results[:min(per_page, 30)]):
                items.append({
                    "path": r.path,
                    "repository": r.repository.full_name,
                    "url": r.html_url,
                    "sha": r.sha[:8],
                })
            text = f"Code search results for '{query}':\n" + "\n".join(
                f"  [{i['repository']}] {i['path']}" for i in items
            )
            return ToolResult(tool="search_code", success=True, data=items, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "search_code")

    # ------------------------------------------------------------------
    # WRITE — Issues
    # ------------------------------------------------------------------

    def _tool_create_issue(self, owner: str, repo: str, title: str,
                           body: str = "", labels: List[str] = None, assignees: List[str] = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            kwargs: Dict[str, Any] = {"title": title, "body": body or ""}
            if labels:
                try:
                    kwargs["labels"] = [gh_repo.get_label(l) for l in labels]
                except Exception:
                    pass  # Skip unknown labels
            if assignees:
                kwargs["assignees"] = assignees
            issue = gh_repo.create_issue(**kwargs)
            data = {
                "number": issue.number,
                "title": issue.title,
                "url": issue.html_url,
            }
            text = f"✅ Issue #{issue.number} created: '{issue.title}'\nURL: {issue.html_url}"
            return ToolResult(tool="create_issue", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "create_issue")

    def _tool_update_issue(self, owner: str, repo: str, issue_number: int,
                           title: str = None, body: str = None, state: str = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            issue = gh_repo.get_issue(issue_number)
            kwargs: Dict[str, Any] = {}
            if title is not None:
                kwargs["title"] = title
            if body is not None:
                kwargs["body"] = body
            if state is not None:
                kwargs["state"] = state
            issue.edit(**kwargs)
            text = f"✅ Issue #{issue_number} updated.\nURL: {issue.html_url}"
            return ToolResult(tool="update_issue", success=True, data={"number": issue_number, "url": issue.html_url}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "update_issue")

    def _tool_add_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            issue = gh_repo.get_issue(issue_number)
            comment = issue.create_comment(body)
            text = f"✅ Comment added to issue #{issue_number}.\nURL: {comment.html_url}"
            return ToolResult(tool="add_issue_comment", success=True, data={"id": comment.id, "url": comment.html_url}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "add_issue_comment")

    # ------------------------------------------------------------------
    # WRITE — Pull Requests
    # ------------------------------------------------------------------

    def _tool_create_pull_request(self, owner: str, repo: str, title: str, head: str, base: str,
                                   body: str = "", draft: bool = False) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            pr = gh_repo.create_pull(title=title, body=body or "", head=head, base=base, draft=draft)
            data = {"number": pr.number, "title": pr.title, "url": pr.html_url}
            text = f"✅ PR #{pr.number} created: '{pr.title}'\nURL: {pr.html_url}"
            return ToolResult(tool="create_pull_request", success=True, data=data, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "create_pull_request")

    def _tool_update_pull_request(self, owner: str, repo: str, pull_number: int,
                                   title: str = None, body: str = None, state: str = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pull_number)
            kwargs: Dict[str, Any] = {}
            if title is not None:
                kwargs["title"] = title
            if body is not None:
                kwargs["body"] = body
            if state is not None:
                kwargs["state"] = state
            pr.edit(**kwargs)
            text = f"✅ PR #{pull_number} updated.\nURL: {pr.html_url}"
            return ToolResult(tool="update_pull_request", success=True, data={"number": pull_number, "url": pr.html_url}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "update_pull_request")

    # ------------------------------------------------------------------
    # WRITE — Files
    # ------------------------------------------------------------------

    def _tool_create_or_update_file(self, owner: str, repo: str, path: str, message: str,
                                     content: str, branch: str = None, sha: str = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            kwargs: Dict[str, Any] = {
                "path": path,
                "message": message,
                "content": encoded,
            }
            if branch:
                kwargs["branch"] = branch

            # Try to get the existing file's SHA if not provided
            if sha:
                kwargs["sha"] = sha
            else:
                try:
                    existing = gh_repo.get_contents(path, ref=branch or gh_repo.default_branch)
                    if not isinstance(existing, list):
                        kwargs["sha"] = existing.sha
                except Exception:
                    pass  # File doesn't exist — creating new

            result = gh_repo.update_file(**kwargs) if "sha" in kwargs else gh_repo.create_file(**kwargs)
            commit = result.get("commit")
            url = commit.html_url if commit else f"https://github.com/{owner}/{repo}/blob/{branch or gh_repo.default_branch}/{path}"
            text = f"✅ File '{path}' committed.\nCommit: {url}"
            return ToolResult(tool="create_or_update_file", success=True, data={"path": path, "url": url}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "create_or_update_file")

    def _tool_push_files(self, owner: str, repo: str, branch: str, message: str, files: List[Dict]) -> ToolResult:
        """
        Push multiple files to a repository in a single commit using the Git Data API (tree + commit).
        Compatible with PyGithub 2.x.
        """
        try:
            # pyrefly: ignore [missing-import]
            from github import InputGitTreeElement
        except ImportError:
            InputGitTreeElement = None

        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            ref = gh_repo.get_git_ref(f"heads/{branch}")
            base_tree = gh_repo.get_git_tree(ref.object.sha)

            # Build tree blobs
            tree_elements = []
            for f in files:
                blob = gh_repo.create_git_blob(f["content"], "utf-8")
                if InputGitTreeElement is not None:
                    tree_elements.append(
                        InputGitTreeElement(
                            path=f["path"],
                            mode="100644",
                            type="blob",
                            sha=blob.sha,
                        )
                    )
                else:
                    # Fallback: use dict-style (older PyGithub)
                    tree_elements.append({
                        "path": f["path"],
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob.sha,
                    })

            new_tree = gh_repo.create_git_tree(tree_elements, base_tree)
            parent_commit = gh_repo.get_git_commit(ref.object.sha)
            new_commit = gh_repo.create_git_commit(message, new_tree, [parent_commit])
            ref.edit(new_commit.sha)

            text = f"✅ {len(files)} file(s) pushed to branch '{branch}' with message: {message}"
            return ToolResult(tool="push_files", success=True, data={"branch": branch, "sha": new_commit.sha}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "push_files")

    # ------------------------------------------------------------------
    # WRITE/DESTRUCTIVE — Branches
    # ------------------------------------------------------------------

    def _tool_create_branch(self, owner: str, repo: str, branch: str, from_branch: str = None) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            source_branch = from_branch or gh_repo.default_branch
            source_sha = gh_repo.get_branch(source_branch).commit.sha
            gh_repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source_sha)
            text = f"✅ Branch '{branch}' created from '{source_branch}' (SHA: {source_sha[:8]})"
            return ToolResult(tool="create_branch", success=True, data={"branch": branch, "sha": source_sha}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "create_branch")

    def _tool_delete_branch(self, owner: str, repo: str, branch: str) -> ToolResult:
        try:
            gh_repo = self._gh.get_repo(f"{owner}/{repo}")
            ref = gh_repo.get_git_ref(f"heads/{branch}")
            ref.delete()
            text = f"✅ Branch '{branch}' deleted from {owner}/{repo}."
            return ToolResult(tool="delete_branch", success=True, data={"branch": branch}, raw_text=text)
        except Exception as exc:
            self._handle_github_exception(exc, "delete_branch")

    # ------------------------------------------------------------------
    # Utility: generate diff for file modifications
    # ------------------------------------------------------------------

    @staticmethod
    def generate_diff(old_content: str, new_content: str, filename: str = "file") -> str:
        """Generate a unified diff string between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )
        return "".join(diff) or "(no changes)"
