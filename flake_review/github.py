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

    _COMMENT_MARKER = "<!-- flake-review -->"

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
        body_with_marker = f"{self._COMMENT_MARKER}\n{body}"

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
