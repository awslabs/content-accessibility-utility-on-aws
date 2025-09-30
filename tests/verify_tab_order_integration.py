#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Simple verification script for tab order optimization integration.

This script verifies that the tab order optimization feature is properly integrated
without requiring full test infrastructure.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        from content_accessibility_utility_on_aws.remediate.remediation_strategies.tab_order_remediation import (
            TabOrderRemediation,
        )

        print("✓ TabOrderRemediation imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import TabOrderRemediation: {e}")
        return False

    try:
        from content_accessibility_utility_on_aws.remediate.remediation_strategies.tab_order_ai_validator import (
            AITabOrderValidator,
        )

        print("✓ AITabOrderValidator imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import AITabOrderValidator: {e}")
        return False

    try:
        from content_accessibility_utility_on_aws.audit.checks.tab_order_checks import (
            TabOrderCheck,
        )

        print("✓ TabOrderCheck imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import TabOrderCheck: {e}")
        return False

    return True


def test_configuration():
    """Test that configuration defaults are set."""
    print("\nTesting configuration...")

    try:
        import yaml

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "content_accessibility_utility_on_aws",
            "utils",
            "config_defaults.yaml",
        )

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        remediate_config = config.get("remediate", {})

        # Check required configuration options
        if "optimize_tab_order" in remediate_config:
            print(
                f"✓ optimize_tab_order configured: {remediate_config['optimize_tab_order']}"
            )
        else:
            print("✗ optimize_tab_order not found in config")
            return False

        if "ai_validate_tab_order" in remediate_config:
            print(
                f"✓ ai_validate_tab_order configured: {remediate_config['ai_validate_tab_order']}"
            )
        else:
            print("✗ ai_validate_tab_order not found in config")
            return False

        if "ai_confidence_threshold" in remediate_config:
            print(
                f"✓ ai_confidence_threshold configured: {remediate_config['ai_confidence_threshold']}"
            )
        else:
            print("✗ ai_confidence_threshold not found in config")
            return False

        if "tab_order_row_threshold" in remediate_config:
            print(
                f"✓ tab_order_row_threshold configured: {remediate_config['tab_order_row_threshold']}"
            )
        else:
            print("✗ tab_order_row_threshold not found in config")
            return False

        return True

    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False


def test_algorithmic_remediation():
    """Test basic algorithmic remediation."""
    print("\nTesting algorithmic remediation...")

    try:
        from content_accessibility_utility_on_aws.remediate.remediation_strategies.tab_order_remediation import (
            TabOrderRemediation,
        )

        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <button tabindex="5">Button 1</button>
            <button tabindex="3">Button 2</button>
            <span tabindex="0">Non-interactive</span>
        </body>
        </html>
        """

        issues = [
            {
                "type": "positive-tabindex",
                "selector": "button[tabindex='5']",
                "element": '<button tabindex="5">Button 1</button>',
            },
            {
                "type": "positive-tabindex",
                "selector": "button[tabindex='3']",
                "element": '<button tabindex="3">Button 2</button>',
            },
            {
                "type": "unnecessary-tabindex-zero",
                "selector": "span[tabindex='0']",
                "element": '<span tabindex="0">Non-interactive</span>',
            },
        ]

        options = {"optimize_tab_order": True, "ai_validate_tab_order": False}

        remediator = TabOrderRemediation(html, issues, options)
        remediated_html, changes = remediator.remediate()

        print(f"✓ Algorithmic remediation completed")
        print(f"  - Applied {len(changes)} changes")

        # Verify positive tabindex values were removed
        soup = BeautifulSoup(remediated_html, "html.parser")
        buttons_with_positive_tabindex = soup.find_all(
            "button", attrs={"tabindex": lambda x: x and int(x) > 0}
        )

        if len(buttons_with_positive_tabindex) == 0:
            print("✓ All positive tabindex values removed")
        else:
            print(
                f"✗ Still found {len(buttons_with_positive_tabindex)} elements with positive tabindex"
            )
            return False

        return True

    except Exception as e:
        print(f"✗ Algorithmic remediation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_issue_detection():
    """Test that tab order checks can detect issues."""
    print("\nTesting issue detection...")

    try:
        from content_accessibility_utility_on_aws.audit.checks.tab_order_checks import (
            TabOrderCheck,
        )

        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <button tabindex="5">Button 1</button>
            <span tabindex="0">Non-interactive</span>
        </body>
        </html>
        """

        soup = BeautifulSoup(html, "html.parser")
        checker = TabOrderCheck()
        issues = checker.check(soup)

        print(f"✓ Issue detection completed")
        print(f"  - Found {len(issues)} issues")

        # Should find at least the positive tabindex issue
        positive_tabindex_issues = [
            i for i in issues if i["type"] == "positive-tabindex"
        ]
        unnecessary_tabindex_issues = [
            i for i in issues if i["type"] == "unnecessary-tabindex-zero"
        ]

        if len(positive_tabindex_issues) > 0:
            print(
                f"✓ Detected {len(positive_tabindex_issues)} positive-tabindex issues"
            )
        else:
            print("✗ Failed to detect positive-tabindex issues")
            return False

        if len(unnecessary_tabindex_issues) > 0:
            print(
                f"✓ Detected {len(unnecessary_tabindex_issues)} unnecessary-tabindex-zero issues"
            )
        else:
            print("✗ Failed to detect unnecessary-tabindex-zero issues")
            return False

        return True

    except Exception as e:
        print(f"✗ Issue detection failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Tab Order Optimization Integration Verification")
    print("=" * 60)

    results = []

    # Test imports
    results.append(("Imports", test_imports()))

    # Test configuration
    results.append(("Configuration", test_configuration()))

    # Test issue detection
    results.append(("Issue Detection", test_issue_detection()))

    # Test algorithmic remediation
    results.append(("Algorithmic Remediation", test_algorithmic_remediation()))

    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:.<50} {status}")

    print("=" * 60)

    # Return exit code
    all_passed = all(passed for _, passed in results)
    if all_passed:
        print("\n✓ All verifications PASSED")
        return 0
    else:
        print("\n✗ Some verifications FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
