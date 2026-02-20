"""Build derivations and collect results."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .flake import ChangeSet, DerivationInfo
from .utils import run_command


@dataclass
class BuildResult:
    """Result of building a single derivation."""

    derivation: DerivationInfo
    success: bool
    output_path: str | None = None
    error: str | None = None
    build_log: str | None = None


@dataclass
class BuildResults:
    """Collection of build results."""

    results: list[BuildResult]

    @property
    def successful(self) -> list[BuildResult]:
        """Get successful builds."""
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[BuildResult]:
        """Get failed builds."""
        return [r for r in self.results if not r.success]

    @property
    def total_count(self) -> int:
        """Total number of builds."""
        return len(self.results)

    @property
    def success_count(self) -> int:
        """Number of successful builds."""
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        """Number of failed builds."""
        return len(self.failed)


def build_derivation(
    flake_path: Path,
    derivation: DerivationInfo,
) -> BuildResult:
    """Build a single derivation.

    Args:
        flake_path: Path to the flake
        derivation: Derivation to build
    """
    try:
        result = run_command(
            [
                "nix",
                "build",
                f"{flake_path}#{derivation.attr_path}",
                "--no-link",
                "--print-out-paths",
            ],
            check=False,
        )

        if result.returncode == 0:
            return BuildResult(
                derivation=derivation,
                success=True,
                output_path=result.stdout.strip(),
            )
        else:
            return BuildResult(
                derivation=derivation,
                success=False,
                error=result.stderr.strip() if result.stderr else "Build failed",
                build_log=result.stderr,
            )

    except Exception as e:
        return BuildResult(
            derivation=derivation,
            success=False,
            error=str(e),
        )


def build_changes(
    flake_path: Path,
    changes: ChangeSet,
    max_workers: int = 4,
) -> BuildResults:
    """Build all changed derivations in parallel.

    Args:
        flake_path: Path to the flake
        changes: ChangeSet containing derivations to build
        max_workers: Maximum number of parallel build workers
    """
    to_build: list[DerivationInfo] = []
    to_build.extend(changes.added)
    to_build.extend([new for old, new in changes.modified])

    if not to_build:
        return BuildResults(results=[])

    total = len(to_build)
    print(f"Building {total} package(s)...\n")

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_drv = {
            executor.submit(build_derivation, flake_path, drv): drv for drv in to_build
        }

        for future in as_completed(future_to_drv):
            drv = future_to_drv[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(
                    BuildResult(
                        derivation=drv,
                        success=False,
                        error=f"Unexpected error: {e}",
                    )
                )
            status = "\u2705" if results[-1].success else "\u274c"
            print(f"  [{len(results)}/{total}] {status} {drv.attr_path}")

    return BuildResults(results=results)
