# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CSS style resolver.

Tests StyleResolver class functionality.
"""

import unittest
from bs4 import BeautifulSoup

from content_accessibility_utility_on_aws.utils.style_resolver import StyleResolver


class TestStyleResolver(unittest.TestCase):
    """Test cases for StyleResolver."""

    def test_inline_style_color(self):
        """Test extraction of inline style color."""
        html = '<p style="color: #FF0000;">Text</p>'
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        color = resolver.get_text_color(element)

        self.assertEqual(color, '#FF0000')

    def test_inline_style_background(self):
        """Test extraction of inline style background color."""
        html = '<div style="background-color: #0000FF;">Content</div>'
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('div')
        bg_color = resolver.get_background_color(element)

        self.assertEqual(bg_color, '#0000FF')

    def test_style_tag_parsing(self):
        """Test parsing of <style> tag CSS."""
        html = '''
        <html>
        <head>
            <style>
                .highlight { color: #00FF00; }
            </style>
        </head>
        <body>
            <p class="highlight">Text</p>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        color = resolver.get_text_color(element)

        self.assertEqual(color, '#00FF00')

    def test_css_specificity(self):
        """Test CSS specificity resolution."""
        html = '''
        <html>
        <head>
            <style>
                p { color: #000000; }
                .special { color: #FF0000; }
            </style>
        </head>
        <body>
            <p class="special">Text</p>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        color = resolver.get_text_color(element)

        # Class selector should override element selector
        self.assertEqual(color, '#FF0000')

    def test_inline_overrides_stylesheet(self):
        """Test that inline styles override stylesheet."""
        html = '''
        <html>
        <head>
            <style>
                .blue { color: #0000FF; }
            </style>
        </head>
        <body>
            <p class="blue" style="color: #FF0000;">Text</p>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        color = resolver.get_text_color(element)

        # Inline style should override stylesheet
        self.assertEqual(color, '#FF0000')

    def test_color_normalization_short_hex(self):
        """Test normalization of short hex colors."""
        resolver = StyleResolver(BeautifulSoup('', 'html.parser'))

        # #RGB should be converted to #RRGGBB
        normalized = resolver._normalize_color('#F0A')
        self.assertEqual(normalized, '#FF00AA')

    def test_color_normalization_rgb(self):
        """Test normalization of rgb() colors."""
        resolver = StyleResolver(BeautifulSoup('', 'html.parser'))

        normalized = resolver._normalize_color('rgb(255, 0, 0)')
        self.assertEqual(normalized, '#FF0000')

    def test_color_normalization_named(self):
        """Test normalization of named colors."""
        resolver = StyleResolver(BeautifulSoup('', 'html.parser'))

        self.assertEqual(resolver._normalize_color('black'), '#000000')
        self.assertEqual(resolver._normalize_color('white'), '#FFFFFF')
        self.assertEqual(resolver._normalize_color('red'), '#FF0000')

    def test_background_inheritance(self):
        """Test background color inheritance from parent."""
        html = '''
        <div style="background-color: #CCCCCC;">
            <p>Text</p>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        bg_color = resolver.get_background_color(element)

        # Should inherit from parent div
        self.assertEqual(bg_color, '#CCCCCC')

    def test_font_weight_detection(self):
        """Test font weight detection."""
        html = '<strong>Bold text</strong>'
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('strong')
        font_weight = resolver.get_font_weight(element)

        self.assertEqual(font_weight, 'bold')

    def test_font_size_parsing(self):
        """Test font size parsing."""
        html = '<p style="font-size: 24px;">Large text</p>'
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')
        font_size = resolver.get_font_size(element)

        self.assertEqual(font_size, '24px')

    def test_default_values(self):
        """Test default color values."""
        html = '<p>Plain text</p>'
        soup = BeautifulSoup(html, 'html.parser')
        resolver = StyleResolver(soup)

        element = soup.find('p')

        # Default text color should be black
        text_color = resolver.get_text_color(element)
        self.assertEqual(text_color, '#000000')

        # Default background should be white
        bg_color = resolver.get_background_color(element)
        self.assertEqual(bg_color, '#FFFFFF')


if __name__ == '__main__':
    unittest.main()
