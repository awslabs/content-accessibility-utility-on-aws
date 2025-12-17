#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0
"""
Release management script for content-accessibility-utility-on-aws.

Production releases: bump version, generate changelog, commit, and tag.
RC releases: just create a tag on the current commit (no file changes).

Usage:
    # Production release - bump patch version
    uv run scripts/release.py patch

    # Production release - bump minor version
    uv run scripts/release.py minor

    # Production release - bump major version
    uv run scripts/release.py major

    # Production release - exact version
    uv run scripts/release.py --version 1.2.3

    # RC release - just tag current commit (no file changes)
    uv run scripts/release.py --rc 1.0.0-RC1

    # Dry run (show what would happen)
    uv run scripts/release.py patch --dry-run

After running, push the tag to trigger the workflow:
    git push origin v{version}

Note: RC releases don't modify any files. The GitHub Action injects the
version into the package during build before publishing to TestPyPI.
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


def get_current_version() -> str:
    """Read the current version from __init__.py."""
    content = VERSION_FILE.read_text()
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find version in {VERSION_FILE}")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string into components (major, minor, patch)."""
    # Strip RC suffix for base parsing
    base = version.split("-RC")[0]
    base_match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", base)
    if not base_match:
        raise ValueError(f"Invalid version format: {version}")

    return int(base_match.group(1)), int(base_match.group(2)), int(base_match.group(3))


def validate_rc_version(version: str) -> None:
    """Validate RC version format."""
    if not re.match(r"^\d+\.\d+\.\d+-RC\d+$", version):
        raise ValueError(f"Invalid RC version format: {version}. Expected: X.Y.Z-RCN")


def validate_prod_version(version: str) -> None:
    """Validate production version format."""
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(f"Invalid version format: {version}. Expected: X.Y.Z")


def bump_version(current: str, bump_type: str) -> str:
    """Calculate the new version based on bump type."""
    major, minor, patch = parse_version(current)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1

    return f"{major}.{minor}.{patch}"


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


def do_rc_release(version: str, dry_run: bool) -> int:
    """Handle RC release - just tag, no file changes."""
    validate_rc_version(version)

    print(f"\n{'=' * 50}")
    print(f"RC Release: v{version}")
    print("(No file changes - just tagging current commit)")
    print(f"{'=' * 50}\n")

    if dry_run:
        print("[DRY RUN] Would perform the following:")
        print(f"  1. Create tag: v{version}")
        print(f"\nAfter running (without --dry-run):")
        print(f"  git push origin v{version}")
        return 0

    # Just create the tag
    print("Creating tag...")
    create_tag(version)

    print(f"\n{'=' * 50}")
    print("RC release prepared successfully!")
    print(f"\nTo publish to TestPyPI, push the tag:")
    print(f"  git push origin v{version}")
    print(f"\nThe GitHub Action will inject the version during build.")
    print(f"{'=' * 50}\n")

    return 0


def do_prod_release(version: str, dry_run: bool) -> int:
    """Handle production release - bump, changelog, commit, tag."""
    validate_prod_version(version)
    current = get_current_version()

    print(f"\n{'=' * 50}")
    print(f"Production Release: {current} -> {version}")
    print(f"{'=' * 50}\n")

    if dry_run:
        print("[DRY RUN] Would perform the following:")
        print(f"  1. Update version in {VERSION_FILE.name}")
        print(f"  2. Generate changelog in {CHANGELOG_FILE.name}")
        print(f"  3. Commit changes")
        print(f"  4. Create tag: v{version}")
        print(f"\nAfter running (without --dry-run):")
        print(f"  git push origin v{version}")
        return 0

    # Step 1: Update version
    print("Step 1: Updating version...")
    update_version_file(version)

    # Step 2: Generate changelog
    print("\nStep 2: Generating changelog...")
    generate_changelog()

    # Step 3: Commit
    print("\nStep 3: Committing changes...")
    git_commit(version)

    # Step 4: Create tag
    print("\nStep 4: Creating tag...")
    create_tag(version)

    print(f"\n{'=' * 50}")
    print("Production release prepared successfully!")
    print(f"\nTo publish to PyPI and create GitHub Release, push the tag:")
    print(f"  git push origin v{version}")
    print(f"{'=' * 50}\n")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Release tool for content-accessibility-utility-on-aws",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Production releases (modifies files, commits, tags)
  uv run scripts/release.py patch           # 0.6.2 -> 0.6.3
  uv run scripts/release.py minor           # 0.6.2 -> 0.7.0
  uv run scripts/release.py major           # 0.6.2 -> 1.0.0
  uv run scripts/release.py --version 1.0.0 # Exact version

  # RC releases (just tags current commit, no file changes)
  uv run scripts/release.py --rc 0.7.0-RC1

After running, push the tag:
  git push origin v{version}
""",
    )

    # Production release options
    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Version bump type for production release",
    )
    parser.add_argument(
        "--version", "-v",
        dest="exact_version",
        metavar="VERSION",
        help="Exact version for production release (e.g., 1.2.3)",
    )

    # RC release option
    parser.add_argument(
        "--rc",
        metavar="VERSION",
        help="Create RC release tag (e.g., --rc 1.0.0-RC1). No file changes.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.rc:
        # RC release - can't combine with other version options
        if args.bump_type or args.exact_version:
            parser.error("--rc cannot be combined with bump_type or --version")
    else:
        # Production release - need either bump_type or --version
        if not args.exact_version and not args.bump_type:
            parser.error("Specify bump_type (major/minor/patch), --version, or --rc")
        if args.exact_version and args.bump_type:
            parser.error("Cannot specify both bump_type and --version")

    try:
        if args.rc:
            return do_rc_release(args.rc, args.dry_run)
        else:
            if args.exact_version:
                version = args.exact_version
            else:
                current = get_current_version()
                version = bump_version(current, args.bump_type)
            return do_prod_release(version, args.dry_run)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
