"""Push build outputs to a Cachix binary cache."""

import shutil
import sys

from .build import BuildResults
from .utils import run_command


def collect_store_paths(results: BuildResults) -> list[str]:
    """Collect store paths from successful builds.

    A build's output_path may contain multiple newline-separated paths
    (multi-output derivations via --print-out-paths).
    """
    paths: list[str] = []
    for result in results.successful:
        if not result.output_path:
            continue
        paths.extend(
            line.strip() for line in result.output_path.splitlines() if line.strip()
        )
    return paths


def push_to_cachix(cache: str, results: BuildResults) -> bool:
    """Push successful build outputs to a Cachix cache.

    Requires the `cachix` executable in PATH and authentication via
    CACHIX_AUTH_TOKEN (or an existing cachix config).

    Returns True if the push succeeded (or there was nothing to push).
    """
    paths = collect_store_paths(results)
    if not paths:
        print("No store paths to push to cachix.")
        return True

    if shutil.which("cachix") is None:
        print(
            "Error: cachix executable not found in PATH "
            "(install it, e.g. `nix profile add nixpkgs#cachix`)",
            file=sys.stderr,
        )
        return False

    print(f"\nPushing {len(paths)} store path(s) to cachix cache '{cache}'...")

    result = run_command(["cachix", "push", cache, *paths], check=False)

    if result.returncode != 0:
        error = result.stderr.strip() if result.stderr else "cachix push failed"
        print(f"Error pushing to cachix: {error}", file=sys.stderr)
        return False

    print(f"✅ Pushed {len(paths)} path(s) to '{cache}'")
    return True
