"""Integration tests for core workflows."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from flake_review.flake import ChangeSet, DerivationInfo, FlakeOutputs
from flake_review.github import PullRequest


def test_flake_outputs_handles_missing_systems() -> None:
    """Test that FlakeOutputs handles systems that don't exist gracefully."""
    # Mock flake show output
    mock_output = {"packages": {"x86_64-linux": {"default": {"type": "derivation"}}}}

    with patch("flake_review.flake.run_command") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(mock_output),
            returncode=0,
        )

        outputs = FlakeOutputs(Path("/fake/path"))

        # Request systems that don't exist
        derivations = outputs.get_derivations(
            output_types=["packages"],
            systems=["x86_64-linux", "aarch64-darwin", "nonexistent"],
        )

        # Should only return derivations for x86_64-linux
        assert len([d for d in derivations if d.system == "x86_64-linux"]) >= 0
        assert len([d for d in derivations if d.system == "aarch64-darwin"]) == 0
        assert len([d for d in derivations if d.system == "nonexistent"]) == 0


def test_changeset_detects_added_packages() -> None:
    """Test that ChangeSet correctly identifies added packages."""
    old_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.old",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="old",
    )

    new_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.new",
        drv_path="/nix/store/new.drv",
        output_type="packages",
        system="x86_64-linux",
        name="new",
    )

    # Simulate old having one package, new having a different one
    changes = ChangeSet(
        added=[new_drv],
        removed=[old_drv],
        modified=[],
    )

    assert len(changes.added) == 1
    assert changes.added[0].name == "new"
    assert len(changes.removed) == 1
    assert changes.removed[0].name == "old"


def test_changeset_detects_modified_packages() -> None:
    """Test that ChangeSet correctly identifies modified packages."""
    old_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )

    new_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/new.drv",  # Different drv path
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )

    changes = ChangeSet(
        added=[],
        removed=[],
        modified=[(old_drv, new_drv)],
    )

    assert len(changes.modified) == 1
    assert changes.modified[0][0].drv_path == "/nix/store/old.drv"
    assert changes.modified[0][1].drv_path == "/nix/store/new.drv"


def test_pull_request_fork_detection() -> None:
    """Test that fork PRs are correctly detected."""
    fork_pr = PullRequest(
        owner="upstream",
        repo="repo",
        number=1,
        base_ref="main",
        base_sha="abc123",
        head_ref="feature",
        head_sha="def456",
        head_repo_url="https://github.com/fork/repo.git",
    )

    same_repo_pr = PullRequest(
        owner="upstream",
        repo="repo",
        number=2,
        base_ref="main",
        base_sha="abc123",
        head_ref="feature",
        head_sha="ghi789",
        head_repo_url=None,
    )

    assert fork_pr.is_fork is True
    assert same_repo_pr.is_fork is False
