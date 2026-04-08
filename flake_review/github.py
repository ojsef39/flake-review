"""GitHub API integration for posting results to PRs."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass
class PullRequest:
    """GitHub pull request information."""

    owner: str
    repo: str
    number: int
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str
    head_repo_url: str | None = None  # For fork PRs

    @property
    def url(self) -> str:
        """Get the PR URL."""
        return f"https://github.com/{self.owner}/{self.repo}/pull/{self.number}"

    @property
    def api_url(self) -> str:
        """Get the API URL."""
        return (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.number}"
        )

    @property
    def is_fork(self) -> bool:
        """Check if this is a fork PR."""
        return self.head_repo_url is not None


class GithubClient:
    """Client for interacting with GitHub API."""

    _COMMENT_MARKER = "<!-- flake-review -->"
    _MAX_COMMENT_BODY_LENGTH = 65536

    def __init__(self, token: str | None = None):
        self.token = (
            token or self._get_token_from_env() or self._get_token_from_gh_cli()
        )

        if not self.token:
            raise RuntimeError(
                "No GitHub token found. Set GITHUB_TOKEN environment variable "
                "or authenticate with `gh auth login`"
            )

    def _get_token_from_env(self) -> str | None:
        """Get GitHub token from environment."""
        return os.environ.get("GITHUB_TOKEN")

    def _get_token_from_gh_cli(self) -> str | None:
        """Get GitHub token from gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated GitHub API request."""
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        request_data = None
        if data is not None:
            request_data = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=request_data, headers=headers, method=method)

        try:
            with urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(
                f"GitHub API error: {e.code} {e.reason}\n{error_body}"
            ) from e

    def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        """Fetch pull request information from GitHub."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        data = self._make_request(url)

        base_ref = data["base"]["ref"]
        base_sha = data["base"]["sha"]
        head_ref = data["head"]["ref"]
        head_sha = data["head"]["sha"]

        # Check if this is a fork PR
        head_repo_url = None
        head_repo = data["head"]["repo"]
        if head_repo and head_repo["full_name"] != f"{owner}/{repo}":
            head_repo_url = head_repo["clone_url"]
            head_label = data["head"]["label"]
            print(f"Fork PR: {head_label} -> {owner}/{repo}:{base_ref}")

        return PullRequest(
            owner=owner,
            repo=repo,
            number=number,
            base_ref=base_ref,
            base_sha=base_sha,
            head_ref=head_ref,
            head_sha=head_sha,
            head_repo_url=head_repo_url,
        )

    def _get_workflow_run_url(self) -> str | None:
        """Get the current GitHub Actions run URL, if available."""
        server_url = os.environ.get("GITHUB_SERVER_URL")
        repository = os.environ.get("GITHUB_REPOSITORY")
        run_id = os.environ.get("GITHUB_RUN_ID")
        if server_url and repository and run_id:
            return f"{server_url}/{repository}/actions/runs/{run_id}"
        return None

    def _truncate_comment_body(self, body: str) -> str:
        """Truncate comment body to fit GitHub's comment size limit."""
        marker_prefix = f"{self._COMMENT_MARKER}\n"
        max_body_len = self._MAX_COMMENT_BODY_LENGTH - len(marker_prefix)

        if len(body) <= max_body_len:
            return body

        notice_lines = [
            "",
            "",
            "---",
            (
                "Note: Report truncated to fit GitHub's "
                f"{self._MAX_COMMENT_BODY_LENGTH} character comment limit."
            ),
        ]
        workflow_run_url = self._get_workflow_run_url()
        if workflow_run_url:
            notice_lines.append(f"Full report in CI logs: {workflow_run_url}")
        notice = "\n".join(notice_lines)

        if len(notice) >= max_body_len:
            return notice[:max_body_len]

        keep_len = max_body_len - len(notice)
        truncated = body[:keep_len].rstrip()

        indent = "  "
        closure = ""
        if truncated.count("```") % 2 == 1:
            closure += f"\n{indent}```"

        open_details = truncated.count("<details>") - truncated.count("</details>")
        if open_details > 0:
            closure += (f"\n{indent}</details>") * open_details

        if closure:
            available = keep_len - len(closure)
            if available < 0:
                available = 0
            truncated = body[:available].rstrip() + closure

        return f"{truncated}{notice}"

    def _find_existing_comment(self, pr: PullRequest) -> int | None:
        """Find an existing flake-review comment on a PR."""
        url = f"https://api.github.com/repos/{pr.owner}/{pr.repo}/issues/{pr.number}/comments"
        comments = self._make_request(url)
        for comment in comments:
            if self._COMMENT_MARKER in comment.get("body", ""):
                return int(comment["id"])
        return None

    def post_comment(self, pr: PullRequest, body: str) -> None:
        """Post or update a flake-review comment on a pull request."""
        safe_body = self._truncate_comment_body(body)
        body_with_marker = f"{self._COMMENT_MARKER}\n{safe_body}"

        existing_id = self._find_existing_comment(pr)
        if existing_id:
            url = f"https://api.github.com/repos/{pr.owner}/{pr.repo}/issues/comments/{existing_id}"
            self._make_request(url, method="PATCH", data={"body": body_with_marker})
        else:
            url = f"https://api.github.com/repos/{pr.owner}/{pr.repo}/issues/{pr.number}/comments"
            self._make_request(url, method="POST", data={"body": body_with_marker})


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL into (owner, repo, number).

    Supports formats:
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pulls/123
    - owner/repo#123
    """
    # Try full URL format
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pulls?/(\d+)", url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    # Try short format
    match = re.match(r"([^/]+)/([^#]+)#(\d+)", url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    raise ValueError(
        f"Invalid PR URL format: {url}\n"
        "Expected: https://github.com/owner/repo/pull/123 or owner/repo#123"
    )
