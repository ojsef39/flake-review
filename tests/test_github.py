"""Tests for GitHub integration."""

import pytest

from flake_review.github import GithubClient, PullRequest, parse_pr_url


def test_parse_pr_url_full() -> None:
    """Test parsing full GitHub PR URLs."""
    owner, repo, number = parse_pr_url("https://github.com/owner/repo/pull/123")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 123


def test_parse_pr_url_pulls() -> None:
    """Test parsing PR URLs with 'pulls'."""
    owner, repo, number = parse_pr_url("https://github.com/owner/repo/pulls/456")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 456


def test_parse_pr_url_short() -> None:
    """Test parsing short format PR URLs."""
    owner, repo, number = parse_pr_url("owner/repo#789")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 789


def test_parse_pr_url_invalid() -> None:
    """Test parsing invalid PR URLs."""
    with pytest.raises(ValueError):
        parse_pr_url("not a valid url")

    with pytest.raises(ValueError):
        parse_pr_url("https://github.com/owner/repo")


def test_pull_request_same_repo() -> None:
    """Test PullRequest for same-repo PR."""
    pr = PullRequest(
        owner="owner",
        repo="repo",
        number=123,
        base_ref="main",
        base_sha="abc123",
        head_ref="feature",
        head_sha="def456",
        head_repo_url=None,
    )

    assert pr.is_fork is False
    assert pr.url == "https://github.com/owner/repo/pull/123"
    assert pr.api_url == "https://api.github.com/repos/owner/repo/pulls/123"


def test_pull_request_fork() -> None:
    """Test PullRequest for fork PR."""
    pr = PullRequest(
        owner="upstream",
        repo="repo",
        number=456,
        base_ref="main",
        base_sha="abc123",
        head_ref="feature",
        head_sha="def456",
        head_repo_url="https://github.com/fork/repo.git",
    )

    assert pr.is_fork is True
    assert pr.head_repo_url == "https://github.com/fork/repo.git"
    assert pr.url == "https://github.com/upstream/repo/pull/456"


def test_truncate_comment_body_no_truncation() -> None:
    """Test comment body remains unchanged when below max length."""
    client = GithubClient.__new__(GithubClient)
    body = "short comment"
    assert client._truncate_comment_body(body) == body


def test_truncate_comment_body_with_ci_link(monkeypatch) -> None:  # type: ignore
    """Test truncation appends notice and CI run URL."""
    client = GithubClient.__new__(GithubClient)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    body = "A" * (GithubClient._MAX_COMMENT_BODY_LENGTH + 1000)
    truncated = client._truncate_comment_body(body)

    assert "Report truncated" in truncated
    assert "https://github.com/owner/repo/actions/runs/12345" in truncated
    marker_len = len(f"{GithubClient._COMMENT_MARKER}\n")
    assert len(truncated) <= GithubClient._MAX_COMMENT_BODY_LENGTH - marker_len


def test_truncate_comment_body_closes_markdown_blocks() -> None:
    """Test truncation closes open code fences and details blocks."""
    client = GithubClient.__new__(GithubClient)
    body = "<details>\n```diff\n" + ("x" * 70000)

    truncated = client._truncate_comment_body(body)

    assert truncated.count("```") % 2 == 0
    assert truncated.count("<details>") <= truncated.count("</details>")
    assert "\n  ```" in truncated
    assert "\n  </details>" in truncated


def test_truncate_comment_body_closes_multiple_details() -> None:
    """Test truncation closes all open details blocks."""
    client = GithubClient.__new__(GithubClient)
    body = "<details>\n<details>\n" + ("x" * 70000)

    truncated = client._truncate_comment_body(body)

    assert truncated.count("<details>") <= truncated.count("</details>")
