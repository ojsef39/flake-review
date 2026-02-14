"""Tests for report generation."""

from unittest.mock import patch

from flake_review.build import BuildResult, BuildResults
from flake_review.flake import ChangeSet, DerivationInfo
from flake_review.report import (
    _render_markdown_from_json,
    format_detailed_changes,
    generate_json_report,
    generate_markdown_report,
)


def test_format_detailed_changes_added() -> None:
    """Test detailed changes for added packages."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.new",
        drv_path="/nix/store/new.drv",
        output_type="packages",
        system="x86_64-linux",
        name="new",
    )

    changes = ChangeSet(added=[drv], removed=[], modified=[])
    results = BuildResults(results=[])

    result = format_detailed_changes(changes, results)
    assert "Added (1)" in result
    assert "packages.x86_64-linux.new" in result


def test_format_detailed_changes_modified_no_diff() -> None:
    """Test detailed changes for modified packages when nix-diff is unavailable."""
    old_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )
    new_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/new.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )

    changes = ChangeSet(added=[], removed=[], modified=[(old_drv, new_drv)])
    results = BuildResults(results=[])

    result = format_detailed_changes(changes, results)
    assert "Modified (1)" in result
    assert "packages.x86_64-linux.pkg" in result


def test_format_detailed_changes_removed() -> None:
    """Test detailed changes for removed packages."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.old",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="old",
    )

    changes = ChangeSet(added=[], removed=[drv], modified=[])
    results = BuildResults(results=[])

    result = format_detailed_changes(changes, results)
    assert "Removed (1)" in result
    assert "packages.x86_64-linux.old" in result


def test_format_detailed_changes_with_build_results() -> None:
    """Test detailed changes include build result status."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/pkg.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )

    changes = ChangeSet(added=[drv], removed=[], modified=[])
    build_result = BuildResult(
        derivation=drv,
        success=True,
        output_path="/nix/store/pkg-out",
    )
    results = BuildResults(results=[build_result])

    result = format_detailed_changes(changes, results)
    assert "/nix/store/pkg-out" in result


def test_generate_markdown_report() -> None:
    """Test generating a complete markdown report."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.default",
        drv_path="/nix/store/abc.drv",
        output_type="packages",
        system="x86_64-linux",
        name="default",
    )

    changes = ChangeSet(added=[drv], removed=[], modified=[])

    build_result = BuildResult(
        derivation=drv,
        success=True,
        output_path="/nix/store/abc-out",
    )

    results = BuildResults(results=[build_result])

    report = generate_markdown_report(changes, results, title="Test Report")

    assert "# Test Report" in report
    assert "Added (1)" in report
    assert "packages.x86_64-linux.default" in report
    assert "flake-review" in report


def test_generate_markdown_report_with_systems() -> None:
    """Test markdown report includes system info."""
    changes = ChangeSet(added=[], removed=[], modified=[])
    results = BuildResults(results=[])

    report = generate_markdown_report(
        changes,
        results,
        requested_systems=["x86_64-linux", "aarch64-darwin"],
        available_systems={"x86_64-linux", "aarch64-darwin", "aarch64-linux"},
    )

    assert "Requested systems:" in report
    assert "x86_64-linux" in report
    assert "Available systems:" in report
    assert "aarch64-linux" in report


def test_format_detailed_changes_build_error_markdown() -> None:
    """Test that build errors are shown in collapsible details block."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.broken",
        drv_path="/nix/store/broken.drv",
        output_type="packages",
        system="x86_64-linux",
        name="broken",
    )

    changes = ChangeSet(added=[drv], removed=[], modified=[])
    build_result = BuildResult(
        derivation=drv,
        success=False,
        error="SQLite warning\nerror: builder failed\nactual error",
    )
    results = BuildResults(results=[build_result])

    result = format_detailed_changes(changes, results, markdown=True)
    assert "<details>" in result
    assert "Build error" in result
    assert "actual error" in result


def test_format_detailed_changes_build_error_console() -> None:
    """Test that build errors show last lines in console mode."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.broken",
        drv_path="/nix/store/broken.drv",
        output_type="packages",
        system="x86_64-linux",
        name="broken",
    )

    changes = ChangeSet(added=[drv], removed=[], modified=[])
    build_result = BuildResult(
        derivation=drv,
        success=False,
        error="error (ignored): SQLite warning\nactual error here",
    )
    results = BuildResults(results=[build_result])

    result = format_detailed_changes(changes, results, markdown=False)
    assert "actual error" in result
    assert "<details>" not in result


