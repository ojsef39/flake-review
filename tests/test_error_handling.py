"""Tests for error handling."""

import pytest

from flake_review.github import parse_pr_url
from flake_review.utils import CommandError


def test_command_error_formatting() -> None:
    """Test CommandError formats nicely."""
    error = CommandError(
        ["git", "fetch", "origin"],
        128,
        "fatal: couldn't find remote ref",
    )

    error_str = str(error)
    assert "git fetch origin" in error_str
    assert "fatal: couldn't find remote ref" in error_str


def test_parse_pr_url_rejects_invalid_urls() -> None:
    """Test that invalid PR URLs are rejected."""
    invalid_urls = [
        "not a url",
        "https://github.com/owner/repo",  # No PR number
        "https://github.com/owner",  # Incomplete
        "owner/repo",  # Missing PR number
        "",
    ]

    for url in invalid_urls:
        with pytest.raises(ValueError):
            parse_pr_url(url)


def test_parse_pr_url_accepts_valid_formats() -> None:
    """Test that valid PR URL formats are accepted."""
    valid_urls = [
        ("https://github.com/owner/repo/pull/123", "owner", "repo", 123),
        ("https://github.com/owner/repo/pulls/456", "owner", "repo", 456),
        ("owner/repo#789", "owner", "repo", 789),
    ]

    for url, expected_owner, expected_repo, expected_number in valid_urls:
        owner, repo, number = parse_pr_url(url)
        assert owner == expected_owner
        assert repo == expected_repo
        assert number == expected_number
