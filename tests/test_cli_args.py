"""Tests for CLI argument parsing."""

from flake_review.cli import main


def test_cli_requires_command(monkeypatch, capsys):  # type: ignore
    """Test that CLI requires a command."""
    monkeypatch.setattr("sys.argv", ["flake-review"])

    try:
        main()
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower() or "usage:" in captured.err.lower()


def test_pr_command_requires_url(monkeypatch, capsys):  # type: ignore
    """Test that pr command requires a URL."""
    monkeypatch.setattr("sys.argv", ["flake-review", "pr"])

    try:
        main()
    except SystemExit as e:
        assert e.code != 0

    captured = capsys.readouterr()
    # Should show error about missing pr_url
    assert captured.err != "" or captured.out != ""
