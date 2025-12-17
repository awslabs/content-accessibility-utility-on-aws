#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
"""
Release management script for content-accessibility-utility-on-aws.

This script handles the full release workflow: bump version, generate changelog,
commit changes, and create a git tag. Push is done separately.

Usage:
    # Bump patch version and release
    uv run scripts/release.py patch

    # Bump minor version and release
    uv run scripts/release.py minor

    # Bump major version and release
    uv run scripts/release.py major

    # Release candidate (bumps patch and adds RC suffix)
    uv run scripts/release.py patch --rc 1

    # Specify exact version
    uv run scripts/release.py --version 1.2.3

    # Specify exact RC version
    uv run scripts/release.py --version 1.2.3-RC1

    # Dry run (show what would happen)
    uv run scripts/release.py patch --dry-run

After running, push the tag to trigger the workflow:
    git push origin v{version}
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "git-cliff>=2.0.0",
# ]
# ///

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
VERSION_FILE = PROJECT_ROOT / "content_accessibility_utility_on_aws" / "__init__.py"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
CLIFF_CONFIG = PROJECT_ROOT / "cliff.toml"

# Regex patterns
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-RC(\d+))?$")


def get_current_version() -> str:
    """Read the current version from __init__.py."""
    content = VERSION_FILE.read_text()
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find version in {VERSION_FILE}")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int, int | None]:
    """Parse version string into components (major, minor, patch, rc)."""
    # Strip RC suffix for base parsing
    base = version.split("-RC")[0]
    base_match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", base)
    if not base_match:
        raise ValueError(f"Invalid version format: {version}")

    major = int(base_match.group(1))
    minor = int(base_match.group(2))
    patch = int(base_match.group(3))

    rc = None
    if "-RC" in version:
        rc_match = re.search(r"-RC(\d+)$", version)
        if rc_match:
            rc = int(rc_match.group(1))

    return major, minor, patch, rc


def format_version(major: int, minor: int, patch: int, rc: int | None = None) -> str:
    """Format version components into a version string."""
    version = f"{major}.{minor}.{patch}"
    if rc is not None:
        version += f"-RC{rc}"
    return version


def bump_version(current: str, bump_type: str, rc: int | None = None) -> str:
    """Calculate the new version based on bump type."""
    major, minor, patch, _ = parse_version(current)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1

    return format_version(major, minor, patch, rc)


def update_version_file(new_version: str) -> None:
    """Update the version in __init__.py."""
    content = VERSION_FILE.read_text()
    new_content = VERSION_PATTERN.sub(f'__version__ = "{new_version}"', content)
    VERSION_FILE.write_text(new_content)
    print(f"  Updated {VERSION_FILE.name} to version {new_version}")


def generate_changelog() -> None:
    """Generate changelog using git-cliff."""
    result = subprocess.run(
        ["git-cliff", "--config", str(CLIFF_CONFIG), "-o", str(CHANGELOG_FILE)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git-cliff failed: {result.stderr}")
    print(f"  Updated {CHANGELOG_FILE.name}")


def git_commit(version: str) -> None:
    """Stage and commit changes."""
    # Stage the changed files
    subprocess.run(
        ["git", "add", str(VERSION_FILE), str(CHANGELOG_FILE)],
        check=True,
        cwd=PROJECT_ROOT,
    )

    # Commit
    commit_msg = f"chore(release): v{version}"
    subprocess.run(
        ["git", "commit", "-m", commit_msg],
        check=True,
        cwd=PROJECT_ROOT,
    )
    print(f"  Committed: {commit_msg}")


def create_tag(version: str) -> None:
    """Create an annotated git tag."""
    tag_name = f"v{version}"

    # Check if tag exists
    result = subprocess.run(
        ["git", "tag", "-l", tag_name],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if tag_name in result.stdout:
        raise RuntimeError(f"Tag {tag_name} already exists")

    # Create annotated tag
    subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
        check=True,
        cwd=PROJECT_ROOT,
    )
    print(f"  Created tag: {tag_name}")


def is_rc_version(version: str) -> bool:
    """Check if version is a release candidate."""
    return "-RC" in version


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Release tool - bumps version, updates changelog, commits, and tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run scripts/release.py patch           # Bump patch: 0.6.2 -> 0.6.3
  uv run scripts/release.py minor           # Bump minor: 0.6.2 -> 0.7.0
  uv run scripts/release.py major           # Bump major: 0.6.2 -> 1.0.0
  uv run scripts/release.py patch --rc 1    # RC release: 0.6.2 -> 0.6.3-RC1
  uv run scripts/release.py --version 1.0.0 # Set exact version

After running, push the tag:
  git push origin v{version}
""",
    )

    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Version bump type (required unless --version is specified)",
    )
    parser.add_argument(
        "--version", "-v",
        dest="exact_version",
        metavar="VERSION",
        help="Set exact version (e.g., 1.2.3 or 1.2.3-RC1)",
    )
    parser.add_argument(
        "--rc",
        type=int,
        metavar="N",
        help="Release candidate number (e.g., --rc 1 for RC1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.exact_version and not args.bump_type:
        parser.error("Either bump_type (major/minor/patch) or --version is required")

    if args.exact_version and args.bump_type:
        parser.error("Cannot specify both bump_type and --version")

    if args.exact_version and args.rc:
        parser.error("Cannot specify both --version and --rc (include RC in version string)")

    try:
        current = get_current_version()

        # Determine new version
        if args.exact_version:
            new_version = args.exact_version
            # Validate format
            parse_version(new_version)
        else:
            new_version = bump_version(current, args.bump_type, args.rc)

        is_rc = is_rc_version(new_version)

        print(f"\n{'=' * 50}")
        print(f"Release: {current} -> {new_version}")
        print(f"Type: {'Release Candidate' if is_rc else 'Production'}")
        print(f"{'=' * 50}\n")

        if args.dry_run:
            print("[DRY RUN] Would perform the following:")
            print(f"  1. Update version in {VERSION_FILE.name}")
            if not is_rc:
                print(f"  2. Generate changelog in {CHANGELOG_FILE.name}")
            else:
                print("  2. Skip changelog (RC release)")
            print(f"  3. Commit changes")
            print(f"  4. Create tag: v{new_version}")
            print(f"\nAfter running (without --dry-run):")
            print(f"  git push origin v{new_version}")
            return 0

        # Step 1: Update version
        print("Step 1: Updating version...")
        update_version_file(new_version)

        # Step 2: Generate changelog (skip for RC releases)
        if not is_rc:
            print("\nStep 2: Generating changelog...")
            generate_changelog()
        else:
            print("\nStep 2: Skipping changelog (RC release)")

        # Step 3: Commit
        print("\nStep 3: Committing changes...")
        git_commit(new_version)

        # Step 4: Create tag
        print("\nStep 4: Creating tag...")
        create_tag(new_version)

        # Done
        print(f"\n{'=' * 50}")
        print("Release prepared successfully!")
        print(f"\nTo publish, push the tag:")
        print(f"  git push origin v{new_version}")
        if is_rc:
            print(f"\nThis will publish to TestPyPI")
        else:
            print(f"\nThis will publish to PyPI and create a GitHub Release")
        print(f"{'=' * 50}\n")

        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
