#!/usr/bin/env python3
# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Integration test for tab order optimization.

This test verifies that the tab order optimization feature is properly integrated
into the main remediation pipeline.
"""

import unittest
from bs4 import BeautifulSoup
from content_accessibility_utility_on_aws.remediate.remediation_manager import (
    RemediationManager,
)


class TestTabOrderIntegration(unittest.TestCase):
    """Test tab order optimization integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Test Document</title>
        </head>
        <body>
            <div data-bda-bbox="10,10,200,50">
                <button tabindex="5">Button 1</button>
            </div>
            <div data-bda-bbox="10,60,200,100">
                <button tabindex="3">Button 2</button>
            </div>
            <div data-bda-bbox="10,110,200,150">
                <span tabindex="0">Non-interactive element</span>
            </div>
        </body>
        </html>
        """

    def test_tab_order_issues_detected_and_grouped(self):
        """Test that tab order issues are properly detected and grouped for batch processing."""
        # Create sample issues
        issues = [
            {
                "id": "issue-1",
                "type": "positive-tabindex",
                "severity": "critical",
                "selector": "button[tabindex='5']",
                "context": "Button with tabindex=5",
            },
            {
                "id": "issue-2",
                "type": "positive-tabindex",
                "severity": "critical",
                "selector": "button[tabindex='3']",
                "context": "Button with tabindex=3",
            },
            {
                "id": "issue-3",
                "type": "unnecessary-tabindex-zero",
                "severity": "minor",
                "selector": "span[tabindex='0']",
                "context": "Non-interactive element with tabindex=0",
            },
            {
                "id": "issue-4",
                "type": "missing-alt-text",
                "severity": "major",
                "selector": "img",
                "context": "Image without alt text",
            },
        ]

        soup = BeautifulSoup(self.sample_html, "html.parser")
        options = {
            "optimize_tab_order": True,
            "ai_validate_tab_order": False,  # Disable AI for unit test
            "disable_ai": True,  # Disable Bedrock client
        }

        manager = RemediationManager(soup, options)
        result = manager.remediate_issues(issues)

        # Verify tab order issues were processed
        self.assertGreater(result["issues_processed"], 0)

        # Verify we have details for all issues
        self.assertEqual(len(result["details"]), len(issues))

        # Find tab order issue details
        tab_order_details = [
            d
            for d in result["details"]
            if d["type"] in ["positive-tabindex", "unnecessary-tabindex-zero"]
        ]

        # Should have 3 tab order issues
        self.assertEqual(len(tab_order_details), 3)

    def test_tab_order_optimization_disabled(self):
        """Test that tab order optimization can be disabled."""
        issues = [
            {
                "id": "issue-1",
                "type": "positive-tabindex",
                "severity": "critical",
                "selector": "button[tabindex='5']",
                "context": "Button with tabindex=5",
            }
        ]

        soup = BeautifulSoup(self.sample_html, "html.parser")
        options = {"optimize_tab_order": False, "disable_ai": True}  # Disabled

        manager = RemediationManager(soup, options)
        result = manager.remediate_issues(issues)

        # When disabled, tab order issues should be skipped
        # They won't be processed through the tab order remediation
        self.assertEqual(result["issues_processed"], len(issues))

    def test_remediate_tab_order_issues_directly(self):
        """Test calling remediate_tab_order_issues directly."""
        tab_order_issues = [
            {
                "id": "issue-1",
                "type": "positive-tabindex",
                "severity": "critical",
                "selector": "button[tabindex='5']",
                "context": "Button with tabindex=5",
                "element": '<button tabindex="5">Button 1</button>',
            }
        ]

        soup = BeautifulSoup(self.sample_html, "html.parser")
        options = {
            "optimize_tab_order": True,
            "ai_validate_tab_order": False,  # Disable AI for unit test
            "disable_ai": True,
        }

        manager = RemediationManager(soup, options)
        result = manager.remediate_tab_order_issues(tab_order_issues)

        # Verify result structure
        self.assertIn("issues_processed", result)
        self.assertIn("issues_remediated", result)
        self.assertIn("changes", result)
        self.assertIn("ai_validation_performed", result)

        # Should have processed 1 issue
        self.assertEqual(result["issues_processed"], 1)

        # AI validation should be disabled
        self.assertFalse(result["ai_validation_performed"])

    def test_empty_tab_order_issues(self):
        """Test handling of empty tab order issues list."""
        soup = BeautifulSoup(self.sample_html, "html.parser")
        options = {"optimize_tab_order": True, "disable_ai": True}

        manager = RemediationManager(soup, options)
        result = manager.remediate_tab_order_issues([])

        # Should return empty result
        self.assertEqual(result["issues_processed"], 0)
        self.assertEqual(result["issues_remediated"], 0)
        self.assertEqual(len(result["changes"]), 0)


if __name__ == "__main__":
    unittest.main()
