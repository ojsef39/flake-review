"""Command-line interface for flake-review."""

import argparse
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .build import build_changes
from .flake import FlakeOutputs, compare_outputs
from .github import GithubClient, parse_pr_url
from .report import (generate_json_report, generate_markdown_report,
                     load_json_report, merge_json_reports,
                     merge_markdown_reports, print_console_report)
from .utils import GitWorktree, get_current_system, get_git_root, run_command


def _get_systems(args: argparse.Namespace) -> list[str]:
    return args.systems.split(",") if args.systems else [get_current_system()]


def _review_changes(
    base_outputs: FlakeOutputs,
    head_outputs: FlakeOutputs,
    head_path: Path,
    systems: list[str],
    args: argparse.Namespace,
    *,
    available_systems: set[str] | None = None,
    title: str = "Flake Review Results",
    post_callback: Callable[[str], None] | None = None,
) -> int:
    """Run compare → build → report for a pair of FlakeOutputs.

    Returns 0 on success, 1 if any build failed or posting failed.
    """
    changes = compare_outputs(
        base_outputs,
        head_outputs,
        output_types=["packages"],
        systems=systems,
        package_filter=args.package,
    )

    total_changes = len(changes.added) + len(changes.modified) + len(changes.removed)

    if total_changes > 0:
        found_systems = set()
        for drv in changes.added + [n for _, n in changes.modified]:
            found_systems.add(drv.system)
        print(f"Changed systems: {', '.join(sorted(found_systems))}")

    output_file = getattr(args, "output_file", None)
    output_format = getattr(args, "output_format", "md")
    show_result = getattr(args, "show_result", False)
    post_result = getattr(args, "post_result", False)

    if total_changes == 0:
        print("No changes detected.")
        return 0

    if args.build:
        results = build_changes(head_path, changes, max_workers=args.max_workers)
    else:
        from .build import BuildResults

        results = BuildResults(results=[])

    print_console_report(changes, results)

    if output_file and output_format == "json":
        import json

        json_data = generate_json_report(
            changes,
            results,
            requested_systems=systems,
            available_systems=available_systems,
        )
        Path(output_file).write_text(json.dumps(json_data, indent=2))
        print(f"Report written to {output_file}")

    markdown = None
    if post_result or show_result or (output_file and output_format != "json"):
        markdown = generate_markdown_report(
            changes,
            results,
            title=title,
            requested_systems=systems,
            available_systems=available_systems,
        )

    if markdown and output_file and output_format != "json":
        Path(output_file).write_text(markdown)
        print(f"Report written to {output_file}")

    if markdown and show_result:
        print("\n--- Markdown Report ---")
        print(markdown)
        print("--- End Report ---")

    if markdown and post_result and post_callback is not None:
        print("Posting results to GitHub...")
        try:
            post_callback(markdown)
        except Exception as e:
            print(f"Error posting to GitHub: {e}", file=sys.stderr)
            return 1

    return 1 if results.failure_count > 0 else 0


