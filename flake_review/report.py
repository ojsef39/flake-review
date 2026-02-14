"""Generate reports for build results."""

import json
import os
import subprocess
import sys
from typing import Any

from .build import BuildResult, BuildResults
from .flake import ChangeSet, DerivationInfo


def _get_nix_diff(old_drv: str, new_drv: str, color: bool = False) -> str | None:
    """Run nix-diff between two derivations."""
    try:
        cmd = ["nix-diff", old_drv, new_drv]
        if color:
            cmd.extend(["--color", "always"])
        # NIX_REMOTE="" forces local store access, avoiding daemon
        # protocol issues where nix-diff can't read .drv files
        env = {**os.environ, "NIX_REMOTE": ""}
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if result.stdout.strip():
            return result.stdout.strip()
        if result.stderr.strip():
            print(
                f"nix-diff failed: {result.stderr.strip()[:200]}",
                file=sys.stderr,
            )
        return None
    except FileNotFoundError:
        print("nix-diff not found on PATH", file=sys.stderr)
        return None
    except Exception as e:
        print(f"nix-diff error: {e}", file=sys.stderr)
        return None


def _format_diff_section(diff: str | None, markdown: bool) -> list[str]:
    """Format nix-diff output."""
    if not diff:
        return []
    lines: list[str] = []
    if markdown:
        lines.append("  <details>")
        lines.append("  <summary>Derivation diff</summary>\n")
        lines.append("  ```diff")
        for diff_line in diff.split("\n"):
            lines.append(f"  {diff_line}")
        lines.append("  ```\n")
        lines.append("  </details>")
    else:
        for diff_line in diff.split("\n"):
            lines.append(f"    {diff_line}")
    return lines


def _format_build_error(error: str, markdown: bool) -> list[str]:
    """Format a build error for display.

    For markdown, uses a collapsible <details> block with the full error.
    For console, shows the last 20 lines.
    """
    lines: list[str] = []
    error_lines = [line for line in error.strip().split("\n") if line.strip()]
    if not error_lines:
        return lines

    if markdown:
        lines.append("  <details>")
        lines.append("  <summary>Build error</summary>\n")
        lines.append("  ```")
        for err_line in error_lines:
            lines.append(f"  {err_line}")
        lines.append("  ```\n")
        lines.append("  </details>")
    else:
        tail = error_lines[-20:]
        for err_line in tail:
            lines.append(f"    {err_line}")

    return lines


def format_detailed_changes(
    changes: ChangeSet,
    results: BuildResults,
    markdown: bool = False,
) -> str:
    """Format detailed changes with build results."""
    lines: list[str] = []

    result_map = {r.derivation.attr_path: r for r in results.results}

    if changes.added:
        lines.append(f"### ➕ Added ({len(changes.added)})\n")
        for drv in changes.added:
            result = result_map.get(drv.attr_path)
            if result and result.success:
                lines.append(f"- ✅ `{drv.attr_path}`")
                if result.output_path:
                    lines.append(f"  - Output: `{result.output_path}`")
            elif result:
                lines.append(f"- ❌ `{drv.attr_path}` (build failed)")
                if result.error:
                    lines.extend(_format_build_error(result.error, markdown))
            else:
                lines.append(f"- `{drv.attr_path}`")
        lines.append("")

    if changes.modified:
        lines.append(f"### 🔄 Modified ({len(changes.modified)})\n")
        for old, new in changes.modified:
            result = result_map.get(new.attr_path)
            if result and result.success:
                lines.append(f"- ✅ `{new.attr_path}`")
                if result.output_path:
                    lines.append(f"  - Output: `{result.output_path}`")
            elif result:
                lines.append(f"- ❌ `{new.attr_path}` (build failed)")
                if result.error:
                    lines.extend(_format_build_error(result.error, markdown))
            else:
                lines.append(f"- `{new.attr_path}`")

            diff = _get_nix_diff(old.drv_path, new.drv_path, color=not markdown)
            lines.extend(_format_diff_section(diff, markdown))
        lines.append("")

    if changes.removed:
        lines.append(f"### ➖ Removed ({len(changes.removed)})\n")
        for drv in changes.removed:
            lines.append(f"- `{drv.attr_path}`")
        lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    changes: ChangeSet,
    results: BuildResults,
    title: str = "Flake Review Results",
    requested_systems: list[str] | None = None,
    available_systems: set[str] | None = None,
) -> str:
    """Generate a complete markdown report.

    Args:
        changes: ChangeSet to report on
        results: Build results
        title: Report title
        requested_systems: Systems that were requested for building
        available_systems: All systems available in the flake
    """
    lines = [f"# {title}\n"]

    if available_systems:
        lines.append(f"**Available systems:** {', '.join(sorted(available_systems))}")
    if requested_systems:
        lines.append(f"**Requested systems:** {', '.join(sorted(requested_systems))}")
    if requested_systems or available_systems:
        lines.append("")

    if changes.added or changes.modified or changes.removed:
        lines.append(format_detailed_changes(changes, results, markdown=True))

    lines.append(
        "---\n*Generated by [flake-review](https://github.com/ojsef39/flake-review)*"
    )

    return "\n".join(lines)


