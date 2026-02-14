"""Tests for utility functions."""

from flake_review.utils import CommandError


def test_command_error() -> None:
    """Test CommandError exception."""
    error = CommandError(["git", "status"], 1, "fatal: not a git repository")

    assert error.returncode == 1
    assert error.stderr == "fatal: not a git repository"
    assert "git status" in str(error)
    assert "fatal: not a git repository" in str(error)
