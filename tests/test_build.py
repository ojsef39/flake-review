"""Tests for build functionality."""

from flake_review.build import BuildResult, BuildResults
from flake_review.flake import DerivationInfo


def test_build_result_success() -> None:
    """Test creating a successful build result."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.test",
        drv_path="/nix/store/test.drv",
        output_type="packages",
        system="x86_64-linux",
        name="test",
    )

    result = BuildResult(
        derivation=drv,
        success=True,
        output_path="/nix/store/test-output",
    )

    assert result.success is True
    assert result.output_path == "/nix/store/test-output"
    assert result.error is None


def test_build_result_failure() -> None:
    """Test creating a failed build result."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.test",
        drv_path="/nix/store/test.drv",
        output_type="packages",
        system="x86_64-linux",
        name="test",
    )

    result = BuildResult(
        derivation=drv,
        success=False,
        error="Build failed",
    )

    assert result.success is False
    assert result.error == "Build failed"
    assert result.output_path is None


def test_build_results_empty() -> None:
    """Test BuildResults with no results."""
    results = BuildResults(results=[])

    assert results.total_count == 0
    assert results.success_count == 0
    assert results.failure_count == 0
    assert len(results.successful) == 0
    assert len(results.failed) == 0


def test_build_results_mixed() -> None:
    """Test BuildResults with mixed success/failure."""
    drv1 = DerivationInfo(
        attr_path="packages.x86_64-linux.success",
        drv_path="/nix/store/success.drv",
        output_type="packages",
        system="x86_64-linux",
        name="success",
    )

    drv2 = DerivationInfo(
        attr_path="packages.x86_64-linux.failure",
        drv_path="/nix/store/failure.drv",
        output_type="packages",
        system="x86_64-linux",
        name="failure",
    )

    result1 = BuildResult(derivation=drv1, success=True)
    result2 = BuildResult(derivation=drv2, success=False, error="Failed")

    results = BuildResults(results=[result1, result2])

    assert results.total_count == 2
    assert results.success_count == 1
    assert results.failure_count == 1
    assert len(results.successful) == 1
    assert len(results.failed) == 1
    assert results.successful[0] == result1
    assert results.failed[0] == result2