def merge_markdown_reports(
    report_files: list[str],
    title: str = "Flake Review Results",
) -> str:
    """Merge multiple markdown report files into one.

    Strips individual titles and footers, combines under a single header.

    Args:
        report_files: Paths to markdown report files
        title: Title for the merged report
    """
    sections: list[str] = []

    for path in report_files:
        content = open(path).read().strip()  # noqa: SIM115
        lines = content.split("\n")

        # Strip title line, empty lines at start, and footer
        filtered: list[str] = []
        for line in lines:
            if line.startswith("# "):
                continue
            if "Generated by [flake-review]" in line:
                continue
            if line.strip() == "---" and not filtered:
                continue
            filtered.append(line)

        # Trim leading/trailing blank lines and stray ---
        while filtered and (not filtered[0].strip() or filtered[0].strip() == "---"):
            filtered.pop(0)
        while filtered and (not filtered[-1].strip() or filtered[-1].strip() == "---"):
            filtered.pop()

        if filtered:
            sections.append("\n".join(filtered))

    merged = f"# {title}\n\n"
    merged += "\n\n---\n\n".join(sections)
    merged += "\n\n---\n*Generated by [flake-review](https://github.com/ojsef39/flake-review)*"

    return merged


def _drv_to_dict(drv: DerivationInfo) -> dict[str, str]:
    """Serialize a DerivationInfo to a dict."""
    return {
        "attr_path": drv.attr_path,
        "drv_path": drv.drv_path,
        "output_type": drv.output_type,
        "system": drv.system,
        "name": drv.name,
    }


def _build_to_dict(
    result: BuildResult | None,
) -> dict[str, Any] | None:
    """Serialize a BuildResult to a dict."""
    if result is None:
        return None
    return {
        "success": result.success,
        "output_path": result.output_path,
        "error": result.error,
    }


def generate_json_report(
    changes: ChangeSet,
    results: BuildResults,
    requested_systems: list[str] | None = None,
    available_systems: set[str] | None = None,
) -> dict[str, Any]:
    """Generate a structured JSON report.

    Captures nix-diff output eagerly so the merge step doesn't need
    access to the derivations.
    """
    result_map = {r.derivation.attr_path: r for r in results.results}

    added = []
    for drv in changes.added:
        entry: dict[str, Any] = _drv_to_dict(drv)
        entry["build"] = _build_to_dict(result_map.get(drv.attr_path))
        added.append(entry)

    removed = [_drv_to_dict(drv) for drv in changes.removed]

    modified = []
    for old, new in changes.modified:
        diff = _get_nix_diff(old.drv_path, new.drv_path)
        entry = {
            "old": _drv_to_dict(old),
            "new": _drv_to_dict(new),
            "nix_diff": diff,
            "build": _build_to_dict(result_map.get(new.attr_path)),
        }
        modified.append(entry)

    return {
        "version": 1,
        "metadata": {
            "requested_systems": requested_systems or [],
            "available_systems": sorted(available_systems) if available_systems else [],
        },
        "changes": {
            "added": added,
            "removed": removed,
            "modified": modified,
        },
    }


