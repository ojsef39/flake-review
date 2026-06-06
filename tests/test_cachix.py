"""Tests for cachix push functionality."""

from unittest.mock import MagicMock, patch

from flake_review.build import BuildResult, BuildResults
from flake_review.cachix import collect_store_paths, push_to_cachix
from flake_review.flake import DerivationInfo


def _drv(name: str) -> DerivationInfo:
    return DerivationInfo(
        attr_path=f"packages.x86_64-linux.{name}",
        drv_path=f"/nix/store/{name}.drv",
        output_type="packages",
        system="x86_64-linux",
        name=name,
    )


def test_collect_store_paths_empty() -> None:
    """No results means no paths."""
    assert collect_store_paths(BuildResults(results=[])) == []


def test_collect_store_paths_skips_failures() -> None:
    """Only successful builds contribute paths."""
    results = BuildResults(
        results=[
            BuildResult(
                derivation=_drv("ok"), success=True, output_path="/nix/store/ok"
            ),
            BuildResult(derivation=_drv("bad"), success=False, error="boom"),
        ]
    )
    assert collect_store_paths(results) == ["/nix/store/ok"]


def test_collect_store_paths_multi_output() -> None:
    """Multi-output derivations yield one path per line."""
    results = BuildResults(
        results=[
            BuildResult(
                derivation=_drv("multi"),
                success=True,
                output_path="/nix/store/multi-out\n/nix/store/multi-dev\n",
            ),
        ]
    )
    assert collect_store_paths(results) == [
        "/nix/store/multi-out",
        "/nix/store/multi-dev",
    ]


def test_push_to_cachix_nothing_to_push() -> None:
    """Pushing with no paths succeeds without invoking cachix."""
    with patch("flake_review.cachix.run_command") as mock_run:
        assert push_to_cachix("my-cache", BuildResults(results=[])) is True
        mock_run.assert_not_called()


def test_push_to_cachix_missing_binary() -> None:
    """Missing cachix executable fails the push."""
    results = BuildResults(
        results=[
            BuildResult(
                derivation=_drv("ok"), success=True, output_path="/nix/store/ok"
            ),
        ]
    )
    with patch("flake_review.cachix.shutil.which", return_value=None):
        assert push_to_cachix("my-cache", results) is False


def test_push_to_cachix_success() -> None:
    """Successful push invokes cachix with cache name and paths."""
    results = BuildResults(
        results=[
            BuildResult(derivation=_drv("a"), success=True, output_path="/nix/store/a"),
            BuildResult(derivation=_drv("b"), success=True, output_path="/nix/store/b"),
        ]
    )
    mock_result = MagicMock(returncode=0)
    with (
        patch("flake_review.cachix.shutil.which", return_value="/bin/cachix"),
        patch("flake_review.cachix.run_command", return_value=mock_result) as mock_run,
    ):
        assert push_to_cachix("my-cache", results) is True
        mock_run.assert_called_once_with(
            ["cachix", "push", "my-cache", "/nix/store/a", "/nix/store/b"],
            check=False,
        )


def test_push_to_cachix_failure() -> None:
    """Failed cachix push returns False."""
    results = BuildResults(
        results=[
            BuildResult(derivation=_drv("a"), success=True, output_path="/nix/store/a"),
        ]
    )
    mock_result = MagicMock(returncode=1, stderr="permission denied")
    with (
        patch("flake_review.cachix.shutil.which", return_value="/bin/cachix"),
        patch("flake_review.cachix.run_command", return_value=mock_result),
    ):
        assert push_to_cachix("my-cache", results) is False
