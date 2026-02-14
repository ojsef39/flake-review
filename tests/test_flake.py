"""Tests for flake output comparison."""

from flake_review.flake import ChangeSet, DerivationInfo


def test_derivation_info_creation() -> None:
    """Test creating a DerivationInfo."""
    drv = DerivationInfo(
        attr_path="packages.x86_64-linux.default",
        drv_path="/nix/store/abc-foo.drv",
        output_type="packages",
        system="x86_64-linux",
        name="default",
    )
    assert drv.attr_path == "packages.x86_64-linux.default"
    assert drv.system == "x86_64-linux"
    assert drv.name == "default"


def test_changeset_empty() -> None:
    """Test empty changeset."""
    changes = ChangeSet(added=[], removed=[], modified=[])
    assert len(changes.added) == 0
    assert len(changes.removed) == 0
    assert len(changes.modified) == 0


def test_changeset_with_changes() -> None:
    """Test changeset with actual changes."""
    added_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.new",
        drv_path="/nix/store/new.drv",
        output_type="packages",
        system="x86_64-linux",
        name="new",
    )

    removed_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.old",
        drv_path="/nix/store/old.drv",
        output_type="packages",
        system="x86_64-linux",
        name="old",
    )

    old_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.modified",
        drv_path="/nix/store/old-modified.drv",
        output_type="packages",
        system="x86_64-linux",
        name="modified",
    )

    new_drv = DerivationInfo(
        attr_path="packages.x86_64-linux.modified",
        drv_path="/nix/store/new-modified.drv",
        output_type="packages",
        system="x86_64-linux",
        name="modified",
    )

    changes = ChangeSet(
        added=[added_drv],
        removed=[removed_drv],
        modified=[(old_drv, new_drv)],
    )

    assert len(changes.added) == 1
    assert len(changes.removed) == 1
    assert len(changes.modified) == 1
    assert changes.added[0].name == "new"
    assert changes.removed[0].name == "old"
    assert changes.modified[0][0].drv_path == "/nix/store/old-modified.drv"
    assert changes.modified[0][1].drv_path == "/nix/store/new-modified.drv"