def load_json_report(path: str) -> dict[str, Any]:
    """Read and validate a JSON report file."""
    with open(path) as f:  # noqa: SIM115
        data: dict[str, Any] = json.load(f)
    if "version" not in data or "changes" not in data:
        msg = f"Invalid JSON report: {path}"
        raise ValueError(msg)
    return data


def _render_markdown_from_json(
    data: dict[str, Any],
    title: str = "Flake Review Results",
) -> str:
    """Render a markdown report from JSON report data."""
    lines = [f"# {title}\n"]

    meta = data.get("metadata", {})
    available = meta.get("available_systems", [])
    requested = meta.get("requested_systems", [])

    if available:
        lines.append(f"**Available systems:** {', '.join(sorted(available))}")
    if requested:
        lines.append(f"**Requested systems:** {', '.join(sorted(requested))}")
    if available or requested:
        lines.append("")

    changes = data.get("changes", {})
    added = changes.get("added", [])
    removed = changes.get("removed", [])
    modified = changes.get("modified", [])

    if added:
        lines.append(f"### ➕ Added ({len(added)})\n")
        for entry in added:
            build = entry.get("build")
            if build and build.get("success"):
                lines.append(f"- ✅ `{entry['attr_path']}`")
                if build.get("output_path"):
                    lines.append(f"  - Output: `{build['output_path']}`")
            elif build:
                lines.append(f"- ❌ `{entry['attr_path']}` (build failed)")
                if build.get("error"):
                    lines.extend(_format_build_error(build["error"], markdown=True))
            else:
                lines.append(f"- `{entry['attr_path']}`")
        lines.append("")

    if modified:
        lines.append(f"### 🔄 Modified ({len(modified)})\n")
        for entry in modified:
            build = entry.get("build")
            attr_path = entry["new"]["attr_path"]
            if build and build.get("success"):
                lines.append(f"- ✅ `{attr_path}`")
                if build.get("output_path"):
                    lines.append(f"  - Output: `{build['output_path']}`")
            elif build:
                lines.append(f"- ❌ `{attr_path}` (build failed)")
                if build.get("error"):
                    lines.extend(_format_build_error(build["error"], markdown=True))
            else:
                lines.append(f"- `{attr_path}`")

            lines.extend(_format_diff_section(entry.get("nix_diff"), markdown=True))
        lines.append("")

    if removed:
        lines.append(f"### ➖ Removed ({len(removed)})\n")
        for entry in removed:
            lines.append(f"- `{entry['attr_path']}`")
        lines.append("")

    lines.append(
        "---\n*Generated by" " [flake-review](https://github.com/ojsef39/flake-review)*"
    )

    return "\n".join(lines)


def merge_json_reports(
    report_files: list[str],
    title: str = "Flake Review Results",
) -> str:
    """Merge multiple JSON report files into a single markdown report.

    Combines structured data from all files, then renders once.
    """
    all_available: set[str] = set()
    all_requested: set[str] = set()
    all_added: list[dict[str, Any]] = []
    all_removed: list[dict[str, Any]] = []
    all_modified: list[dict[str, Any]] = []

    for path in report_files:
        data = load_json_report(path)
        meta = data.get("metadata", {})
        all_available.update(meta.get("available_systems", []))
        all_requested.update(meta.get("requested_systems", []))

        changes = data.get("changes", {})
        all_added.extend(changes.get("added", []))
        all_removed.extend(changes.get("removed", []))
        all_modified.extend(changes.get("modified", []))

    combined: dict[str, Any] = {
        "version": 1,
        "metadata": {
            "requested_systems": sorted(all_requested),
            "available_systems": sorted(all_available),
        },
        "changes": {
            "added": all_added,
            "removed": all_removed,
            "modified": all_modified,
        },
    }

    return _render_markdown_from_json(combined, title=title)


def print_console_report(changes: ChangeSet, results: BuildResults) -> None:
    """Print a report to the console."""
    print("\n" + "=" * 60)
    print("FLAKE REVIEW RESULTS")
    print("=" * 60 + "\n")

    if changes.added or changes.modified or changes.removed:
        print(format_detailed_changes(changes, results, markdown=False))

    print("=" * 60 + "\n")
