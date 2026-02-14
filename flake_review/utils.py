"""Utility functions for git operations and temporary directories."""

import shutil
import subprocess
import tempfile
from pathlib import Path


class CommandError(Exception):
    """Raised when a command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed: {' '.join(cmd)}\n{stderr}")


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture_output,
        text=True,
        check=False,
    )

    if check and result.returncode != 0:
        raise CommandError(cmd, result.returncode, result.stderr)

    return result


def get_git_root(path: Path | None = None) -> Path:
    """Get the root of the git repository."""
    if path is None:
        path = Path.cwd()

    result = run_command(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
    )
    return Path(result.stdout.strip())


def get_current_system() -> str:
    """Get the current Nix system string (e.g., x86_64-linux, aarch64-darwin)."""
    result = run_command(
        ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"]
    )
    return result.stdout.strip()


class GitWorktree:
    """Manages a git worktree for temporary checkouts."""

    def __init__(self, repo_path: Path, ref: str):
        self.repo_path = repo_path
        self.ref = ref
        self.worktree_path: Path | None = None

    def __enter__(self) -> Path:
        """Create a temporary worktree."""
        self.worktree_path = Path(tempfile.mkdtemp(prefix="flake-review-"))

        # Create worktree
        run_command(
            ["git", "worktree", "add", "--detach", str(self.worktree_path), self.ref],
            cwd=self.repo_path,
        )

        return self.worktree_path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Remove the temporary worktree."""
        if self.worktree_path is not None:
            # Remove worktree
            run_command(
                ["git", "worktree", "remove", "--force", str(self.worktree_path)],
                cwd=self.repo_path,
                check=False,  # Don't fail if already removed
            )

            # Clean up temp directory if it still exists
            if self.worktree_path.exists():
                shutil.rmtree(self.worktree_path)