def test_generate_json_report_structure() -> None:
    """Test JSON report has correct structure."""
    added_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.new",
        drv_path="/nix/store/new.drv",
        output_type="packages",
        system="x86_64-linux",
        name="new",
    )
    old_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )
    new_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.pkg",
        drv_path="/nix/store/new-pkg.drv",
        output_type="packages",
        system="x86_64-linux",
        name="pkg",
    )
    removed_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.gone",
        drv_path="/nix/store/gone.drv",
        output_type="packages",
        system="x86_64-linux",
        name="gone",
    )

    changes = ChangeSet(
        added=[added_drv],
        removed=[removed_drv],
        modified=[(old_drv, new_drv)],
    )
    build_result = BuildResult(
        derivation=added_drv,
        success=True,
        output_path="/nix/store/new-out",
    )
    results = BuildResults(results=[build_result])

    with patch("flake_review.report._get_nix_diff", return_value="fake diff"):
        data = generate_json_report(
            changes,
            results,
            requested_systems=["x86_64-linux"],
            available_systems={"x86_64-linux", "aarch64-darwin"},
        )

    assert data["version"] == 1
    assert "x86_64-linux" in data["metadata"]["requested_systems"]
    assert "aarch64-darwin" in data["metadata"]["available_systems"]

    assert len(data["changes"]["added"]) == 1
    assert data["changes"]["added"][0]["attr_path"] == "packages.x86_64-linux.new"
    assert data["changes"]["added"][0]["build"]["success"] is True

    assert len(data["changes"]["removed"]) == 1
    assert data["changes"]["removed"][0]["name"] == "gone"

    assert len(data["changes"]["modified"]) == 1
    assert data["changes"]["modified"][0]["nix_diff"] == "fake diff"
    assert data["changes"]["modified"][0]["old"]["drv_path"] == "/nix/store/old.drv"


def test_render_markdown_from_json() -> None:
    """Test rendering markdown from JSON data produces unified report."""
    data = {
        "version": 1,
        "metadata": {
            "requested_systems": ["x86_64-linux", "aarch64-darwin"],
            "available_systems": ["x86_64-linux", "aarch64-darwin"],
        },
        "changes": {
            "added": [
                {
                    "attr_path": "packages.x86_64-linux.new",
                    "drv_path": "/nix/store/new.drv",
                    "output_type": "packages",
                    "system": "x86_64-linux",
                    "name": "new",
                    "build": {
                        "success": True,
                        "output_path": "/nix/store/new-out",
                        "error": None,
                    },
                }
            ],
            "removed": [],
            "modified": [
                {
                    "old": {
                        "attr_path": "packages.aarch64-darwin.pkg",
                        "drv_path": "/nix/store/old.drv",
                        "output_type": "packages",
                        "system": "aarch64-darwin",
                        "name": "pkg",
                    },
                    "new": {
                        "attr_path": "packages.aarch64-darwin.pkg",
                        "drv_path": "/nix/store/new.drv",
                        "output_type": "packages",
                        "system": "aarch64-darwin",
                        "name": "pkg",
                    },
                    "nix_diff": "- old input\n+ new input",
                    "build": {
                        "success": True,
                        "output_path": "/nix/store/pkg-out",
                        "error": None,
                    },
                }
            ],
        },
    }

    md = _render_markdown_from_json(data, title="Test Report")

    assert "# Test Report" in md
    assert "Added (1)" in md
    assert "Modified (1)" in md
    assert "packages.x86_64-linux.new" in md
    assert "packages.aarch64-darwin.pkg" in md
    assert "- old input" in md
    assert "+ new input" in md
    assert "flake-review" in md


def test_build_results_properties() -> None:
    """Test BuildResults helper properties."""
    drv1 = DerivationInfo(
        attr_path="packages.x86_64-linux.success",
        drv_path="/nix/store/abc.drv",
        output_type="packages",
        system="x86_64-linux",
        name="success",
    )

    drv2 = DerivationInfo(
        attr_path="packages.x86_64-linux.failure",
        drv_path="/nix/store/def.drv",
        output_type="packages",
        system="x86_64-linux",
        name="failure",
    )

    build_result1 = BuildResult(derivation=drv1, success=True)
    build_result2 = BuildResult(derivation=drv2, success=False)

    results = BuildResults(results=[build_result1, build_result2])

    assert results.total_count == 2
    assert results.success_count == 1
    assert results.failure_count == 1
    assert len(results.successful) == 1
    assert len(results.failed) == 1
    assert results.successful[0].derivation.name == "success"
    assert results.failed[0].derivation.name == "failure"
