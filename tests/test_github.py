"""Tests for GitHub integration."""

import pytest

from flake_review.github import PullRequest, parse_pr_url


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
