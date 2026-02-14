"""Flake output discovery and comparison."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import run_command


@dataclass
class DerivationInfo:
    """Information about a flake derivation."""

    attr_path: str  # e.g., "packages.x86_64-linux.default"
    drv_path: str  # e.g., "/nix/store/...-foo.drv"
    output_type: str  # "packages", "devShells", "apps"
    system: str  # e.g., "x86_64-linux"
    name: str  # e.g., "default"


@dataclass
class ChangeSet:
    """Set of changes between two flake outputs."""

    added: list[DerivationInfo]
    removed: list[DerivationInfo]
    modified: list[tuple[DerivationInfo, DerivationInfo]]  # (old, new)


class FlakeOutputs:
    """Represents the outputs of a flake."""

    def __init__(self, flake_path: Path):
        self.flake_path = flake_path
        self._outputs: dict[str, Any] | None = None
        self._derivations: list[DerivationInfo] | None = None

    def _get_raw_outputs(
        self,
        output_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get flake outputs for specified types.

        Uses targeted nix eval per output type instead of
        nix flake show --all-systems, which would evaluate
        everything (including devShells that may fail).
        """
        if self._outputs is not None:
            return self._outputs

        if output_types is None:
            output_types = ["packages"]

        outputs: dict[str, Any] = {}

        for output_type in output_types:
            try:
                result = run_command(
                    [
                        "nix",
                        "eval",
                        "--no-eval-cache",
                        f"{self.flake_path}#{output_type}",
                        "--json",
                        "--apply",
                        "x: builtins.mapAttrs (_: builtins.attrNames) x",
                    ],
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    raw = json.loads(result.stdout)
                    outputs[output_type] = {
                        system: {name: {"type": "derivation"} for name in names}
                        for system, names in raw.items()
                    }
            except Exception:
                continue

        self._outputs = outputs
        return self._outputs

    def _traverse_outputs(
        self,
        outputs: dict[str, Any],
        output_type: str,
        system: str,
    ) -> list[tuple[str, str]]:
        """Traverse output structure to find derivations.

        Returns list of (name, attr_path) tuples.
        """
        results = []

        def recurse(obj: Any, path: list[str]) -> None:
            if isinstance(obj, dict):
                if obj.get("type") == "derivation":
                    name = path[-1] if path else "unknown"
                    attr_path = f"{output_type}.{system}.{'.'.join(path)}"
                    results.append((name, attr_path))
                else:
                    for key, value in obj.items():
                        recurse(value, path + [key])

        if output_type in outputs and system in outputs[output_type]:
            recurse(outputs[output_type][system], [])

        return results

    def get_derivations(
        self,
        output_types: list[str] | None = None,
        systems: list[str] | None = None,
        package_filter: list[str] | None = None,
    ) -> list[DerivationInfo]:
        """Get all derivations from the flake.

        Args:
            output_types: List of output types to include (default: ["packages"])
            systems: List of systems to include (default: all found systems)
            package_filter: List of package names to include (default: all)
        """
        if (
            self._derivations is not None
            and output_types is None
            and systems is None
            and package_filter is None
        ):
            return self._derivations

        if output_types is None:
            output_types = ["packages"]

        raw_outputs = self._get_raw_outputs(output_types)

        if systems is None:
            systems_set = set()
            for output_type in output_types:
                if output_type in raw_outputs:
                    systems_set.update(raw_outputs[output_type].keys())
            systems = list(systems_set)

        derivations = []

        for output_type in output_types:
            if output_type not in raw_outputs:
                continue

            for system in systems:
                if system not in raw_outputs[output_type]:
                    continue

                attr_list = self._traverse_outputs(raw_outputs, output_type, system)

                for name, attr_path in attr_list:
                    if package_filter is not None and name not in package_filter:
                        continue

                    drv_path = self._get_derivation_path(attr_path)

                    if drv_path:
                        derivations.append(
                            DerivationInfo(
                                attr_path=attr_path,
                                drv_path=drv_path,
                                output_type=output_type,
                                system=system,
                                name=name,
                            )
                        )

        if output_types == ["packages"] and systems is None and package_filter is None:
            self._derivations = derivations

        return derivations

    def _get_derivation_path(self, attr_path: str) -> str | None:
        """Get the derivation store path for a flake attribute."""
        try:
            result = run_command(
                [
                    "nix",
                    "eval",
                    "--no-eval-cache",
                    f"{self.flake_path}#{attr_path}.drvPath",
                    "--raw",
                ],
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None


def compare_outputs(
    base: FlakeOutputs,
    target: FlakeOutputs,
    output_types: list[str] | None = None,
    systems: list[str] | None = None,
    package_filter: list[str] | None = None,
) -> ChangeSet:
    """Compare two flake outputs and return the changes.

    Args:
        base: Base flake outputs
        target: Target flake outputs (e.g., PR branch)
        output_types: List of output types to compare (default: ["packages"])
        systems: List of systems to compare (default: all systems)
        package_filter: List of package names to include (default: all)
    """
    base_derivations = base.get_derivations(output_types, systems, package_filter)
    target_derivations = target.get_derivations(output_types, systems, package_filter)

    base_map = {drv.attr_path: drv for drv in base_derivations}
    target_map = {drv.attr_path: drv for drv in target_derivations}

    added = []
    removed = []
    modified = []

    for attr_path, target_drv in target_map.items():
        if attr_path not in base_map:
            added.append(target_drv)
        elif base_map[attr_path].drv_path != target_drv.drv_path:
            modified.append((base_map[attr_path], target_drv))

    for attr_path, base_drv in base_map.items():
        if attr_path not in target_map:
            removed.append(base_drv)

    return ChangeSet(added=added, removed=removed, modified=modified)
