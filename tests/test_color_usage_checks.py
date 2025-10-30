# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for color usage accessibility checks.

Tests ColorUsageCheck class (WCAG 1.4.1).
"""

import unittest
from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.audit.checks.color_usage_checks import ColorUsageCheck


class TestColorUsageCheck(unittest.TestCase):
    """Test cases for ColorUsageCheck."""

    def setUp(self):
        """Set up test fixtures."""
        self.issues = []

    def add_issue_callback(self, issue_type, wcag, severity, element=None, description="", location=None):
        """Callback to collect issues."""
        self.issues.append({
            'type': issue_type,
            'wcag': wcag,
            'severity': severity,
            'element': str(element) if element else None,
            'description': description,
            'location': location or {}
        })

    def test_required_field_with_only_red_asterisk(self):
        """Test detection of required field indicated only by red asterisk."""
        html = '''
        <html>
        <body>
            <label>Name <span style="color: #FF0000;">*</span></label>
            <input type="text" id="name">
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should detect color-only indication
        color_only_issues = [i for i in self.issues if i['type'] == 'color-only-indication']
        self.assertGreater(len(color_only_issues), 0)
        self.assertEqual(color_only_issues[0]['wcag'], '1.4.1')

    def test_required_field_with_aria_attribute(self):
        """Test that required field with aria-required is acceptable."""
        html = '''
        <html>
        <body>
            <label>Name <span style="color: #FF0000;">*</span></label>
            <input type="text" id="name" aria-required="true">
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should not detect issue with aria-required
        color_only_issues = [i for i in self.issues if i['type'] == 'color-only-indication']
        # Filter for required field pattern
        required_issues = [i for i in color_only_issues if i['location'].get('pattern') == 'required_field_indicator']
        self.assertEqual(len(required_issues), 0)

    def test_link_without_underline(self):
        """Test detection of link distinguished only by color."""
        html = '''
        <html>
        <body>
            <p style="color: #000000;">This is text with a
            <a href="#" style="color: #0000FF; text-decoration: none;">link</a> in it.</p>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should detect link without underline
        link_issues = [i for i in self.issues if i['location'].get('pattern') == 'link_without_underline']
        self.assertGreater(len(link_issues), 0)

    def test_link_with_underline(self):
        """Test that link with underline is acceptable."""
        html = '''
        <html>
        <body>
            <p style="color: #000000;">This is text with a
            <a href="#" style="color: #0000FF; text-decoration: underline;">link</a> in it.</p>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should not detect issue with underlined link
        link_issues = [i for i in self.issues if i['location'].get('pattern') == 'link_without_underline']
        self.assertEqual(len(link_issues), 0)

    def test_form_validation_error_color_only(self):
        """Test detection of validation error shown only in red."""
        html = '''
        <html>
        <body>
            <div class="error" style="color: #FF0000; border: 1px solid #FF0000;">
                Please fix this field
            </div>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should detect form validation error (no explicit "error" or "invalid" text)
        error_issues = [i for i in self.issues if i['location'].get('pattern') == 'form_validation_error']
        self.assertGreater(len(error_issues), 0)

    def test_form_validation_with_explicit_text(self):
        """Test that validation error with explicit 'Error:' text is acceptable."""
        html = '''
        <html>
        <body>
            <div class="error" style="color: #FF0000;">
                Error: Invalid input
            </div>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should not detect issue with explicit error text
        error_issues = [i for i in self.issues if i['location'].get('pattern') == 'form_validation_error']
        self.assertEqual(len(error_issues), 0)

    def test_status_badge_color_only(self):
        """Test detection of status badge indicated only by color."""
        html = '''
        <html>
        <body>
            <span class="badge" style="background-color: #00FF00;">OK</span>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should detect status badge
        status_issues = [i for i in self.issues if i['location'].get('pattern') == 'status_badge']
        self.assertGreater(len(status_issues), 0)

    def test_status_badge_with_meaningful_text(self):
        """Test that status badge with meaningful text is acceptable."""
        html = '''
        <html>
        <body>
            <span class="badge" style="background-color: #00FF00;">Success</span>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        check = ColorUsageCheck(soup, self.add_issue_callback)
        check.check()

        # Should not detect issue with meaningful text
        status_issues = [i for i in self.issues if i['location'].get('pattern') == 'status_badge']
        self.assertEqual(len(status_issues), 0)

    def test_is_error_color(self):
        """Test error color detection."""
        check = ColorUsageCheck(BeautifulSoup('', 'html.parser'), self.add_issue_callback)

        # Red should be detected as error color
        self.assertTrue(check._is_error_color('#FF0000'))
        self.assertTrue(check._is_error_color('#CC0000'))

        # Green should not be error color
        self.assertFalse(check._is_error_color('#00FF00'))

        # Black should not be error color
        self.assertFalse(check._is_error_color('#000000'))

    def test_is_status_color(self):
        """Test status color detection."""
        check = ColorUsageCheck(BeautifulSoup('', 'html.parser'), self.add_issue_callback)

        # Green (success)
        self.assertTrue(check._is_status_color('#00FF00'))

        # Red (error)
        self.assertTrue(check._is_status_color('#FF0000'))

        # Yellow (warning)
        self.assertTrue(check._is_status_color('#FFFF00'))

        # Blue (info)
        self.assertTrue(check._is_status_color('#0000FF'))

        # Gray should not be status color
        self.assertFalse(check._is_status_color('#808080'))


if __name__ == '__main__':
    unittest.main()