def cmd_pr(args: argparse.Namespace) -> int:
    """Review a GitHub pull request."""
    try:
        owner, repo, pr_number = parse_pr_url(args.pr_url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Reviewing PR: {owner}/{repo}#{pr_number}")

    try:
        client = GithubClient()
        pr = client.get_pull_request(owner, repo, pr_number)
        print(f"Base: {pr.base_ref}, Head: {pr.head_ref}")
    except Exception as e:
        print(f"Error fetching PR: {e}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        repo_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    else:
        repo_url = f"https://github.com/{owner}/{repo}.git"
    temp_dir = Path(tempfile.mkdtemp(prefix=f"flake-review-{repo}-"))

    try:
        print(f"\nCloning https://github.com/{owner}/{repo}.git...")
        run_command(["git", "clone", "--quiet", repo_url, str(temp_dir)])
        repo_path = temp_dir

        base_sha = pr.base_sha
        head_sha = pr.head_sha

        if pr.is_fork:
            assert pr.head_repo_url is not None  # Guaranteed by is_fork
            print("Fetching from fork...")
            run_command(
                ["git", "fetch", pr.head_repo_url, head_sha],
                cwd=repo_path,
            )
        else:
            print("Fetching commits...")
            run_command(
                ["git", "fetch", "origin", head_sha],
                cwd=repo_path,
            )

        requested_systems = _get_systems(args)
        print(f"Requested systems: {', '.join(requested_systems)}")

        base_short = f"{pr.base_ref} ({base_sha[:8]})"
        head_short = f"{pr.head_ref} ({head_sha[:8]})"
        print(f"\nComparing {base_short} vs {head_short}...")

        with GitWorktree(repo_path, base_sha) as base_path:
            with GitWorktree(repo_path, head_sha) as head_path:
                base_outputs = FlakeOutputs(base_path)
                head_outputs = FlakeOutputs(head_path)

                print("\nChecking flake inputs...")
                try:
                    base_lock = (base_path / "flake.lock").read_text()
                    head_lock = (head_path / "flake.lock").read_text()
                    if base_lock != head_lock:
                        print("⚠️  flake.lock changed")
                    else:
                        print("✅ flake.lock unchanged")
                except Exception:
                    pass

                base_raw = base_outputs._get_raw_outputs()
                head_raw = head_outputs._get_raw_outputs()

                available_systems: set[str] = set()
                if "packages" in base_raw:
                    available_systems.update(base_raw["packages"].keys())
                if "packages" in head_raw:
                    available_systems.update(head_raw["packages"].keys())

                unavailable = set(requested_systems) - available_systems
                if unavailable:
                    print(f"⚠️  Systems not in flake: {', '.join(sorted(unavailable))}")
                if available_systems:
                    print(f"Available systems: {', '.join(sorted(available_systems))}")

                title = f"Flake Review Results for [#{pr_number}]({pr.url})"

                return _review_changes(
                    base_outputs,
                    head_outputs,
                    head_path,
                    requested_systems,
                    args,
                    available_systems=available_systems,
                    title=title,
                    post_callback=lambda md: client.post_comment(pr, md),
                )

    finally:
        if temp_dir.exists():
            print(f"\nCleaning up {temp_dir}...")
            shutil.rmtree(temp_dir)


def cmd_local(args: argparse.Namespace) -> int:
    """Review local changes against a base ref."""
    repo_path = get_git_root()
    systems = _get_systems(args)
    print(f"Building for systems: {', '.join(systems)}")

    if args.base_ref:
        base_ref = args.base_ref
        print(f"Comparing working tree against {base_ref}...")
    else:
        try:
            result = run_command(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                base_ref = result.stdout.strip()
                print(f"Comparing working tree against upstream: {base_ref}...")
            else:
                base_ref = "HEAD~1"
                print(
                    "No upstream branch found, comparing working tree against HEAD~1..."
                )
        except Exception:
            base_ref = "HEAD~1"
            print("No upstream branch found, comparing working tree against HEAD~1...")

    # Base is a clean worktree; head is the working directory so uncommitted
    # changes are included (Nix evaluates the dirty tree).
    with GitWorktree(repo_path, base_ref) as base_path:
        return _review_changes(
            FlakeOutputs(base_path),
            FlakeOutputs(repo_path),
            repo_path,
            systems,
            args,
        )


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two git refs."""
    repo_path = get_git_root()
    systems = _get_systems(args)
    print(f"Building for systems: {', '.join(systems)}")
    print(f"Comparing {args.base_ref} vs {args.target_ref}...")

    with GitWorktree(repo_path, args.base_ref) as base_path:
        with GitWorktree(repo_path, args.target_ref) as target_path:
            return _review_changes(
                FlakeOutputs(base_path),
                FlakeOutputs(target_path),
                target_path,
                systems,
                args,
            )


def cmd_merge_reports(args: argparse.Namespace) -> int:
    """Merge multiple report files into one."""
    is_json = False
    try:
        load_json_report(args.report_files[0])
        is_json = True
    except (ValueError, Exception):
        pass

    if is_json:
        merged = merge_json_reports(args.report_files, title=args.title)
    else:
        merged = merge_markdown_reports(args.report_files, title=args.title)

    if args.output_file:
        Path(args.output_file).write_text(merged)
        print(f"Merged report written to {args.output_file}")
    else:
        print(merged)

    if args.post_result:
        owner, repo, pr_number = parse_pr_url(args.pr_url)
        client = GithubClient()
        pr = client.get_pull_request(owner, repo, pr_number)
        client.post_comment(pr, merged)
        print(f"✅ Posted results to {pr.url}")

    return 0


def _add_common_args(p: argparse.ArgumentParser, *, has_build: bool = True) -> None:
    """Add flags shared by pr / local / compare."""
    p.add_argument(
        "-p",
        "--package",
        action="append",
        help="Only review specific packages (can be repeated)",
    )
    p.add_argument(
        "--systems",
        help="Comma-separated list of systems to build for (default: current system)",
    )
    if has_build:
        p.add_argument(
            "--build/--no-build",
            dest="build",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Whether to build packages (default: --build)",
        )
        p.add_argument(
            "--max-workers",
            type=int,
            default=4,
            help="Maximum number of parallel build workers (default: 4)",
        )


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Review tool for Nix flake pull requests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"flake-review {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # PR command
    pr_parser = subparsers.add_parser("pr", help="Review a GitHub pull request")
    pr_parser.add_argument(
        "pr_url",
        help="GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)",
    )
    _add_common_args(pr_parser)
    pr_parser.add_argument(
        "--post-result",
        action="store_true",
        help="Post results as GitHub PR comment",
    )
    pr_parser.add_argument(
        "--show-result",
        action="store_true",
        help="Print the markdown report to console (preview before posting)",
    )
    pr_parser.add_argument(
        "--output-file",
        help="Write report to a file (for CI pipelines)",
    )
    pr_parser.add_argument(
        "--output-format",
        choices=["md", "json"],
        default="md",
        help="Output file format (default: md)",
    )

    # Local command
    local_parser = subparsers.add_parser(
        "local", help="Review local changes against a base ref"
    )
    local_parser.add_argument(
        "base_ref",
        nargs="?",
        help="Base git ref (default: upstream tracking branch, or HEAD~1)",
    )
    _add_common_args(local_parser)

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two git refs")
    compare_parser.add_argument("base_ref", help="Base git ref (e.g., main, HEAD~1)")
    compare_parser.add_argument(
        "target_ref", help="Target git ref (e.g., feature-branch, HEAD)"
    )
    _add_common_args(compare_parser)

    # Merge reports command
    merge_parser = subparsers.add_parser(
        "merge-reports",
        help="Merge multiple report files into one (for CI pipelines)",
    )
    merge_parser.add_argument(
        "report_files",
        nargs="+",
        help="Report files to merge (JSON or markdown)",
    )
    merge_parser.add_argument(
        "--title",
        default="Flake Review Results",
        help="Title for the merged report",
    )
    merge_parser.add_argument(
        "--output-file",
        help="Write merged report to file (default: stdout)",
    )
    merge_parser.add_argument(
        "--post-result",
        action="store_true",
        help="Post merged results as GitHub PR comment",
    )
    merge_parser.add_argument(
        "--pr-url",
        help="GitHub PR URL (required with --post-result)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "pr":
            sys.exit(cmd_pr(args))
        elif args.command == "local":
            sys.exit(cmd_local(args))
        elif args.command == "compare":
            sys.exit(cmd_compare(args))
        elif args.command == "merge-reports":
            sys.exit(cmd_merge_reports(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
