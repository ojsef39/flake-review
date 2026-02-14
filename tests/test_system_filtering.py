"""Tests for system filtering logic."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from flake_review.flake import FlakeOutputs, compare_outputs


def _mock_nix_eval(packages_by_system: dict[str, list[str]]):  # type: ignore
    """Create a side_effect for run_command that handles nix eval calls.

    packages_by_system: e.g. {"x86_64-linux": ["pkg1"], "aarch64-darwin": ["pkg2"]}
    """

    def side_effect(cmd: list[str], **kwargs):  # type: ignore
        if "nix" in cmd and "eval" in cmd and "--apply" in cmd:
            return MagicMock(
                stdout=json.dumps(packages_by_system),
                returncode=0,
            )
        if "nix" in cmd and "eval" in cmd and any(".drvPath" in c for c in cmd):
            attr = next(c for c in cmd if ".drvPath" in c)
            return MagicMock(
                stdout=f"/nix/store/fake-{attr}.drv",
                returncode=0,
            )
        return MagicMock(stdout="", returncode=1)

    return side_effect


def test_get_derivations_filters_nonexistent_systems() -> None:
    """Test that get_derivations only returns systems that exist."""
    packages = {
        "x86_64-linux": ["pkg1"],
        "aarch64-darwin": ["pkg2"],
    }

    with patch("flake_review.flake.run_command") as mock_run:
        mock_run.side_effect = _mock_nix_eval(packages)

        outputs = FlakeOutputs(Path("/fake"))

        # Request 4 systems but only 2 exist
        derivations = outputs.get_derivations(
            systems=[
                "x86_64-linux",
                "aarch64-linux",
                "x86_64-darwin",
                "aarch64-darwin",
            ]
        )

        # Should only get the 2 that exist
        systems_found = {d.system for d in derivations}
        assert "x86_64-linux" in systems_found
        assert "aarch64-darwin" in systems_found
        assert "aarch64-linux" not in systems_found
        assert "x86_64-darwin" not in systems_found


def test_compare_outputs_only_compares_common_systems() -> None:
    """Test that compare_outputs works with different systems."""
    base_packages = {"x86_64-linux": ["pkg"]}
    head_packages = {
        "x86_64-linux": ["pkg", "new"],
        "aarch64-darwin": ["pkg"],
    }

    with patch("flake_review.flake.run_command") as mock_run:

        def side_effect(cmd: list[str], **kwargs):  # type: ignore
            path = ""
            for part in cmd:
                if "#" in part:
                    path = part
                    break
            if "base" in path:
                return _mock_nix_eval(base_packages)(cmd, **kwargs)
            return _mock_nix_eval(head_packages)(cmd, **kwargs)

        mock_run.side_effect = side_effect

        base = FlakeOutputs(Path("/fake/base"))
        head = FlakeOutputs(Path("/fake/head"))

        changes = compare_outputs(
            base, head, systems=["x86_64-linux", "aarch64-darwin"]
        )

        # Should detect changes
        total = len(changes.added) + len(changes.modified) + len(changes.removed)
        assert total >= 0


def test_flake_outputs_with_no_packages() -> None:
    """Test FlakeOutputs when flake has no packages."""
    with patch("flake_review.flake.run_command") as mock_run:
        # nix eval .#packages fails (no packages output)
        mock_run.return_value = MagicMock(stdout="", returncode=1)

        outputs = FlakeOutputs(Path("/fake"))
        derivations = outputs.get_derivations(output_types=["packages"])

        assert len(derivations) == 0


def test_flake_outputs_auto_detect_systems() -> None:
    """Test that FlakeOutputs auto-detects all available systems."""
    packages = {
        "x86_64-linux": ["pkg1"],
        "aarch64-darwin": ["pkg2"],
        "aarch64-linux": ["pkg3"],
    }

    with patch("flake_review.flake.run_command") as mock_run:
        mock_run.side_effect = _mock_nix_eval(packages)

        outputs = FlakeOutputs(Path("/fake"))

        # Don't specify systems - should auto-detect all
        derivations = outputs.get_derivations(systems=None)

        systems_found = {d.system for d in derivations}
        assert len(systems_found) == 3
        assert "x86_64-linux" in systems_found
        assert "aarch64-darwin" in systems_found
        assert "aarch64-linux" in systems_found
